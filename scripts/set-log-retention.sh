#!/usr/bin/env bash
# Set CloudWatch Logs retention on every AgriNexus Lambda and Synthetics canary log group.
# Lambda creates these groups on first invocation (outside the SAM template), so they
# default to "never expire". Run after `sam deploy` whenever a function is added.
# Usage:
#   ./scripts/set-log-retention.sh          # 90 days, us-east-1
#   ./scripts/set-log-retention.sh 30 eu-west-1

set -euo pipefail
DAYS="${1:-90}"
REGION="${2:-${AWS_REGION:-us-east-1}}"

aws logs describe-log-groups --region "$REGION" --log-group-name-prefix /aws/lambda/ \
  --query 'logGroups[].logGroupName' --output text \
  | tr '\t' '\n' \
  | grep -E '^/aws/lambda/(agrinexus-|cwsyn-agnx-)' \
  | while read -r group; do
      aws logs put-retention-policy --region "$REGION" --log-group-name "$group" --retention-in-days "$DAYS"
      echo "$group -> ${DAYS}d"
    done
