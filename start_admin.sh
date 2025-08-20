#!/bin/bash
set -e

echo "🚀 Starting AFBench Admin UI..."
echo "📍 Will open at: http://localhost:8501"
echo "🛑 Press Ctrl+C to stop"

# Set working directory explicitly
cd /Users/andrewhill/Coding/afbench

# Run streamlit with explicit config to avoid directory issues
STREAMLIT_SERVER_FILE_WATCHER_TYPE=auto \
STREAMLIT_SERVER_RUN_ON_SAVE=true \
STREAMLIT_GLOBAL_DEVELOPMENT_MODE=false \
streamlit run admin_ui.py --server.port=8501