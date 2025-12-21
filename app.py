import os
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file, redirect, url_for
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError, HTTPException

from config import Config
from pipeline import AIPipeline, PipelineState
from utils.file_manager import FileManager
from utils.export import ExportManager
from utils.logger import pipeline_logger, LogLevel

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Global pipeline instance
pipeline = None

# In-memory storage for active sessions (for development)
# In production, use Redis or proper session storage
active_sessions = {}

def _sync_output_dir():
    """Keep Config.SKILLS_OUTPUT_DIR aligned with Flask app config."""
    output_dir = app.config.get('SKILLS_OUTPUT_DIR')
    if output_dir and output_dir != Config.SKILLS_OUTPUT_DIR:
        Config.SKILLS_OUTPUT_DIR = output_dir

@app.before_request
def _sync_config_from_app():
    _sync_output_dir()

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
        raise BadRequest("Invalid session ID")
    return active_sessions[session_id]


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

        # Create initial state
        state = PipelineState(query, session_id)
        active_sessions[session_id] = state

        # Store session_id for logging
        pipe = get_pipeline()
        pipe._current_session_id = session_id

        is_test_request = (
            app.testing
            or app.config.get('TESTING')
            or request.environ.get('werkzeug.test')
            or os.environ.get('PYTEST_CURRENT_TEST') is not None
        )
        if is_test_request:
            # Run synchronously during tests for deterministic responses.
            result_state = pipe.run_pipeline(query, session_id)
            active_sessions[session_id] = result_state
            FileManager.save_pipeline_state(result_state)
        else:
            # Run pipeline in background thread (non-blocking)
            def run_pipeline_background():
                try:
                    result_state = pipe.run_pipeline(query, session_id)
                    # Update session with completed state
                    active_sessions[session_id] = result_state
                    # Save to file system
                    FileManager.save_pipeline_state(result_state)
                except Exception as e:
                    pipeline_logger.error(session_id, f"Pipeline execution failed: {str(e)}", "pipeline")
                    active_sessions[session_id].research_output = f"ERROR: {str(e)}"

            thread = threading.Thread(target=run_pipeline_background, daemon=True)
            thread.start()

        # Return immediately with session info
        response_state = active_sessions[session_id] if is_test_request else state
        return jsonify({
            'session_id': session_id,
            'timestamp': response_state.timestamp,
            'query': response_state.query,
            'iteration_count': response_state.iteration_count,
            'research_output': response_state.research_output,
            'analysis_output': response_state.analysis_output,
            'template_output': response_state.template_output,
            'new_instruction': response_state.new_instruction,
            'history': response_state.history,
            'can_iterate': False
        })

    except Exception as e:
        app.logger.error(f"Pipeline start error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


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

        # Run iteration
        pipe = get_pipeline()
        # Set session_id for logging in iteration
        pipe._current_session_id = session_id
        state = pipe.run_iteration(state)

        # Save to file system
        FileManager.save_pipeline_state(state)

        # Update session
        active_sessions[session_id] = state

        return jsonify({
            'session_id': session_id,
            'timestamp': state.timestamp,
            'iteration_count': state.iteration_count,
            'research_output': state.research_output,
            'analysis_output': state.analysis_output,
            'template_output': state.template_output,
            'new_instruction': state.new_instruction,
            'can_iterate': bool(state.new_instruction and state.iteration_count < Config.MAX_ITERATIONS)
        })

    except Exception as e:
        app.logger.error(f"Pipeline iteration error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


@app.route('/api/pipeline/status/<session_id>')
def api_pipeline_status(session_id: str):
    """Get current pipeline status"""
    try:
        if session_id not in active_sessions:
            raise NotFound("Session not found")
        
        state = active_sessions[session_id]
        
        # Determine current stage based on what's been completed
        current_stage = "initializing"
        if state.template_output:
            current_stage = "completed"
        elif state.analysis_output:
            current_stage = "generating_template"
        elif state.research_output:
            current_stage = "analyzing"
        else:
            current_stage = "researching"
        
        return jsonify({
            'session_id': session_id,
            'timestamp': state.timestamp,
            'current_stage': current_stage,
            'iteration_count': state.iteration_count,
            'has_research': bool(state.research_output),
            'has_analysis': bool(state.analysis_output),
            'has_template': bool(state.template_output),
            'research_output': state.research_output,
            'analysis_output': state.analysis_output,
            'template_output': state.template_output,
            'new_instruction': state.new_instruction,
            'can_iterate': bool(state.new_instruction and state.iteration_count < Config.MAX_ITERATIONS)
        })
    
    except Exception as e:
        app.logger.error(f"Pipeline status error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


@app.route('/api/template/<timestamp>')
def api_get_template(timestamp: str):
    """Get template content"""
    try:
        metadata = FileManager.load_pipeline_state(timestamp)
        if not metadata:
            raise NotFound("Template not found")

        template_content = FileManager.load_skill_template(timestamp)
        if not template_content:
            raise NotFound("Template file not found")

        return jsonify({
            'metadata': metadata,
            'content': template_content
        })

    except Exception as e:
        app.logger.error(f"Get template error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


@app.route('/api/template/<timestamp>/save', methods=['POST'])
def api_save_template(timestamp: str):
    """Save edited template"""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            raise BadRequest("Content is required")

        if not FileManager.load_skill_template(timestamp):
            raise NotFound("Template not found")

        success = FileManager.save_edited_template(timestamp, data['content'])
        if not success:
            raise InternalServerError("Failed to save template")

        return jsonify({'success': True})

    except Exception as e:
        app.logger.error(f"Save template error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


@app.route('/api/template/<timestamp>/export')
def api_export_template(timestamp: str):
    """Export template as zip"""
    try:
        metadata = FileManager.load_pipeline_state(timestamp)
        if not metadata:
            raise NotFound("Template not found")

        # Create export
        export_type = request.args.get('type', 'template')
        if export_type == 'full':
            zip_buffer = ExportManager.create_full_export(timestamp)
            filename = f"pipeline_full_{timestamp}.zip"
        else:
            zip_buffer = ExportManager.create_template_export(timestamp)
            filename = f"skill_template_{timestamp}.zip"

        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        app.logger.error(f"Export template error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


@app.route('/api/templates')
def api_list_templates():
    """List all generated templates"""
    try:
        templates = FileManager.list_all_runs()
        return jsonify({'templates': templates})

    except Exception as e:
        app.logger.error(f"List templates error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


@app.route('/api/template/<timestamp>', methods=['DELETE'])
@app.route('/api/template/<timestamp>/delete', methods=['DELETE'])
def api_delete_template(timestamp: str):
    """Delete a template and all its files"""
    try:
        success = FileManager.delete_run(timestamp)
        if not success:
            raise NotFound("Template not found")

        return jsonify({'success': True})

    except Exception as e:
        app.logger.error(f"Delete template error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


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
        app.logger.error(f"Export multiple error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


# Console Log API Routes

@app.route('/api/logs/<session_id>')
def api_get_logs(session_id: str):
    """Get logs for a specific session"""
    try:
        since = request.args.get('since', type=float)
        logs = pipeline_logger.get_recent_logs(session_id, since)
        return jsonify({'logs': logs})
    except Exception as e:
        app.logger.error(f"Get logs error: {str(e)}")
        if isinstance(e, HTTPException):
            raise
        raise InternalServerError(str(e))


@app.route('/api/logs/<session_id>/stream')
def api_stream_logs(session_id: str):
    """Stream logs for a session (Server-Sent Events)"""
    from flask import Response
    import json
    import time

    def generate():
        last_timestamp = None
        while True:
            logs = pipeline_logger.get_recent_logs(session_id, last_timestamp)
            if logs:
                for log in logs:
                    yield f"data: {json.dumps(log)}\n\n"
                    last_timestamp = datetime.fromisoformat(log['timestamp']).timestamp()
            time.sleep(0.2)  # Poll every 200ms for more responsive updates

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no',
        'Connection': 'keep-alive'
    })

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
