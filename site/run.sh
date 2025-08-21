#!/bin/bash

# AFBench Admin UI Runner
# Configurable data directory support

# Default to quick profile data
export AFBENCH_ADMIN_DATA_DIR="${AFBENCH_ADMIN_DATA_DIR:-data/quick}"

echo "🚀 Starting AFBench Admin UI..."
echo "📊 Using data directory: $AFBENCH_ADMIN_DATA_DIR"
echo "🌐 Open http://localhost:8501 in your browser"
echo ""
echo "💡 To use different data directories:"
echo "   Production: AFBENCH_ADMIN_DATA_DIR=data/production ./run.sh"
echo "   Legacy:     AFBENCH_ADMIN_DATA_DIR=data ./run.sh"
echo ""

# Change to parent directory to access the data paths correctly
cd ..

# Run streamlit with the admin UI
streamlit run admin_ui.py --server.port 8501 --server.address localhost