#!/bin/bash

while true; do
  # Run qstat to check for running or queued jobs
  job_output=$(qstat)

  # Count the number of words in the output
  word_count=$(echo "$job_output" | wc -w)

  # Check if the word count is more than 10
  if [ "$word_count" -gt 10 ]; then
    echo "Job is running"
  else
    echo "No jobs running. Restarting job..."
    
    # Kill all jobs submitted by qsub
    pkill -9 qsub

    # Delete all queued jobs
    qdel all

    # Submit a new job and capture the job ID
    JOB_ID=$(qsub -l walltime=24:00:00 -d . script.sh)

    # Print the new job ID
    echo "Job restarted with ID: $JOB_ID"
  fi

  # Wait for 10 seconds before checking again
  sleep 360
done







