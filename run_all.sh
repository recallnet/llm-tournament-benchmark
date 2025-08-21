#!/bin/bash

# AFBench Quick Profile Runner
# Runs the complete AFBench pipeline with the quick profile

# Set log file with timestamp
LOG_FILE="afbench_run_$(date +%Y%m%d_%H%M%S).log"

echo "🚀 Starting AFBench pipeline with quick profile..."
echo "📝 Output will be logged to: $LOG_FILE"
echo ""

# Run the pipeline with verbose output, piping to log file
snakemake --unlock && snakemake afbench --profile profiles/quick --verbose > "$LOG_FILE" 2>&1

# Check if pipeline completed successfully
if [ $? -eq 0 ]; then
    echo "🎉 Congrats! AFBench pipeline completed successfully!"
else
    echo "❌ Pipeline failed. Check the log file for details."
fi

echo "📋 Log file written to: $LOG_FILE"