"""
Comprehensive tests for GitHub issue integration to ensure no bugs.

These tests verify:
1. URL generation works correctly and safely
2. Context tracking doesn't break page functionality
3. Table data capture doesn't affect performance
4. Edge cases and error handling
5. Integration with actual admin UI pages
"""

import sys
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest


# Mock streamlit completely
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
streamlit_mock.columns = lambda n: [
    MagicMock() for _ in range(len(n) if isinstance(n, list) else n)
]
streamlit_mock.markdown = MagicMock()
streamlit_mock.header = MagicMock()
streamlit_mock.dataframe = MagicMock()
streamlit_mock.selectbox = MagicMock(return_value="test_model")
streamlit_mock.subheader = MagicMock()
sys.modules["streamlit"] = streamlit_mock

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent))

import admin_ui
from github_issue_helper import AFBenchIssueReporter


class TestGitHubIssueIntegrationSafety:
    """Test that GitHub issue integration is safe and doesn't break anything."""

    def test_url_encoding_safety(self):
        """Test that special characters in data are properly URL encoded."""

        print("\n🔒 TESTING URL ENCODING SAFETY")
        print("=" * 32)

        reporter = AFBenchIssueReporter()

        # Create data with special characters that could break URLs
        dangerous_data = pd.DataFrame(
            {
                "Model": ["test/model&name", "model with spaces", 'model"with"quotes'],
                "Skill": [
                    '<script>alert("xss")</script>',
                    "skill & other",
                    "normal_skill",
                ],
                "Rating": [1500.0, 1600.0, 1700.0],
                "Description": [
                    'Contains "quotes" and \n newlines \t tabs',
                    "Unicode: café résumé naïve",
                    "Special chars: @#$%^&*()_+-=[]{}|;:,.<>?",
                ],
            }
        )

        # Mock session state with dangerous data
        streamlit_mock.session_state.clear()
        streamlit_mock.session_state.update(
            {
                "issue_context": {
                    "page": "Models",
                    "selected_model": "dangerous/model&name",
                    "description": 'Contains <script>alert("hack")</script> and other bad stuff',
                },
                "captured_tables": {
                    "Dangerous Data": {
                        "columns": list(dangerous_data.columns),
                        "data": dangerous_data.to_dict("records"),
                        "shape": dangerous_data.shape,
                        "markdown": reporter._dataframe_to_markdown(dangerous_data),
                    }
                },
            }
        )

        # Generate issue content
        issue_content = reporter.generate_issue_content()

        print(f"Title contains dangerous chars: {'<script>' in issue_content['title']}")
        print(f"Body contains dangerous chars: {'<script>' in issue_content['body']}")

        # Create GitHub URL
        title_encoded = urllib.parse.quote(issue_content["title"])
        body_encoded = urllib.parse.quote(issue_content["body"])
        github_url = f"https://github.com/recallnet/beam/issues/new?title={title_encoded}&body={body_encoded}"

        print(f"URL length: {len(github_url)}")
        print(
            f"URL contains unencoded chars: {'&' in github_url.split('?')[1] and 'body=' not in github_url.split('&')[0]}"
        )

        # Verify URL is properly encoded
        assert (
            "<script>" not in github_url
        ), "Dangerous script tags should be URL encoded"
        assert "alert(" not in github_url, "JavaScript should be URL encoded"
        assert github_url.startswith(
            "https://github.com/"
        ), "URL should be properly formed"
        assert "title=" in github_url, "URL should contain title parameter"
        assert "body=" in github_url, "URL should contain body parameter"

        # Verify content is preserved after encoding/decoding
        decoded_title = urllib.parse.unquote(title_encoded)
        decoded_body = urllib.parse.unquote(body_encoded)

        assert "dangerous/model&name" in decoded_title, "Model name should be preserved"
        assert "café résumé naïve" in decoded_body, "Unicode should be preserved"

        print("✅ URL encoding safety verified")

    def test_context_tracking_doesnt_break_pages(self):
        """Test that context tracking doesn't interfere with normal page operation."""

        print("\n🔄 TESTING CONTEXT TRACKING SAFETY")
        print("=" * 35)

        # Reset session state
        streamlit_mock.session_state.clear()

        # Create realistic test data
        test_data = {
            "models": {
                "models": [
                    {
                        "id": "test_model",
                        "author": "Test",
                        "context_window": 32768,
                        "endpoint": "test",
                    }
                ]
            },
            "judges": {
                "judges": [
                    {"id": "test_judge", "author": "Test", "context_window": 64000}
                ]
            },
            "tournaments": {
                "test_skill": {
                    "model_rankings": [
                        {"model_id": "test_model", "wins": 5, "losses": 2, "rank": 1}
                    ],
                    "match_history": [
                        {"judges": ["test_judge"], "match_id": "match_1"}
                    ],
                }
            },
            "ratings": {
                "test_skill": {
                    "model_ratings": {"test_model": {"mu": 1600.0, "sigma": 50.0}}
                }
            },
        }

        # Test Models page
        print("Testing Models page...")
        try:
            admin_ui.show_models_page(test_data)
            models_context = streamlit_mock.session_state.get("issue_context", {})
            print(f"  Models context: {models_context}")
            assert (
                models_context.get("page") == "Models"
            ), "Models page context should be set"
            print("  ✅ Models page works with context tracking")
        except Exception as e:
            print(f"  ❌ Models page failed: {e}")
            raise

        # Test Judges page
        print("Testing Judges page...")
        try:
            admin_ui.show_judges_page(test_data)
            judges_context = streamlit_mock.session_state.get("issue_context", {})
            print(f"  Judges context: {judges_context}")
            assert (
                judges_context.get("page") == "Judges"
            ), "Judges page context should be set"
            print("  ✅ Judges page works with context tracking")
        except Exception as e:
            print(f"  ❌ Judges page failed: {e}")
            raise

        print("✅ Context tracking doesn't break page functionality")

    def test_table_capture_performance_impact(self):
        """Test that table data capture doesn't significantly impact performance."""

        print("\n⚡ TESTING TABLE CAPTURE PERFORMANCE")
        print("=" * 36)

        reporter = AFBenchIssueReporter()
        streamlit_mock.session_state.clear()

        # Create large DataFrame to test performance
        import time

        large_data = pd.DataFrame(
            {
                "ID": range(1000),
                "Name": [f"item_{i}" for i in range(1000)],
                "Value": [i * 1.5 for i in range(1000)],
                "Description": [
                    f"Description for item {i} with some text" for i in range(1000)
                ],
            }
        )

        # Time the capture operation
        start_time = time.time()
        reporter.capture_table_data("Large Test Table", large_data)
        capture_time = time.time() - start_time

        print(f"Time to capture 1000-row table: {capture_time:.4f} seconds")

        # Verify data was captured correctly
        captured = streamlit_mock.session_state.get("captured_tables", {})
        assert "Large Test Table" in captured, "Large table should be captured"

        table_info = captured["Large Test Table"]
        assert table_info["shape"] == (1000, 4), "Table shape should be preserved"
        assert len(table_info["data"]) == 1000, "All data should be captured"

        # Test markdown generation performance
        start_time = time.time()
        markdown = reporter._dataframe_to_markdown(
            large_data.head(10)
        )  # Only first 10 rows for markdown
        markdown_time = time.time() - start_time

        print(f"Time to generate markdown for 10 rows: {markdown_time:.4f} seconds")
        print(f"Markdown length: {len(markdown)} characters")

        # Performance should be reasonable (less than 1 second for these operations)
        assert capture_time < 1.0, f"Table capture took too long: {capture_time:.4f}s"
        assert (
            markdown_time < 0.1
        ), f"Markdown generation took too long: {markdown_time:.4f}s"

        print("✅ Table capture performance is acceptable")

    def test_edge_cases_and_error_handling(self):
        """Test edge cases and error handling in GitHub issue integration."""

        print("\n🚨 TESTING EDGE CASES AND ERROR HANDLING")
        print("=" * 41)

        reporter = AFBenchIssueReporter()

        # Test with empty session state
        streamlit_mock.session_state.clear()

        # Should not crash with empty state
        try:
            path = reporter.get_context_path()
            print(f"Empty context path: '{path}'")
            assert path == "", "Empty context should return empty path"
            print("  ✅ Handles empty context gracefully")
        except Exception as e:
            print(f"  ❌ Failed on empty context: {e}")
            raise

        # Test with empty DataFrame
        try:
            empty_df = pd.DataFrame()
            markdown = reporter._dataframe_to_markdown(empty_df)
            print(f"Empty DataFrame markdown: '{markdown[:50]}...'")
            assert "empty table" in markdown, "Should handle empty DataFrames"
            print("  ✅ Handles empty DataFrames gracefully")
        except Exception as e:
            print(f"  ❌ Failed on empty DataFrame: {e}")
            raise

        # Test with None values in data
        try:
            none_data = pd.DataFrame(
                {"A": [1, None, 3], "B": [None, "text", None], "C": [1.5, None, 2.5]}
            )
            markdown = reporter._dataframe_to_markdown(none_data)
            print(f"DataFrame with None values handled: {'None' in markdown}")
            assert "None" in markdown, "Should preserve None values as strings"
            print("  ✅ Handles None values gracefully")
        except Exception as e:
            print(f"  ❌ Failed with None values: {e}")
            raise

        # Test with very long strings (URL length limits)
        try:
            very_long_string = "A" * 5000  # Very long string
            issue_content = reporter.generate_issue_content(
                issue_title="Test with very long content",
                issue_description=very_long_string,
            )

            title_encoded = urllib.parse.quote(issue_content["title"])
            body_encoded = urllib.parse.quote(issue_content["body"])
            github_url = f"https://github.com/recallnet/beam/issues/new?title={title_encoded}&body={body_encoded}"

            print(f"URL length with long content: {len(github_url)}")
            print(f"URL is valid: {github_url.startswith('https://github.com/')}")

            # GitHub has URL length limits, but encoding should not crash
            assert len(github_url) > 100, "URL should contain the encoded content"
            print("  ✅ Handles very long content without crashing")
        except Exception as e:
            print(f"  ❌ Failed with long content: {e}")
            raise

        print("✅ All edge cases handled properly")

    def test_multiple_page_navigation(self):
        """Test context tracking across multiple page navigations."""

        print("\n🗺️ TESTING MULTIPLE PAGE NAVIGATION")
        print("=" * 34)

        reporter = AFBenchIssueReporter()
        streamlit_mock.session_state.clear()

        # Simulate navigating through different pages
        navigation_sequence = [
            ("Models", {"selected_model": "model_1"}),
            ("Judges", {"selected_judge": "judge_1"}),
            ("Skills", {"selected_skill": "skill_1", "selected_eval": "eval_1"}),
            ("Tournaments", {"selected_skill": "skill_2", "selected_match": "match_1"}),
            ("Models", {"selected_model": "model_2"}),  # Back to Models
        ]

        for i, (page, context_data) in enumerate(navigation_sequence):
            print(f"Step {i+1}: Navigating to {page}")

            # Update context
            reporter.update_context(page, **context_data)

            # Check context path
            path = reporter.get_context_path()
            print(f"  Context path: {path}")

            # Verify page is correctly set
            current_context = streamlit_mock.session_state.get("issue_context", {})
            assert current_context.get("page") == page, f"Page should be {page}"

            # Verify specific context data
            for key, value in context_data.items():
                assert current_context.get(key) == value, f"{key} should be {value}"

            # Generate issue content and verify it contains current context
            issue_content = reporter.generate_issue_content()
            assert (
                page in issue_content["title"]
            ), f"Title should contain page name {page}"

            print(f"  ✅ Step {i+1} navigation successful")

        print("✅ Multi-page navigation tracking works correctly")

    def test_concurrent_table_captures(self):
        """Test that multiple table captures don't interfere with each other."""

        print("\n📊 TESTING CONCURRENT TABLE CAPTURES")
        print("=" * 36)

        reporter = AFBenchIssueReporter()
        streamlit_mock.session_state.clear()

        # Create multiple different tables
        table1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        table2 = pd.DataFrame(
            {"X": [10, 20, 30], "Y": ["a", "b", "c"], "Z": [1.1, 2.2, 3.3]}
        )
        table3 = pd.DataFrame({"Model": ["m1", "m2"], "Score": [100, 200]})

        # Capture all tables
        reporter.capture_table_data("Table One", table1)
        reporter.capture_table_data("Table Two", table2)
        reporter.capture_table_data("Table Three", table3)

        # Verify all tables are captured correctly
        captured = streamlit_mock.session_state.get("captured_tables", {})

        print(f"Number of captured tables: {len(captured)}")
        assert len(captured) == 3, "Should capture all three tables"

        # Verify each table individually
        assert "Table One" in captured
        assert "Table Two" in captured
        assert "Table Three" in captured

        # Verify table data integrity
        assert captured["Table One"]["shape"] == (2, 2)
        assert captured["Table Two"]["shape"] == (3, 3)
        assert captured["Table Three"]["shape"] == (2, 2)

        # Verify data content
        assert captured["Table One"]["data"][0]["A"] == 1
        assert captured["Table Two"]["data"][0]["Y"] == "a"
        assert captured["Table Three"]["data"][1]["Score"] == 200

        # Generate issue content with all tables
        issue_content = reporter.generate_issue_content()

        # Verify all tables are in the issue body
        assert "Table One" in issue_content["body"]
        assert "Table Two" in issue_content["body"]
        assert "Table Three" in issue_content["body"]

        print(f"Issue body length: {len(issue_content['body'])}")
        print("✅ All tables captured and included correctly")

    def test_url_length_limits(self):
        """Test behavior with very long URLs that might hit browser limits."""

        print("\n📏 TESTING URL LENGTH LIMITS")
        print("=" * 28)

        reporter = AFBenchIssueReporter()

        # Create scenario that generates very long URL
        huge_table = pd.DataFrame(
            {
                "Very Long Column Name With Lots Of Text": [
                    f"Very long value {i} with lots of descriptive text that goes on and on"
                    for i in range(50)
                ],
                "Another Very Long Column Name": [
                    f"More long text for row {i} with additional descriptive content"
                    for i in range(50)
                ],
                "Third Column With Even Longer Name And More Content": [
                    f"Even more verbose text for entry {i}" for i in range(50)
                ],
            }
        )

        streamlit_mock.session_state.clear()
        streamlit_mock.session_state.update(
            {
                "issue_context": {
                    "page": "Models",
                    "selected_model": "very_long_model_name_that_contains_lots_of_descriptive_information",
                    "additional_context": "A very long description that contains a lot of contextual information about the current state",
                },
                "captured_tables": {
                    "Huge Data Table With Very Long Name": {
                        "columns": list(huge_table.columns),
                        "data": huge_table.to_dict("records"),
                        "shape": huge_table.shape,
                        "markdown": reporter._dataframe_to_markdown(
                            huge_table.head(5)
                        ),  # Limit for URL
                    }
                },
            }
        )

        # Generate issue content
        issue_content = reporter.generate_issue_content(
            issue_title="Very Long Issue Title With Lots Of Descriptive Information About The Problem",
            issue_description="A very long description that goes into great detail about the specific issue, including context, steps to reproduce, expected behavior, actual behavior, and any other relevant information that might be helpful for debugging.",
        )

        # Create URL
        title_encoded = urllib.parse.quote(issue_content["title"])
        body_encoded = urllib.parse.quote(issue_content["body"])
        github_url = f"https://github.com/recallnet/beam/issues/new?title={title_encoded}&body={body_encoded}"

        url_length = len(github_url)
        print(f"Generated URL length: {url_length} characters")

        # Check if URL exceeds common browser limits
        # Most browsers support URLs up to 2048 characters, some support much more
        if url_length > 2048:
            print("⚠️  URL exceeds 2048 character limit - may not work in all browsers")
        else:
            print("✅ URL length is within safe browser limits")

        if url_length > 8192:
            print(
                "⚠️  URL exceeds 8192 character limit - likely to fail in most browsers"
            )

        # Verify URL is still properly formed despite length
        assert github_url.startswith("https://github.com/recallnet/beam/issues/new?")
        assert "title=" in github_url
        assert "body=" in github_url

        print(f"✅ URL structure remains valid despite length: {url_length} chars")

        # Suggest truncation strategy for very long URLs
        if url_length > 4000:
            print("💡 Consider implementing URL truncation for very large datasets")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
