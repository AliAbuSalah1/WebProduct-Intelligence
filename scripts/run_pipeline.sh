#!/usr/bin/env bash
# Run the pipeline from anywhere; extra arguments are passed through.
#   ./scripts/run_pipeline.sh --details
# Example cron entry (every day at 06:00, logging to data/run.log):
#   0 6 * * * /path/to/web_product_intelligence/scripts/run_pipeline.sh >> /path/to/web_product_intelligence/data/run.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
python -m src.pipeline "$@"
