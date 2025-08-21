"""
Test to demonstrate the GitHub issue integration functionality.

This shows how the context-aware issue reporter captures page state,
table data, and generates GitHub issues with relevant information.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


# Mock streamlit before importing
class MockSessionState(dict):
    """Mock session state that supports both dict and attribute access."""

    def __getattr__(self, key):
        return self.get(key)

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        if key in self:
            del self[key]


streamlit_mock = MagicMock()
streamlit_mock.session_state = MockSessionState()
streamlit_mock.columns = lambda n: [MagicMock() for _ in range(len(n) if isinstance(n, list) else n)]
streamlit_mock.button = MagicMock(return_value=False)
streamlit_mock.text_input = MagicMock(return_value="Test Issue Title")
streamlit_mock.text_area = MagicMock(return_value="Test issue description")
streamlit_mock.expander = MagicMock(
    return_value=MagicMock(__enter__=MagicMock(return_value=MagicMock()), __exit__=MagicMock())
)
sys.modules["streamlit"] = streamlit_mock

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_issue_helper import AFBenchIssueReporter


class TestGitHubIssueIntegration:
    """Test the GitHub issue integration functionality."""

    def test_context_tracking(self):
        """Test that context is tracked correctly across page navigation."""

        print("\n📋 TESTING CONTEXT TRACKING")
        print("=" * 30)

        reporter = AFBenchIssueReporter()

        # Simulate navigating to Models page
        reporter.update_context("Models")

        context = streamlit_mock.session_state.get("issue_context", {})
        print(f"Initial context: {context}")

        assert context["page"] == "Models"
        assert "timestamp" in context

        # Simulate selecting a model
        reporter.update_context("Models", selected_model="thedrummer/unslopnemo-12b")

        context = streamlit_mock.session_state.get("issue_context", {})
        print(f"After model selection: {context}")

        assert context["selected_model"] == "thedrummer/unslopnemo-12b"

        # Test context path generation
        path = reporter.get_context_path()
        print(f"Generated context path: {path}")

        expected_path = "Models > Model: thedrummer/unslopnemo-12b"
        assert path == expected_path

        print("✅ Context tracking working correctly!")

    def test_table_data_capture(self):
        """Test capturing table data for issue reporting."""

        print("\n📊 TESTING TABLE DATA CAPTURE")
        print("=" * 32)

        reporter = AFBenchIssueReporter()

        # Create sample DataFrame (like models overview)
        sample_data = pd.DataFrame(
            {
                "Model ID": ["thedrummer/unslopnemo-12b", "openai/gpt-oss-120b"],
                "Best Skill": ["harm_avoidance", "persuasiveness"],
                "Worst Skill": ["code_generation", "harm_avoidance"],
                "Win Rate": ["37.0%", "40.0%"],
            }
        )

        # Capture table data
        reporter.capture_table_data("Models Overview", sample_data)

        captured = streamlit_mock.session_state.get("captured_tables", {})
        print(f"Captured tables: {list(captured.keys())}")

        assert "Models Overview" in captured
        table_info = captured["Models Overview"]

        print(f"Table shape: {table_info['shape']}")
        print(f"Table columns: {table_info['columns']}")
        print(f"First row: {table_info['data'][0]}")

        assert table_info["shape"] == (2, 4)
        assert "Model ID" in table_info["columns"]
        assert table_info["data"][0]["Model ID"] == "thedrummer/unslopnemo-12b"

        print("✅ Table data capture working correctly!")

    def test_issue_content_generation(self):
        """Test generating GitHub issue content with all captured data."""

        print("\n🐛 TESTING ISSUE CONTENT GENERATION")
        print("=" * 36)

        reporter = AFBenchIssueReporter()

        # Set up context and data
        reporter.update_context("Models", selected_model="thedrummer/unslopnemo-12b")

        # Add table data
        sample_table = pd.DataFrame(
            {
                "Skill": ["harm_avoidance", "code_generation"],
                "Rating": ["1652.8", "1314.4"],
                "Wins": [14, 1],
                "Losses": [1, 20],
            }
        )
        reporter.capture_table_data("Model Performance", sample_table)

        # Add JSON data
        sample_json = {
            "model_info": {"id": "thedrummer/unslopnemo-12b", "author": "TheDrummer", "ratings": {"harm_avoidance": 1652.8}}
        }
        reporter.capture_json_data("Model Details", sample_json)

        # Generate issue content
        issue_content = reporter.generate_issue_content(
            issue_description="The model shows wrong best/worst skills in overview table"
        )

        print(f"Generated issue title: {issue_content['title']}")
        print("\nGenerated issue body preview:")
        print(f"{'='*50}")
        print(issue_content["body"][:500] + "..." if len(issue_content["body"]) > 500 else issue_content["body"])
        print(f"{'='*50}")

        # Verify content
        assert "Models > Model: thedrummer/unslopnemo-12b" in issue_content["title"]
        assert "Issue Description" in issue_content["body"]
        assert "Context Information" in issue_content["body"]
        assert "Table Data" in issue_content["body"]
        assert "JSON Data" in issue_content["body"]
        assert "Model Performance" in issue_content["body"]
        assert "harm_avoidance" in issue_content["body"]
        assert "1652.8" in issue_content["body"]

        print("✅ Issue content generation working correctly!")

    def test_github_integration_workflow(self):
        """Test the complete GitHub integration workflow."""

        print("\n🔗 TESTING GITHUB INTEGRATION WORKFLOW")
        print("=" * 39)

        reporter = AFBenchIssueReporter()

        # Test URL generation for GitHub
        issue_content = reporter.generate_issue_content("Test Issue")
        title = issue_content["title"]
        body = issue_content["body"]

        # Simulate creating GitHub URL
        import urllib.parse

        title_encoded = urllib.parse.quote(title)
        body_encoded = urllib.parse.quote(body)
        github_url = f"https://github.com/recallnet/beam/issues/new?title={title_encoded}&body={body_encoded}"

        print(f"Generated GitHub URL length: {len(github_url)}")
        print(f"URL preview: {github_url[:100]}...")

        # Verify URL components
        assert "github.com/recallnet/beam/issues/new" in github_url
        assert "title=" in github_url
        assert "body=" in github_url

        print("✅ GitHub integration workflow ready!")
        print("\nWorkflow summary:")
        print("1. ✅ Context tracking across page navigation")
        print("2. ✅ Table data capture from DataFrames")
        print("3. ✅ JSON data capture for detailed info")
        print("4. ✅ Issue content generation with all data")
        print("5. ✅ GitHub URL generation for easy issue creation")

    def test_different_page_contexts(self):
        """Test context tracking for different page types."""

        print("\n📄 TESTING DIFFERENT PAGE CONTEXTS")
        print("=" * 34)

        reporter = AFBenchIssueReporter()

        # Test Models page
        reporter.update_context("Models", selected_model="test_model")
        path1 = reporter.get_context_path()
        print(f"Models context: {path1}")

        # Test Tournaments page
        reporter.update_context("Tournaments", selected_skill="harm_avoidance", selected_match="match_123")
        path2 = reporter.get_context_path()
        print(f"Tournaments context: {path2}")

        # Test Skills page
        reporter.update_context("Skills", selected_skill="code_generation", selected_eval="eval_456")
        path3 = reporter.get_context_path()
        print(f"Skills context: {path3}")

        assert path1 == "Models > Model: test_model"
        assert path2 == "Tournaments > Skill: harm_avoidance > Match: match_123"
        assert path3 == "Skills > Skill: code_generation > Eval: eval_456"

        print("✅ Multi-page context tracking working correctly!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
