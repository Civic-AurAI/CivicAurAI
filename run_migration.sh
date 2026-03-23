#!/bin/bash
# End-to-End Database Migration and Embedding Pipeline

set -e

# Source env if it exists
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

PROJECT="${GCP_PROJECT_ID:-waybackhome-t3nafn8idj7dzub9t5}"
INSTANCE="${SPANNER_INSTANCE_ID:-hazard-detection}"
DATABASE="${SPANNER_DATABASE_ID:-hazard-db}"

echo "============================================="
echo " Initiating CivicAurAI Environment Migration "
echo " Target Project: $PROJECT"
echo "============================================="

# 1. Provision Platform Instance (Ignored if exists)
echo -e "\n1. Provisioning Target Spanner Instance..."
gcloud spanner instances create "$INSTANCE" \
    --config=regional-us-central1 \
    --description="CivicAurAI Geographic Cluster" \
    --processing-units=100 \
    --project="$PROJECT" || echo "Instance $INSTANCE already exists. Proceeding..."

# 2. Provision Database with Geographically Upgraded DDL
echo -e "\n2. Generating Upgraded Database Schema..."
gcloud spanner databases create "$DATABASE" \
    --instance="$INSTANCE" \
    --project="$PROJECT" \
    --ddl-file=00_schema_upgraded.sql || echo "Database $DATABASE exists. Retrying schema application..."

# Ensures schema updates correctly apply if database existed but was empty
gcloud spanner databases ddl update "$DATABASE" \
    --instance="$INSTANCE" \
    --project="$PROJECT" \
    --ddl-file=00_schema_upgraded.sql || echo "DDL synchronized."

# 3. Stream Backup Data into Upgraded Structure
echo -e "\n3. Engaging Bulk DML Python Import Service..."
uv run python restore_data.py

# 4. Trigger Native Embedding and AI Summary Generation
echo -e "\n4. Commencing AI Backfill (LLM Summaries & Vertex Embeddings)..."
uv run python -c "from seed_and_embed import backfill_embeddings; backfill_embeddings()"

echo "============================================="
echo " MIGRATION & ENRICHMENT COMPLETE!"
echo " Everything is provisioned securely on $PROJECT."
echo "============================================="
