#!/bin/bash
set -e

echo "🚀 Starting AFBench Admin UI..."
echo "📍 Navigate to: http://localhost:8501"
echo "🛑 Press Ctrl+C to stop"

# Run from project root to avoid directory issues
streamlit run admin_ui.py
