import os
import json
import queue
from datetime import datetime
from threading import Thread

from flask import Flask, request, jsonify, render_template, send_file, redirect, url_for, Response, stream_with_context
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError

from config import Config
from pipeline import AIPipeline, PipelineState
from utils.file_manager import FileManager
from utils.export import ExportManager

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Global pipeline instance
pipeline = None

# In-memory storage for active sessions (for development)
# In production, use Redis or proper session storage
active_sessions = {}
session_status = {}
session_logs = {}
session_log_queues = {}
LOG_BUFFER_LIMIT = 500


def get_pipeline():
    """Get or create pipeline instance"""
    global pipeline
    if pipeline is None:
        Config.validate()
        pipeline = AIPipeline()
    return pipeline


def get_session_state(session_id: str) -> PipelineState:
    """Get or create session state"""
    if session_id not in active_sessions:
        if session_id in session_status:
            raise BadRequest("Session not ready")
        raise BadRequest("Invalid session ID")
    return active_sessions[session_id]


def init_session_logging(session_id: str) -> None:
    session_logs[session_id] = []
    session_log_queues[session_id] = queue.Queue()


def append_session_log(session_id: str, message: str) -> None:
    entry = {
        "timestamp": datetime.now().isoformat(),
        "message": message
    }
    session_logs[session_id].append(entry)
    if len(session_logs[session_id]) > LOG_BUFFER_LIMIT:
        session_logs[session_id] = session_logs[session_id][-LOG_BUFFER_LIMIT:]
    session_log_queues[session_id].put(entry)


def create_session_logger(session_id: str):
    def _logger(message: str) -> None:
        append_session_log(session_id, message)
    return _logger


def update_session_status(session_id: str, status: str = None,
                          stage: str = None, error: str = None) -> None:
    info = session_status.get(session_id)
    if not info:
        return
    if status is not None:
        info["status"] = status
    if stage is not None:
        info["stage"] = stage
    if error is not None:
        info["error"] = error
    info["updated_at"] = datetime.now().isoformat()


def handle_api_exception(context: str, error: Exception):
    if isinstance(error, (BadRequest, NotFound)):
        raise error
    app.logger.error(f"{context} error: {str(error)}")
    raise InternalServerError(str(error))


@app.route('/')
def index():
    """Main UI page"""
    return render_template('index.html')


@app.route('/preview/<timestamp>')
def preview(timestamp: str):
    """Template preview and edit page"""
    metadata = FileManager.load_pipeline_state(timestamp)
    if not metadata:
        raise NotFound("Template not found")

    template_content = FileManager.load_skill_template(timestamp)
    if not template_content:
        raise NotFound("Template file not found")

    return render_template('preview.html',
                         timestamp=timestamp,
                         metadata=metadata,
                         content=template_content)


# API Routes

@app.route('/api/pipeline/start', methods=['POST'])
def api_pipeline_start():
    """Start a new pipeline run"""
    try:
        data = request.get_json()
        if not data or 'query' not in data:
            raise BadRequest("Query is required")

        query = data['query'].strip()
        if not query:
            raise BadRequest("Query cannot be empty")

        # Generate session ID
        import uuid
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        session_status[session_id] = {
            "status": "queued",
            "stage": "queued",
            "query": query,
            "timestamp": timestamp,
            "error": None,
            "started_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        init_session_logging(session_id)

        def stage_callback(stage: str) -> None:
            update_session_status(session_id, stage=stage)
            append_session_log(session_id, f"Stage: {stage}")

        def run_pipeline_async() -> None:
            logger = create_session_logger(session_id)
            try:
                update_session_status(session_id, status="running", stage="research")
                logger("Pipeline started")
                pipe = get_pipeline()
                state = pipe.run_pipeline(
                    query,
                    logger=logger,
                    session_id=session_id,
                    timestamp=timestamp,
                    stage_callback=stage_callback
                )
                # Save to file system
                FileManager.save_pipeline_state(state)
                # Store in session
                active_sessions[session_id] = state
                update_session_status(session_id, status="completed", stage="completed")
                logger("Pipeline completed")
            except Exception as e:
                update_session_status(session_id, status="error", stage="error", error=str(e))
                logger(f"Pipeline error: {str(e)}")

        Thread(target=run_pipeline_async, daemon=True).start()

        return jsonify({
            'session_id': session_id,
            'timestamp': timestamp,
            'query': query,
            'status': session_status[session_id]["status"],
            'stage': session_status[session_id]["stage"]
        }), 202

    except Exception as e:
        handle_api_exception("Pipeline start", e)


@app.route('/api/pipeline/iterate', methods=['POST'])
def api_pipeline_iterate():
    """Run a pipeline iteration"""
    try:
        data = request.get_json()
        if not data or 'session_id' not in data:
            raise BadRequest("Session ID is required")

        session_id = data['session_id']
        state = get_session_state(session_id)

        # Check if iteration is possible
        if state.iteration_count >= Config.MAX_ITERATIONS:
            raise BadRequest(f"Maximum iterations ({Config.MAX_ITERATIONS}) reached")

        if not state.new_instruction:
            raise BadRequest("No instruction available for iteration")

        def stage_callback(stage: str) -> None:
            update_session_status(session_id, stage=stage)
            append_session_log(session_id, f"Stage: {stage}")

        def run_iteration_async() -> None:
            logger = create_session_logger(session_id)
            try:
                update_session_status(session_id, status="running", stage="research")
                logger("Iteration started")
                pipe = get_pipeline()
                updated_state = pipe.run_iteration(
                    state,
                    logger=logger,
                    stage_callback=stage_callback
                )
                # Save to file system
                FileManager.save_pipeline_state(updated_state)
                # Update session
                active_sessions[session_id] = updated_state
                update_session_status(session_id, status="completed", stage="completed")
                logger("Iteration completed")
            except Exception as e:
                update_session_status(session_id, status="error", stage="error", error=str(e))
                logger(f"Iteration error: {str(e)}")

        Thread(target=run_iteration_async, daemon=True).start()

        return jsonify({
            'session_id': session_id,
            'status': session_status.get(session_id, {}).get("status"),
            'stage': session_status.get(session_id, {}).get("stage")
        }), 202

    except Exception as e:
        handle_api_exception("Pipeline iteration", e)


@app.route('/api/pipeline/status')
def api_pipeline_status():
    """Get pipeline status for a session"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            raise BadRequest("Session ID is required")

        if session_id not in session_status:
            raise BadRequest("Invalid session ID")

        status_info = session_status[session_id]
        state = active_sessions.get(session_id)

        response = {
            'session_id': session_id,
            'status': status_info.get('status'),
            'stage': status_info.get('stage'),
            'error': status_info.get('error'),
            'timestamp': status_info.get('timestamp'),
            'query': status_info.get('query'),
            'iteration_count': state.iteration_count if state else 0,
            'research_output': state.research_output if state else "",
            'analysis_output': state.analysis_output if state else "",
            'template_output': state.template_output if state else "",
            'new_instruction': state.new_instruction if state else "",
            'can_iterate': bool(state and state.new_instruction and state.iteration_count < Config.MAX_ITERATIONS),
            'skill_name': state.skill_name if state else "",
            'bundle_tree': state.bundle_tree if state else ""
        }

        return jsonify(response)

    except Exception as e:
        handle_api_exception("Pipeline status", e)


@app.route('/api/pipeline/logs')
def api_pipeline_logs():
    """Stream pipeline logs via SSE"""
    try:
        session_id = request.args.get('session_id')
        if not session_id:
            raise BadRequest("Session ID is required")

        if session_id not in session_logs:
            raise BadRequest("Invalid session ID")

        def stream():
            # Send existing log buffer first
            for entry in session_logs.get(session_id, []):
                yield f"data: {json.dumps(entry)}\n\n"

            log_queue = session_log_queues.get(session_id)
            while True:
                try:
                    entry = log_queue.get(timeout=30)
                except queue.Empty:
                    yield "event: ping\ndata: {}\n\n"
                    continue
                yield f"data: {json.dumps(entry)}\n\n"

        return Response(stream_with_context(stream()), mimetype='text/event-stream')

    except Exception as e:
        handle_api_exception("Pipeline log stream", e)


@app.route('/api/template/<timestamp>', methods=['GET', 'DELETE'])
def api_template(timestamp: str):
    """Get or delete template content"""
    try:
        if request.method == 'DELETE':
            success = FileManager.delete_run(timestamp)
            if not success:
                raise NotFound("Template not found")
            return jsonify({'success': True})

        metadata = FileManager.load_pipeline_state(timestamp)
        if not metadata:
            raise NotFound("Template not found")

        template_content = FileManager.load_skill_template(timestamp)
        if not template_content:
            raise NotFound("Template file not found")

        return jsonify({
            'metadata': metadata,
            'content': template_content,
            'skill_name': metadata.get('skill_name', ''),
            'bundle_tree': metadata.get('bundle_tree', '')
        })

    except Exception as e:
        handle_api_exception("Get template", e)


@app.route('/api/template/<timestamp>/save', methods=['POST'])
def api_save_template(timestamp: str):
    """Save edited template"""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            raise BadRequest("Content is required")

        metadata = FileManager.load_pipeline_state(timestamp)
        if not metadata:
            raise NotFound("Template not found")

        success = FileManager.save_edited_template(timestamp, data['content'])
        if not success:
            raise InternalServerError("Failed to save template")

        return jsonify({'success': True})

    except Exception as e:
        handle_api_exception("Save template", e)


@app.route('/api/template/<timestamp>/export')
def api_export_template(timestamp: str):
    """Export template as zip"""
    try:
        metadata = FileManager.load_pipeline_state(timestamp)
        if not metadata:
            raise NotFound("Template not found")

        # Create export
        export_type = request.args.get('type', 'bundle')
        if export_type == 'full':
            zip_buffer = ExportManager.create_full_export(timestamp)
            filename = f"pipeline_full_{timestamp}.zip"
        elif export_type in ('template', 'skill'):
            zip_buffer = ExportManager.create_skill_export(timestamp)
            filename = f"{metadata.get('skill_name', 'skill')}_SKILL.zip"
        else:
            zip_buffer = ExportManager.create_bundle_export(timestamp)
            filename = f"{metadata.get('skill_name', 'skill')}_bundle.zip"

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        handle_api_exception("Export template", e)


@app.route('/api/templates')
def api_list_templates():
    """List all generated templates"""
    try:
        templates = FileManager.list_all_runs()
        return jsonify({'templates': templates})

    except Exception as e:
        handle_api_exception("List templates", e)


@app.route('/api/template/<timestamp>/delete', methods=['DELETE'])
def api_delete_template(timestamp: str):
    """Delete a template and all its files"""
    try:
        success = FileManager.delete_run(timestamp)
        if not success:
            raise NotFound("Template not found")

        return jsonify({'success': True})

    except Exception as e:
        handle_api_exception("Delete template", e)


@app.route('/api/templates/export', methods=['POST'])
def api_export_multiple():
    """Export multiple templates"""
    try:
        data = request.get_json()
        if not data or 'timestamps' not in data:
            raise BadRequest("Timestamps are required")

        timestamps = data['timestamps']
        if not timestamps:
            raise BadRequest("At least one template must be selected")

        zip_buffer = ExportManager.create_multi_export(timestamps)
        filename = f"skills_batch_{len(timestamps)}_templates.zip"

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        handle_api_exception("Export multiple", e)


# Error Handlers

@app.errorhandler(BadRequest)
def handle_bad_request(e):
    return jsonify({'error': str(e)}), 400


@app.errorhandler(NotFound)
def handle_not_found(e):
    return jsonify({'error': str(e)}), 404


@app.errorhandler(InternalServerError)
def handle_internal_error(e):
    return jsonify({'error': str(e)}), 500


# Initialize
if __name__ == '__main__':
    # Ensure output directory exists
    FileManager.ensure_output_dir()

    # Run development server on port 5001 (5000 often used by AirPlay on macOS)
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=5001)
