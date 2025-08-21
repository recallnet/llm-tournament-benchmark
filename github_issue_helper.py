"""
GitHub Issue Helper for AFBench Admin UI

This module provides functionality to create GitHub issues with contextual
information from the Streamlit dashboard, including current page state,
selected items, visible data, and table contents.
"""

import json
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st


class AFBenchIssueReporter:
    """Context-aware GitHub issue reporter for AFBench Admin UI."""

    def __init__(self, repo_owner: str = "recallnet", repo_name: str = "beam"):
        self.repo_owner = repo_owner
        self.repo_name = repo_name

    def _safe_session_state_set(self, key: str, value):
        """Safely set session state value, works in both Streamlit and test environments."""
        try:
            # Try dict access first (works in most cases)
            st.session_state[key] = value
        except (TypeError, AttributeError):
            # Fallback to attribute access (real Streamlit)
            try:
                setattr(st.session_state, key, value)
            except AttributeError:
                # Last resort - store in a backup dict
                if not hasattr(self, "_backup_state"):
                    self._backup_state = {}
                self._backup_state[key] = value

    def _safe_session_state_get(self, key: str, default=None):
        """Safely get session state value, works in both Streamlit and test environments."""
        try:
            # Try dict access first (works in both environments usually)
            if hasattr(st.session_state, "get"):
                return st.session_state.get(key, default)
            elif key in st.session_state:
                return st.session_state[key]
            else:
                return default
        except (AttributeError, TypeError):
            # Fallback to attribute access
            try:
                return getattr(st.session_state, key, default)
            except AttributeError:
                # Last resort - check backup dict
                if hasattr(self, "_backup_state"):
                    return self._backup_state.get(key, default)
                return default

    def update_context(self, page: str, **kwargs):
        """Update the current context state."""
        if "issue_context" not in st.session_state:
            self._safe_session_state_set("issue_context", {})

        issue_context = self._safe_session_state_get("issue_context", {})
        issue_context.update({"page": page, "timestamp": datetime.now().isoformat(), **kwargs})
        self._safe_session_state_set("issue_context", issue_context)

    def capture_table_data(self, table_name: str, dataframe: pd.DataFrame):
        """Capture table data for inclusion in issues."""
        if "captured_tables" not in st.session_state:
            self._safe_session_state_set("captured_tables", {})

        # Convert DataFrame to a nice format for GitHub
        # Create markdown table manually to avoid tabulate dependency
        markdown_table = self._dataframe_to_markdown(dataframe)

        captured_tables = self._safe_session_state_get("captured_tables", {})
        captured_tables[table_name] = {
            "columns": list(dataframe.columns),
            "data": dataframe.to_dict("records"),
            "shape": dataframe.shape,
            "markdown": markdown_table,
        }
        self._safe_session_state_set("captured_tables", captured_tables)

    def _dataframe_to_markdown(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to markdown table without tabulate dependency."""
        if df.empty:
            return "| (empty table) |\n|----------------|\n"

        # Create header
        headers = [""] + list(df.columns)  # Add index column
        header_row = "| " + " | ".join(str(h) for h in headers) + " |"
        separator_row = "|" + "|".join("---" for _ in headers) + "|"

        # Create data rows
        data_rows = []
        for idx, row in df.iterrows():
            row_data = [str(idx)] + [str(val) for val in row.values]
            data_row = "| " + " | ".join(row_data) + " |"
            data_rows.append(data_row)

        return "\n".join([header_row, separator_row] + data_rows)

    def capture_json_data(self, data_name: str, json_data: dict[Any, Any]):
        """Capture JSON data for inclusion in issues."""
        if "captured_json" not in st.session_state:
            self._safe_session_state_set("captured_json", {})

        captured_json = self._safe_session_state_get("captured_json", {})
        captured_json[data_name] = json_data
        self._safe_session_state_set("captured_json", captured_json)

    def get_context_path(self) -> str:
        """Generate a hierarchical context path."""
        context = self._safe_session_state_get("issue_context", {})
        path_parts = []

        # Build hierarchical path
        if "page" in context:
            path_parts.append(context["page"])

        # Add specific selections based on page
        page = context.get("page", "")
        if page == "Models":
            if "selected_model" in context:
                path_parts.append(f"Model: {context['selected_model']}")
        elif page == "Judges":
            if "selected_judge" in context:
                path_parts.append(f"Judge: {context['selected_judge']}")
        elif page == "Tournaments":
            if "selected_skill" in context:
                path_parts.append(f"Skill: {context['selected_skill']}")
            if "selected_match" in context:
                path_parts.append(f"Match: {context['selected_match']}")
        elif page == "Skills":
            if "selected_skill" in context:
                path_parts.append(f"Skill: {context['selected_skill']}")
            if "selected_eval" in context:
                path_parts.append(f"Eval: {context['selected_eval']}")

        return " > ".join(path_parts)

    def generate_issue_content(self, issue_title: str = "", issue_description: str = "") -> dict[str, str]:
        """Generate GitHub issue title and body with all contextual data."""

        context = self._safe_session_state_get("issue_context", {})
        tables = self._safe_session_state_get("captured_tables", {})
        json_data = self._safe_session_state_get("captured_json", {})

        # Generate title
        context_path = self.get_context_path()
        if not issue_title:
            # Special handling for Skills page with eval selection
            if context.get("page") == "Skills" and "selected_skill" in context and "selected_eval" in context:
                skill_eval_pair = f"{context['selected_skill']}-{context['selected_eval']}"
                issue_title = f"Issue with eval {skill_eval_pair}: AFBench Admin UI"
            else:
                issue_title = f"Issue from AFBench Admin UI: {context_path}"

        # Generate body
        body_parts = []

        # User description
        if issue_description:
            body_parts.append(f"## Issue Description\n{issue_description}\n")

        # Context information
        body_parts.append("## Context Information")
        body_parts.append(f"- **Page**: {context.get('page', 'Unknown')}")
        body_parts.append(f"- **Path**: {context_path}")
        body_parts.append(f"- **Timestamp**: {context.get('timestamp', 'Unknown')}")

        # Add specific context details
        for key, value in context.items():
            if key not in ["page", "timestamp"] and not key.startswith("_"):
                body_parts.append(f"- **{key.replace('_', ' ').title()}**: {value}")

        body_parts.append("")

        # Include captured table data
        if tables:
            body_parts.append("## Table Data")
            for table_name, table_info in tables.items():
                body_parts.append(f"### {table_name}")
                body_parts.append(f"Shape: {table_info['shape'][0]} rows × {table_info['shape'][1]} columns\n")
                body_parts.append("```")
                body_parts.append(table_info["markdown"])
                body_parts.append("```\n")

        # Include captured JSON data
        if json_data:
            body_parts.append("## JSON Data")
            for data_name, data in json_data.items():
                body_parts.append(f"### {data_name}")
                body_parts.append("```json")
                body_parts.append(json.dumps(data, indent=2))
                body_parts.append("```\n")

        # Add environment info
        body_parts.append("## Environment")
        body_parts.append("- **Source**: AFBench Admin UI")
        body_parts.append("- **Generated**: Automatically via Streamlit dashboard")

        return {"title": issue_title, "body": "\n".join(body_parts)}

    def show_issue_button(self, key: str = "default"):
        """Show a simple 'Open Issue' button that opens GitHub in a new tab."""

        # Generate issue content with current context
        issue_content = self.generate_issue_content()

        # Create GitHub URL with pre-filled data
        import urllib.parse

        title_encoded = urllib.parse.quote(issue_content["title"])
        body_encoded = urllib.parse.quote(issue_content["body"])
        github_url = (
            f"https://github.com/{self.repo_owner}/{self.repo_name}/issues/new?title={title_encoded}&body={body_encoded}"
        )

        # Simple button that opens in new tab
        try:
            columns = st.columns([3, 1])
            if len(columns) == 2:
                col1, col2 = columns
                with col2:
                    st.markdown(
                        f'<a href="{github_url}" target="_blank"><button style="background-color:#ff4444;color:white;border:none;padding:8px 16px;border-radius:4px;cursor:pointer;">🐛 Open Issue</button></a>',
                        unsafe_allow_html=True,
                    )
            else:
                # Fallback for test environment
                st.markdown(
                    f'<a href="{github_url}" target="_blank"><button style="background-color:#ff4444;color:white;border:none;padding:8px 16px;border-radius:4px;cursor:pointer;">🐛 Open Issue</button></a>',
                    unsafe_allow_html=True,
                )
        except (ValueError, TypeError):
            # Fallback for test environment where st.columns might not work properly
            st.markdown(
                f'<a href="{github_url}" target="_blank"><button style="background-color:#ff4444;color:white;border:none;padding:8px 16px;border-radius:4px;cursor:pointer;">🐛 Open Issue</button></a>',
                unsafe_allow_html=True,
            )


# Global instance for easy access
issue_reporter = AFBenchIssueReporter()
