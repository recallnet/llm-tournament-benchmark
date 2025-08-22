#!/bin/bash

# Pipeline monitoring script - runs Claude Code to monitor production pipeline 24 times over 12 hours

COMMAND="Your job is to run 'snakemake --profile profiles/production -j5 > pipeline_run.log 2>&1 &'. It may already be running, so check the end of that file (exactly pipeline_run.log, never create or use a different log file). If it looks like it is running, sleep for 5m and check back, see if it still looks like it is running. You can also evaluate data/production updates to see. If it is not running, you need to run it again. Always in the background, always using pipeline_run.log. If it is running but looks like it is flailing, you are to restart it after you think you've fixed whatever issue caused it to flail. If it is not running anymore and quit for a known reason, try to fix the reason and restart it. Basically, do what you can to get it running again until the full production pipeline is finished. After you cleanup, address, or simply check on it running, then you are done, we can let it run in the background. Make sure any background processes you start use nohup or disown so they don't quit when you exit."

echo "Starting pipeline monitoring script - will run 24 cycles over 12 hours"
echo "Started at: $(date)"

for i in {1..24}; do
    echo ""
    echo "=== Cycle $i/24 - $(date) ==="
    
    # Send command to Claude Code
    claude --dangerously-skip-permissions -p "$COMMAND"
    
    # Sleep for 30 minutes unless it's the last iteration
    if [ $i -lt 24 ]; then
        echo "Sleeping for 30 minutes before next check..."
        sleep 1800  # 30 minutes = 1800 seconds
    fi
done

echo ""
echo "=== Monitoring complete - $(date) ==="
echo "Pipeline monitoring script finished after 24 cycles"