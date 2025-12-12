import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import patch, Mock, MagicMock

from app import app
from pipeline import PipelineState
from utils.file_manager import FileManager


class TestFlaskApp(unittest.TestCase):
    """Test Flask application routes and functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.app = app.test_client()
        self.app.testing = True

        # Create temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()
        self.original_output_dir = app.config.get('SKILLS_OUTPUT_DIR')
        app.config['SKILLS_OUTPUT_DIR'] = self.temp_dir

    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_index_route(self):
        """Test main index route"""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'AI Skills Development Pipeline', response.data)

    def test_preview_route_not_found(self):
        """Test preview route with non-existent template"""
        response = self.app.get('/preview/non-existent')
        self.assertEqual(response.status_code, 404)

    @patch('app.get_pipeline')
    @patch('app.Config')
    def test_api_pipeline_start_success(self, mock_config, mock_get_pipeline):
        """Test successful pipeline start"""
        # Mock config validation
        mock_config.validate.return_value = True

        # Mock pipeline
        mock_pipeline = Mock()
        mock_state = PipelineState("Test query")
        mock_state.research_output = "Research"
        mock_state.analysis_output = "Analysis"
        mock_state.template_output = "Template"
        mock_state.new_instruction = "Instruction"
        mock_pipeline.run_pipeline.return_value = mock_state
        mock_get_pipeline.return_value = mock_pipeline

        # Mock file manager
        with patch('app.FileManager.save_pipeline_state') as mock_save:
            response = self.app.post('/api/pipeline/start',
                                   json={'query': 'Test query'},
                                   content_type='application/json')

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['query'], 'Test query')
            self.assertEqual(data['research_output'], 'Research')
            self.assertEqual(data['analysis_output'], 'Analysis')
            self.assertEqual(data['template_output'], 'Template')
            self.assertEqual(data['new_instruction'], 'Instruction')

    def test_api_pipeline_start_missing_query(self):
        """Test pipeline start without query"""
        response = self.app.post('/api/pipeline/start',
                               json={},
                               content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Query is required', response.json['error'])

    def test_api_pipeline_start_empty_query(self):
        """Test pipeline start with empty query"""
        response = self.app.post('/api/pipeline/start',
                               json={'query': '   '},
                               content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Query cannot be empty', response.json['error'])

    def test_api_pipeline_start_invalid_json(self):
        """Test pipeline start with invalid JSON"""
        response = self.app.post('/api/pipeline/start',
                               data='invalid json',
                               content_type='application/json')
        self.assertEqual(response.status_code, 400)

    @patch('app.get_pipeline')
    def test_api_pipeline_iterate_success(self, mock_get_pipeline):
        """Test successful pipeline iteration"""
        # Create mock state
        mock_state = PipelineState("Test query")
        mock_state.iteration_count = 1
        mock_state.new_instruction = "New instruction"
        mock_state.research_output = "New research"
        mock_state.analysis_output = "New analysis"
        mock_state.template_output = "New template"

        # Mock pipeline
        mock_pipeline = Mock()
        mock_pipeline.run_iteration.return_value = mock_state
        mock_get_pipeline.return_value = mock_pipeline

        # Add to active sessions
        with patch('app.active_sessions', {'test-session': mock_state}):
            response = self.app.post('/api/pipeline/iterate',
                                   json={'session_id': 'test-session'},
                                   content_type='application/json')

            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(data['iteration_count'], 1)
            self.assertEqual(data['research_output'], "New research")

    def test_api_pipeline_iterate_missing_session(self):
        """Test iteration without session ID"""
        response = self.app.post('/api/pipeline/iterate',
                               json={},
                               content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Session ID is required', response.json['error'])

    def test_api_pipeline_iterate_invalid_session(self):
        """Test iteration with invalid session ID"""
        with patch('app.active_sessions', {}):
            response = self.app.post('/api/pipeline/iterate',
                                   json={'session_id': 'invalid'},
                                   content_type='application/json')
            self.assertEqual(response.status_code, 400)
            self.assertIn('Invalid session ID', response.json['error'])

    def test_api_get_template_not_found(self):
        """Test getting non-existent template"""
        response = self.app.get('/api/template/non-existent')
        self.assertEqual(response.status_code, 404)

    def test_api_get_template_success(self):
        """Test successful template retrieval"""
        # Create test template
        timestamp = "2023-01-01_00-00-00"
        template_dir = os.path.join(self.temp_dir, timestamp)
        os.makedirs(template_dir)

        # Create skill.md and metadata.json
        with open(os.path.join(template_dir, 'skill.md'), 'w') as f:
            f.write('Test template content')

        metadata = {
            'query': 'Test query',
            'iteration_count': 1,
            'created_at': '2023-01-01T00:00:00'
        }
        with open(os.path.join(template_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f)

        response = self.app.get(f'/api/template/{timestamp}')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['content'], 'Test template content')
        self.assertEqual(data['metadata']['query'], 'Test query')

    def test_api_save_template_not_found(self):
        """Test saving non-existent template"""
        response = self.app.post('/api/template/non-existent/save',
                               json={'content': 'Test'},
                               content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_api_save_template_success(self):
        """Test successful template save"""
        # Create test template
        timestamp = "2023-01-01_00-00-00"
        template_dir = os.path.join(self.temp_dir, timestamp)
        os.makedirs(template_dir)

        skill_file = os.path.join(template_dir, 'skill.md')
        with open(skill_file, 'w') as f:
            f.write('Original content')

        # Save new content
        response = self.app.post(f'/api/template/{timestamp}/save',
                               json={'content': 'Updated content'},
                               content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])

        # Verify file was updated
        with open(skill_file, 'r') as f:
            self.assertEqual(f.read(), 'Updated content')

    def test_api_list_templates_empty(self):
        """Test listing templates when none exist"""
        response = self.app.get('/api/templates')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data['templates'], [])

    def test_api_list_templates_success(self):
        """Test successful template listing"""
        # Create test templates
        for i in range(2):
            timestamp = f"2023-01-01_00-0{i}-00"
            template_dir = os.path.join(self.temp_dir, timestamp)
            os.makedirs(template_dir)

            metadata = {
                'query': f'Test query {i}',
                'iteration_count': i + 1,
                'created_at': f'2023-01-01T00:0{i}:00'
            }
            with open(os.path.join(template_dir, 'metadata.json'), 'w') as f:
                json.dump(metadata, f)

        response = self.app.get('/api/templates')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(len(data['templates']), 2)
        # Should be sorted by timestamp (newest first)
        self.assertEqual(data['templates'][0]['query'], 'Test query 1')
        self.assertEqual(data['templates'][1]['query'], 'Test query 0')

    def test_api_delete_template_not_found(self):
        """Test deleting non-existent template"""
        response = self.app.delete('/api/template/non-existent')
        self.assertEqual(response.status_code, 404)

    def test_api_delete_template_success(self):
        """Test successful template deletion"""
        # Create test template
        timestamp = "2023-01-01_00-00-00"
        template_dir = os.path.join(self.temp_dir, timestamp)
        os.makedirs(template_dir)

        response = self.app.delete(f'/api/template/{timestamp}')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['success'])

        # Verify directory was deleted
        self.assertFalse(os.path.exists(template_dir))

    def test_error_handlers(self):
        """Test error handlers"""
        # Test 400 error
        response = self.app.post('/api/pipeline/start', json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json)

        # Test 404 error
        response = self.app.get('/non-existent-route')
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()