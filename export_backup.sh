#!/bin/bash
# Description: Pure bash backup script requiring zero python dependencies.
# Uses your authenticated gcloud CLI to pull DDL schemas and full CSV table dumps.

set -e

# Try loading from .env if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

PROJECT="${GCP_PROJECT_ID:-waybackhome-qdtl7yj6kghd4u340n}"
INSTANCE="${SPANNER_INSTANCE_ID:-hazard-detection}"
DATABASE="${SPANNER_DATABASE_ID:-hazard-db}"

BACKUP_DIR="spanner_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "============================================="
echo " Creating Spanner Backup in: $BACKUP_DIR"
echo "============================================="

echo "1. Extracting complete DDL schema..."
gcloud spanner databases ddl describe "$DATABASE" --instance="$INSTANCE" --project="$PROJECT" > "$BACKUP_DIR/schema.sql"

TABLES=(
    "Districts" "IssueCategories" "Users" "Organizations"
    "Issues" "Videos" "IssueEpisodes" "VideoTelemetry"
    "IssueUpvotes" "VideoSegments" "Reports" "MediaBlobs"
    "UserDistricts" "UserInterests" "OrgDistricts"
)

echo "2. Exporting table subsets to individual CSV files..."
for TABLE in "${TABLES[@]}"; do
    echo "   -> Dumping $TABLE..."
    gcloud spanner databases execute-sql "$DATABASE" --instance="$INSTANCE" --project="$PROJECT" \
        --sql="SELECT * FROM $TABLE" \
        --format="csv" > "$BACKUP_DIR/${TABLE}.csv"
done

echo "============================================="
echo " SUCCESS! Full system backup downloaded."
echo " Details: $BACKUP_DIR/"
echo "============================================="
