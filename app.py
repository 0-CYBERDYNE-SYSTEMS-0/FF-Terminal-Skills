import os
from flask import Flask, request, jsonify, render_template, send_file, redirect, url_for
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

        # Run pipeline
        pipe = get_pipeline()
        state = pipe.run_pipeline(query)

        # Save to file system
        FileManager.save_pipeline_state(state)

        # Store in session
        active_sessions[session_id] = state

        return jsonify({
            'session_id': session_id,
            'timestamp': state.timestamp,
            'query': state.query,
            'iteration_count': state.iteration_count,
            'research_output': state.research_output,
            'analysis_output': state.analysis_output,
            'template_output': state.template_output,
            'new_instruction': state.new_instruction,
            'history': state.history,
            'can_iterate': bool(state.new_instruction and state.iteration_count < Config.MAX_ITERATIONS)
        })

    except Exception as e:
        app.logger.error(f"Pipeline start error: {str(e)}")
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
        raise InternalServerError(str(e))


@app.route('/api/template/<timestamp>/save', methods=['POST'])
def api_save_template(timestamp: str):
    """Save edited template"""
    try:
        data = request.get_json()
        if not data or 'content' not in data:
            raise BadRequest("Content is required")

        success = FileManager.save_edited_template(timestamp, data['content'])
        if not success:
            raise InternalServerError("Failed to save template")

        return jsonify({'success': True})

    except Exception as e:
        app.logger.error(f"Save template error: {str(e)}")
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
        raise InternalServerError(str(e))


@app.route('/api/templates')
def api_list_templates():
    """List all generated templates"""
    try:
        templates = FileManager.list_all_runs()
        return jsonify({'templates': templates})

    except Exception as e:
        app.logger.error(f"List templates error: {str(e)}")
        raise InternalServerError(str(e))


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
        raise InternalServerError(str(e))


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