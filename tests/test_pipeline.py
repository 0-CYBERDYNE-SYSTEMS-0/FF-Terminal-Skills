import unittest
from unittest.mock import Mock, patch, MagicMock
import json

from pipeline import AIPipeline, PipelineState


class TestPipelineState(unittest.TestCase):
    """Test PipelineState class"""

    def test_init(self):
        """Test PipelineState initialization"""
        query = "Test query"
        state = PipelineState(query)

        self.assertEqual(state.query, query)
        self.assertIsNone(state.session_id)
        self.assertEqual(state.iteration_count, 0)
        self.assertEqual(state.research_output, "")
        self.assertEqual(state.analysis_output, "")
        self.assertEqual(state.template_output, "")
        self.assertEqual(state.new_instruction, "")
        self.assertEqual(state.history, [])
        self.assertIsNotNone(state.timestamp)

    def test_to_dict(self):
        """Test PipelineState to_dict method"""
        query = "Test query"
        state = PipelineState(query)
        state.research_output = "Research"
        state.analysis_output = "Analysis"
        state.template_output = "Template"
        state.new_instruction = "New instruction"
        state.iteration_count = 2
        state.history = [{"test": "data"}]

        result = state.to_dict()

        expected = {
            'query': query,
            'session_id': None,
            'timestamp': state.timestamp,
            'iteration_count': 2,
            'research_output': 'Research',
            'analysis_output': 'Analysis',
            'template_output': 'Template',
            'new_instruction': 'New instruction',
            'history': [{"test": "data"}]
        }

        self.assertEqual(result, expected)


class TestAIPipeline(unittest.TestCase):
    """Test AIPipeline class"""

    def setUp(self):
        """Set up test fixtures"""
        with patch('pipeline.Config.OPENROUTER_API_KEY', 'test-key'):
            self.pipeline = AIPipeline()

    @patch('pipeline.requests.post')
    def test_call_model_success(self, mock_post):
        """Test successful model call"""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Test response'}}]
        }
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Test message"}]
        result = self.pipeline.call_model("test-model", messages)

        self.assertEqual(result, 'Test response')
        mock_post.assert_called_once()

    @patch('pipeline.requests.post')
    def test_call_model_api_error(self, mock_post):
        """Test model call with API error"""
        # Mock error response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Test message"}]

        with self.assertRaises(Exception) as context:
            self.pipeline.call_model("test-model", messages)

        self.assertIn("API error for test-model: 400", str(context.exception))

    @patch('pipeline.requests.post')
    def test_call_model_request_error(self, mock_post):
        """Test model call with request error"""
        # Mock request exception
        import requests
        mock_post.side_effect = requests.exceptions.RequestException("Connection error")

        messages = [{"role": "user", "content": "Test message"}]

        with self.assertRaises(Exception) as context:
            self.pipeline.call_model("test-model", messages)

        self.assertIn("Request failed", str(context.exception))

    @patch.object(AIPipeline, 'call_model')
    def test_run_research(self, mock_call):
        """Test research stage"""
        mock_call.return_value = "Research results"

        result = self.pipeline.run_research("Test query")

        self.assertEqual(result, "Research results")
        mock_call.assert_called_once()

        # Check the call arguments
        call_args = mock_call.call_args
        self.assertIn("Test query", call_args[0][1][0]['content'])

    @patch.object(AIPipeline, 'call_model')
    def test_run_analysis_with_new_instruction(self, mock_call):
        """Test analysis stage with new instruction"""
        mock_response = """
        Issues: Some issues
        Shortcomings: Some shortcomings
        Enhancements: Some enhancements
        New Research Instruction: Research more deeply
        """
        mock_call.return_value = mock_response

        result, new_instruction = self.pipeline.run_analysis("Research output")

        self.assertEqual(result, mock_response)
        self.assertEqual(new_instruction, "Research more deeply")

    @patch.object(AIPipeline, 'call_model')
    def test_run_analysis_without_new_instruction(self, mock_call):
        """Test analysis stage without new instruction"""
        mock_response = """
        Issues: Some issues
        Shortcomings: Some shortcomings
        Enhancements: Some enhancements
        """
        mock_call.return_value = mock_response

        result, new_instruction = self.pipeline.run_analysis("Research output")

        self.assertEqual(result, mock_response)
        self.assertEqual(new_instruction, "")

    @patch.object(AIPipeline, 'call_model')
    def test_run_template_generation(self, mock_call):
        """Test template generation stage"""
        mock_call.return_value = "Template content"

        result = self.pipeline.run_template_generation("Research", "Analysis")

        self.assertEqual(result, "Template content")
        mock_call.assert_called_once()

    @patch.object(AIPipeline, 'run_template_generation')
    @patch.object(AIPipeline, 'run_analysis')
    @patch.object(AIPipeline, 'run_research')
    def test_run_pipeline(self, mock_research, mock_analysis, mock_template):
        """Test complete pipeline run"""
        # Mock stage returns
        mock_research.return_value = "Research output"
        mock_analysis.return_value = ("Analysis output", "New instruction")
        mock_template.return_value = "Template output"

        # Run pipeline
        state = self.pipeline.run_pipeline("Test query")

        # Verify state
        self.assertEqual(state.query, "Test query")
        self.assertEqual(state.iteration_count, 1)
        self.assertEqual(state.research_output, "Research output")
        self.assertEqual(state.analysis_output, "Analysis output")
        self.assertEqual(state.template_output, "Template output")
        self.assertEqual(state.new_instruction, "New instruction")
        self.assertEqual(len(state.history), 1)

        # Verify history
        history_item = state.history[0]
        self.assertEqual(history_item['iteration'], 1)
        self.assertEqual(history_item['research'], "Research output")
        self.assertEqual(history_item['analysis'], "Analysis output")
        self.assertEqual(history_item['template'], "Template output")
        self.assertEqual(history_item['instruction'], "New instruction")

    @patch.object(AIPipeline, 'run_template_generation')
    @patch.object(AIPipeline, 'run_analysis')
    @patch.object(AIPipeline, 'run_research')
    def test_run_iteration(self, mock_research, mock_analysis, mock_template):
        """Test pipeline iteration"""
        # Create initial state
        state = PipelineState("Original query")
        state.iteration_count = 1
        state.new_instruction = "Research deeper"
        state.analysis_output = "Previous analysis"
        state.history = [{"iteration": 1, "data": "test"}]

        # Mock stage returns
        mock_research.return_value = "New research"
        mock_analysis.return_value = ("New analysis", "Newer instruction")
        mock_template.return_value = "New template"

        # Run iteration
        new_state = self.pipeline.run_iteration(state)

        # Verify updated state
        self.assertEqual(new_state.iteration_count, 2)
        self.assertEqual(new_state.research_output, "New research")
        self.assertEqual(new_state.analysis_output, "New analysis")
        self.assertEqual(new_state.template_output, "New template")
        self.assertEqual(new_state.new_instruction, "Newer instruction")
        self.assertEqual(len(new_state.history), 2)

        # Verify new history item
        new_history = new_state.history[1]
        self.assertEqual(new_history['iteration'], 2)
        self.assertEqual(new_history['research'], "New research")
        self.assertEqual(new_history['analysis'], "New analysis")
        self.assertEqual(new_history['template'], "New template")
        self.assertEqual(new_history['instruction'], "Newer instruction")

    def test_run_iteration_max_iterations(self):
        """Test iteration limit"""
        state = PipelineState("Test")
        state.iteration_count = 3  # Max iterations
        state.new_instruction = "Instruction"

        with patch('pipeline.Config.MAX_ITERATIONS', 3):
            with self.assertRaises(Exception) as context:
                self.pipeline.run_iteration(state)

            self.assertIn("Maximum iterations", str(context.exception))

    def test_run_iteration_no_instruction(self):
        """Test iteration without instruction"""
        state = PipelineState("Test")
        state.iteration_count = 1
        state.new_instruction = ""

        with self.assertRaises(Exception) as context:
            self.pipeline.run_iteration(state)

            self.assertIn("No instruction available", str(context.exception))


if __name__ == '__main__':
    unittest.main()
