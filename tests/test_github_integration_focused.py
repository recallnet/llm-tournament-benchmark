"""
Focused tests for GitHub issue integration to ensure it works correctly.

These tests use better mocking and focus on core functionality.
"""

import sys
import urllib.parse
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

from github_issue_helper import AFBenchIssueReporter


class TestGitHubIntegrationCore:
    """Test core GitHub integration functionality."""

    def test_url_generation_basic(self):
        """Test basic URL generation works correctly."""

        print("\n🔗 TESTING BASIC URL GENERATION")
        print("=" * 31)

        reporter = AFBenchIssueReporter()

        # Mock streamlit session state as a proper object
        class MockSessionState:
            def __init__(self):
                self.issue_context = {"page": "Models", "selected_model": "test_model"}
                self.captured_tables = {
                    "Test Table": {
                        "columns": ["A", "B"],
                        "data": [{"A": 1, "B": 2}],
                        "shape": (1, 2),
                        "markdown": "| A | B |\n|---|---|\n| 1 | 2 |",
                    }
                }

            def get(self, key, default=None):
                return getattr(self, key, default)

        # Mock streamlit
        with patch("github_issue_helper.st") as mock_st:
            mock_st.session_state = MockSessionState()

            # Generate issue content
            content = reporter.generate_issue_content()

            print(f"Title: {content['title']}")
            print(f"Body length: {len(content['body'])}")

            # Create URL
            title_encoded = urllib.parse.quote(content["title"])
            body_encoded = urllib.parse.quote(content["body"])
            github_url = f"https://github.com/recallnet/beam/issues/new?title={title_encoded}&body={body_encoded}"

            print(f"URL length: {len(github_url)}")

            # Verify URL structure
            assert github_url.startswith(
                "https://github.com/recallnet/beam/issues/new?"
            )
            assert "title=" in github_url
            assert "body=" in github_url
            assert "Models" in content["title"]
            assert "test_model" in content["title"]
            assert "Test Table" in content["body"]

            print("✅ Basic URL generation works correctly")

    def test_markdown_generation(self):
        """Test DataFrame to markdown conversion."""

        print("\n📋 TESTING MARKDOWN GENERATION")
        print("=" * 29)

        reporter = AFBenchIssueReporter()

        # Test with normal data
        df = pd.DataFrame(
            {"Model": ["model_1", "model_2"], "Score": [1600.5, 1450.2], "Rank": [1, 2]}
        )

        markdown = reporter._dataframe_to_markdown(df)
        print(f"Generated markdown:\n{markdown}")

        # Verify markdown structure
        lines = markdown.split("\n")
        assert len(lines) >= 4, "Should have header, separator, and data rows"
        assert "|" in lines[0], "Should be proper table format"
        assert "Model" in lines[0], "Should include column headers"
        assert "model_1" in markdown, "Should include data values"
        assert "1600.5" in markdown, "Should include numeric values"

        # Test with empty DataFrame
        empty_df = pd.DataFrame()
        empty_markdown = reporter._dataframe_to_markdown(empty_df)
        print(f"Empty DataFrame markdown: {empty_markdown}")
        assert "empty table" in empty_markdown, "Should handle empty DataFrames"

        print("✅ Markdown generation works correctly")

    def test_context_path_generation(self):
        """Test context path generation for different scenarios."""

        print("\n🗺️ TESTING CONTEXT PATH GENERATION")
        print("=" * 33)

        reporter = AFBenchIssueReporter()

        test_cases = [
            ({}, ""),
            ({"page": "Models"}, "Models"),
            (
                {"page": "Models", "selected_model": "test_model"},
                "Models > Model: test_model",
            ),
            (
                {"page": "Judges", "selected_judge": "test_judge"},
                "Judges > Judge: test_judge",
            ),
            (
                {
                    "page": "Tournaments",
                    "selected_skill": "skill_1",
                    "selected_match": "match_1",
                },
                "Tournaments > Skill: skill_1 > Match: match_1",
            ),
        ]

        with patch("github_issue_helper.st") as mock_st:
            for i, (context, expected_path) in enumerate(test_cases):
                mock_st.session_state = Mock()
                mock_st.session_state.get = lambda key, default: (
                    context if key == "issue_context" else default
                )

                path = reporter.get_context_path()
                print(f"Test {i+1}: {context} -> '{path}'")
                assert (
                    path == expected_path
                ), f"Expected '{expected_path}', got '{path}'"

        print("✅ Context path generation works correctly")

    def test_special_characters_encoding(self):
        """Test that special characters are properly handled."""

        print("\n🔒 TESTING SPECIAL CHARACTER ENCODING")
        print("=" * 37)

        reporter = AFBenchIssueReporter()

        # Test data with special characters
        special_df = pd.DataFrame(
            {
                "Model": ["test/model", "model with spaces", 'model"quotes"'],
                "Description": [
                    "Contains & and <tags>",
                    "Normal text",
                    "Special: @#$%",
                ],
            }
        )

        class MockSessionState:
            def __init__(self):
                self.issue_context = {
                    "page": "Models",
                    "selected_model": "dangerous/model&name",
                }
                self.captured_tables = {
                    "Special Chars": {
                        "columns": list(special_df.columns),
                        "data": special_df.to_dict("records"),
                        "shape": special_df.shape,
                        "markdown": reporter._dataframe_to_markdown(special_df),
                    }
                }

            def get(self, key, default=None):
                return getattr(self, key, default)

        with patch("github_issue_helper.st") as mock_st:
            mock_st.session_state = MockSessionState()

            # Generate content
            content = reporter.generate_issue_content()

            # Create URL with encoding
            title_encoded = urllib.parse.quote(content["title"])
            body_encoded = urllib.parse.quote(content["body"])
            github_url = f"https://github.com/recallnet/beam/issues/new?title={title_encoded}&body={body_encoded}"

            print(f"URL length: {len(github_url)}")

            # Verify dangerous characters are encoded
            assert "<tags>" not in github_url, "Angle brackets should be encoded"
            assert (
                " " not in github_url.split("?", 1)[1]
            ), "Spaces should be encoded in parameters"

            # Verify content is preserved when decoded
            decoded_title = urllib.parse.unquote(title_encoded)
            decoded_body = urllib.parse.unquote(body_encoded)

            assert (
                "dangerous/model&name" in decoded_title
            ), "Model name should be preserved"
            assert (
                "Contains & and <tags>" in decoded_body
            ), "Special chars should be preserved in body"

            print("✅ Special characters encoded safely")

    def test_performance_with_large_data(self):
        """Test performance with reasonably large datasets."""

        print("\n⚡ TESTING PERFORMANCE WITH LARGE DATA")
        print("=" * 37)

        import time

        reporter = AFBenchIssueReporter()

        # Create moderately large DataFrame (100 rows)
        large_df = pd.DataFrame(
            {
                "ID": range(100),
                "Model": [f"model_{i}" for i in range(100)],
                "Score": [1500 + i * 2.5 for i in range(100)],
                "Description": [
                    f"Description for model {i} with some additional text"
                    for i in range(100)
                ],
            }
        )

        # Time markdown generation
        start_time = time.time()
        markdown = reporter._dataframe_to_markdown(large_df)
        markdown_time = time.time() - start_time

        print(f"Markdown generation time (100 rows): {markdown_time:.4f} seconds")
        print(f"Generated markdown length: {len(markdown)} characters")

        # Time full issue generation
        class MockSessionState:
            def __init__(self):
                self.issue_context = {"page": "Models", "selected_model": "test_model"}
                self.captured_tables = {
                    "Large Table": {
                        "columns": list(large_df.columns),
                        "data": large_df.to_dict("records"),
                        "shape": large_df.shape,
                        "markdown": markdown,
                    }
                }

            def get(self, key, default=None):
                return getattr(self, key, default)

        with patch("github_issue_helper.st") as mock_st:
            mock_st.session_state = MockSessionState()

            start_time = time.time()
            content = reporter.generate_issue_content()
            generation_time = time.time() - start_time

            print(f"Issue content generation time: {generation_time:.4f} seconds")
            print(f"Issue body length: {len(content['body'])} characters")

            # Performance should be reasonable
            assert (
                markdown_time < 0.5
            ), f"Markdown generation too slow: {markdown_time:.4f}s"
            assert (
                generation_time < 0.1
            ), f"Issue generation too slow: {generation_time:.4f}s"

        print("✅ Performance is acceptable for large datasets")

    def test_issue_button_integration(self):
        """Test that the issue button generates correct HTML."""

        print("\n🔲 TESTING ISSUE BUTTON INTEGRATION")
        print("=" * 34)

        reporter = AFBenchIssueReporter()

        class MockSessionState:
            def __init__(self):
                self.issue_context = {"page": "Models", "selected_model": "test_model"}
                self.captured_tables = {}

            def get(self, key, default=None):
                return getattr(self, key, default)

        # Mock streamlit markdown call
        markdown_calls = []

        with patch("github_issue_helper.st") as mock_st:
            mock_st.session_state = MockSessionState()

            # Create context manager mock columns
            def create_column_mock():
                col_mock = Mock()
                col_mock.__enter__ = Mock(return_value=col_mock)
                col_mock.__exit__ = Mock(return_value=None)
                return col_mock

            mock_st.columns = lambda n: [
                create_column_mock()
                for _ in range(len(n) if isinstance(n, list) else n)
            ]
            mock_st.markdown = lambda content, **kwargs: markdown_calls.append(content)

            # Generate issue button
            reporter.show_issue_button("test")

            # Verify button was generated
            assert len(markdown_calls) > 0, "Should generate button HTML"

            button_html = markdown_calls[-1]
            print(f"Button HTML preview: {str(button_html)[:100]}...")

            # Verify HTML structure
            assert "<a href=" in str(button_html), "Should contain anchor tag"
            assert 'target="_blank"' in str(button_html), "Should open in new tab"
            assert "github.com/recallnet/beam/issues/new" in str(
                button_html
            ), "Should link to GitHub"
            assert "Open Issue" in str(button_html), "Should contain button text"

            print("✅ Issue button generates correct HTML")

    def test_error_handling(self):
        """Test error handling for various edge cases."""

        print("\n🚨 TESTING ERROR HANDLING")
        print("=" * 24)

        reporter = AFBenchIssueReporter()

        # Test with completely empty session state
        with patch("github_issue_helper.st") as mock_st:
            mock_st.session_state = Mock()
            mock_st.session_state.get = lambda key, default: default

            try:
                path = reporter.get_context_path()
                content = reporter.generate_issue_content()
                print(f"Empty state - Path: '{path}', Title: '{content['title']}'")
                assert path == "", "Empty state should return empty path"
                print("✅ Handles empty session state gracefully")
            except Exception as e:
                print(f"❌ Failed with empty state: {e}")
                raise

        # Test with None values in DataFrame
        try:
            none_df = pd.DataFrame({"A": [1, None, 3], "B": [None, "text", None]})
            markdown = reporter._dataframe_to_markdown(none_df)
            assert "None" in markdown, "Should handle None values"
            print("✅ Handles None values in DataFrames")
        except Exception as e:
            print(f"❌ Failed with None values: {e}")
            raise

        print("✅ Error handling works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
