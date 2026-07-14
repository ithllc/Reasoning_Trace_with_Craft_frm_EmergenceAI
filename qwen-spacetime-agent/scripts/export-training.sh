#!/usr/bin/env bash
set -euo pipefail

database="${SPACETIME_DATABASE:-qwen-agent-jobs}"
server="${SPACETIME_SERVER:-local}"
output="${1:-data/training-export.txt}"

mkdir -p "$(dirname "$output")"
spacetime sql --server "$server" "$database" \
  "SELECT j.id, j.prompt, j.final_answer, m.sequence, m.role, m.content, m.tool_name, m.tool_call_id FROM job j JOIN message m ON j.id = m.job_id WHERE j.status = 'completed' ORDER BY j.id, m.sequence" \
  > "$output"
echo "Exported completed trajectories to $output"
