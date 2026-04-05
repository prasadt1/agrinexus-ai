#!/usr/bin/env bash
# Orchestrate S3 Vectors + Bedrock KB rebuild. Run from repo root with AWS CLI configured.
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
export AWS_REGION

echo "=== AgriNexus: S3 Vectors + Knowledge Base helper ==="
echo "Region: $REGION"
echo ""
echo "Step A — Create vector bucket + index (Python/boto3)"
python3 scripts/create_s3_vector_resources.py --region "$REGION" || true

echo ""
echo "Step B — Create Knowledge Base (console recommended)"
echo "  Bedrock > Knowledge bases > Create > Vector store: Amazon S3 Vectors"
echo "  Embedding: Amazon Titan Text Embeddings v2 (1024 dimensions)"
echo ""
echo "Step C — Add S3 data source pointing at your FAO PDF prefix, then start ingestion."
echo "  See REBUILD-KB-WITH-S3-VECTORS.md for CLI examples."
echo ""
echo "Step D — Deploy with new Knowledge Base ID:"
echo "  sam deploy --config-file samconfig-week2.toml --parameter-overrides KnowledgeBaseId=YOUR_NEW_KB_ID"
echo "  (OpenWeatherMap key: Secrets Manager agrinexus/weather/api-key — not a deploy parameter)"
echo ""
echo "Step E — Smoke test:"
echo "  pytest tests/test_golden_questions.py -v   # with KNOWLEDGE_BASE_ID set"
echo "  # or WhatsApp text query against cotton IPM"
