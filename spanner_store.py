"""Cloud Spanner storage for CivicAurAI — 16-table schema + Property Graph."""

from __future__ import annotations

import logging
import math
import uuid
from datetime import datetime

from google.cloud import spanner
from google.cloud.spanner_v1 import param_types

from config import config
from models import (
    DEFAULT_ISSUE_CATEGORIES,
    HazardDetection,
    VideoChunk,
    normalize_category,
)

logger = logging.getLogger(__name__)

_client = None
_database = None

# ---------------------------------------------------------------------------
# DDL — ordered by dependency (phases 1-5)
# ---------------------------------------------------------------------------

TABLE_DDL: dict[str, str] = {
    # Phase 1 — standalone
    "Districts": """\
CREATE TABLE Districts (
    DistrictId      STRING(36) NOT NULL,
    Name            STRING(256) NOT NULL,
    BoundaryGeoJson STRING(MAX),
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
) PRIMARY KEY (DistrictId)""",

    "IssueCategories": """\
CREATE TABLE IssueCategories (
    CategoryId      STRING(64) NOT NULL,
    Name            STRING(256) NOT NULL,
    Description     STRING(2048),
) PRIMARY KEY (CategoryId)""",

    "Users": """\
CREATE TABLE Users (
    UserId          STRING(36) NOT NULL,
    Name            STRING(256) NOT NULL,
    Email           STRING(512),
    Role            STRING(32) NOT NULL,
    DistrictId      STRING(36),
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
) PRIMARY KEY (UserId)""",

    "Organizations": """\
CREATE TABLE Organizations (
    OrgId           STRING(36) NOT NULL,
    Name            STRING(256) NOT NULL,
    OrgType         STRING(32) NOT NULL,
    Capabilities    ARRAY<STRING(128)>,
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
) PRIMARY KEY (OrgId)""",

    # Phase 2 — parent tables for interleaving
    "Issues": """\
CREATE TABLE Issues (
    IssueId         STRING(36) NOT NULL,
    CategoryId      STRING(64) NOT NULL,
    Title           STRING(512) NOT NULL,
    Description     STRING(4096),
    Location        GEOGRAPHY NOT NULL,
    Severity        STRING(16),
    Status          STRING(32) NOT NULL,
    Priority        INT64,
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    UpdatedAt       TIMESTAMP,
) PRIMARY KEY (IssueId)""",

    "Videos": """\
CREATE TABLE Videos (
    VideoId         STRING(36) NOT NULL,
    SourceDevice    STRING(256),
    UploadedBy      STRING(36),
    GcsUrl          STRING(1024),
    DurationSec     FLOAT64,
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
) PRIMARY KEY (VideoId)""",

    # Phase 3 — interleaved children
    "VideoSegments": """\
CREATE TABLE VideoSegments (
    VideoId         STRING(36) NOT NULL,
    SegmentId       STRING(36) NOT NULL,
    SegmentIndex    INT64,
    StartTime       TIMESTAMP NOT NULL,
    EndTime         TIMESTAMP NOT NULL,
    Location        GEOGRAPHY NOT NULL,
    ClipGcsUrl      STRING(1024),
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    Embedding       ARRAY<FLOAT64>,
) PRIMARY KEY (VideoId, SegmentId),
  INTERLEAVE IN PARENT Videos ON DELETE CASCADE""",

    "IssueEpisodes": """\
CREATE TABLE IssueEpisodes (
    IssueId         STRING(36) NOT NULL,
    EpisodeId       STRING(36) NOT NULL,
    ActorId         STRING(36),
    Action          STRING(64) NOT NULL,
    OldValue        STRING(1024),
    NewValue        STRING(1024),
    Notes           STRING(4096),
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
) PRIMARY KEY (IssueId, EpisodeId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE""",

    "VideoTelemetry": """\
CREATE TABLE VideoTelemetry (
    VideoId         STRING(36) NOT NULL,
    TelemetryId     STRING(36) NOT NULL,
    Timestamp       TIMESTAMP NOT NULL,
    Location        GEOGRAPHY,
    Heading         FLOAT64,
    Speed           FLOAT64,
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
) PRIMARY KEY (VideoId, TelemetryId),
  INTERLEAVE IN PARENT Videos ON DELETE CASCADE""",

    # Phase 4 — FK-dependent tables
    "Reports": """\
CREATE TABLE Reports (
    ReportId        STRING(36) NOT NULL,
    IssueId         STRING(36) NOT NULL,
    ReporterId      STRING(36),
    ReportType      STRING(32) NOT NULL,
    Description     STRING(4096),
    Location        GEOGRAPHY NOT NULL,
    Confidence      FLOAT64,
    SegmentId       STRING(36),
    VideoId         STRING(36),
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    Embedding       ARRAY<FLOAT64>,
) PRIMARY KEY (ReportId)""",

    "MediaBlobs": """\
CREATE TABLE MediaBlobs (
    BlobId          STRING(36) NOT NULL,
    ReportId        STRING(36) NOT NULL,
    BlobType        STRING(32) NOT NULL,
    GcsUrl          STRING(1024) NOT NULL,
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    Embedding       ARRAY<FLOAT64>,
) PRIMARY KEY (BlobId)""",

    "IssueUpvotes": """\
CREATE TABLE IssueUpvotes (
    IssueId         STRING(36) NOT NULL,
    UserId          STRING(36) NOT NULL,
    CreatedAt       TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
) PRIMARY KEY (IssueId, UserId)""",

    # Phase 5 — graph edge tables
    "UserDistricts": """\
CREATE TABLE UserDistricts (
    UserId          STRING(36) NOT NULL,
    DistrictId      STRING(36) NOT NULL,
) PRIMARY KEY (UserId, DistrictId)""",

    "UserInterests": """\
CREATE TABLE UserInterests (
    UserId          STRING(36) NOT NULL,
    CategoryId      STRING(64) NOT NULL,
) PRIMARY KEY (UserId, CategoryId)""",

    "OrgDistricts": """\
CREATE TABLE OrgDistricts (
    OrgId           STRING(36) NOT NULL,
    DistrictId      STRING(36) NOT NULL,
) PRIMARY KEY (OrgId, DistrictId)""",

    "IssueDistricts": """\
CREATE TABLE IssueDistricts (
    IssueId         STRING(36) NOT NULL,
    DistrictId      STRING(36) NOT NULL,
) PRIMARY KEY (IssueId, DistrictId)""",
}

# Ordered list ensures dependency-safe creation
TABLE_ORDER = [
    # Phase 1
    "Districts", "IssueCategories", "Users", "Organizations",
    # Phase 2
    "Issues", "Videos",
    # Phase 3 (interleaved — parents must exist first)
    "VideoSegments", "IssueEpisodes", "VideoTelemetry",
    # Phase 4
    "Reports", "MediaBlobs", "IssueUpvotes",
    # Phase 5 (edge tables)
    "UserDistricts", "UserInterests", "OrgDistricts", "IssueDistricts",
]

GRAPH_DDL = """\
CREATE PROPERTY GRAPH CivicGraph
  NODE TABLES (
    Users,
    Organizations,
    Districts,
    IssueCategories,
    Issues,
    Videos,
    VideoSegments,
    Reports,
    MediaBlobs
  )
  EDGE TABLES (
    UserDistricts
      SOURCE KEY (UserId) REFERENCES Users (UserId)
      DESTINATION KEY (DistrictId) REFERENCES Districts (DistrictId),
    UserInterests
      SOURCE KEY (UserId) REFERENCES Users (UserId)
      DESTINATION KEY (CategoryId) REFERENCES IssueCategories (CategoryId),
    OrgDistricts
      SOURCE KEY (OrgId) REFERENCES Organizations (OrgId)
      DESTINATION KEY (DistrictId) REFERENCES Districts (DistrictId),
    IssueDistricts
      SOURCE KEY (IssueId) REFERENCES Issues (IssueId)
      DESTINATION KEY (DistrictId) REFERENCES Districts (DistrictId)
  )"""

# Legacy tables to drop
LEGACY_TABLES = ["video_chunks", "known_hazards"]


# ---------------------------------------------------------------------------
# Database access
# ---------------------------------------------------------------------------

def get_database():
    global _client, _database
    if _database is None:
        _client = spanner.Client(project=config.gcp_project_id)
        instance = _client.instance(config.spanner_instance_id)
        _database = instance.database(config.spanner_database_id)
    return _database


def _existing_tables() -> set[str]:
    db = get_database()
    with db.snapshot() as snapshot:
        results = snapshot.execute_sql(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = ''"
        )
        return {row[0] for row in results}


def _graph_exists(graph_name: str = "CivicGraph") -> bool:
    db = get_database()
    try:
        with db.snapshot() as snapshot:
            results = snapshot.execute_sql(
                "SELECT property_graph_name FROM information_schema.property_graphs "
                "WHERE property_graph_name = @name",
                params={"name": graph_name},
                param_types={"name": param_types.STRING},
            )
            return bool(list(results))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------

def ensure_tables() -> None:
    """Create all CivicAurAI tables + property graph. Drop legacy tables."""
    existing = _existing_tables()

    # Drop legacy tables first
    drop_ddl = []
    for legacy in LEGACY_TABLES:
        if legacy in existing:
            drop_ddl.append(f"DROP TABLE {legacy}")
    if drop_ddl:
        db = get_database()
        op = db.update_ddl(drop_ddl)
        op.result()
        logger.info("Dropped legacy tables: %s", LEGACY_TABLES)
        existing = _existing_tables()

    # Create missing tables in dependency order
    create_ddl = []
    for name in TABLE_ORDER:
        if name not in existing:
            create_ddl.append(TABLE_DDL[name])

    if create_ddl:
        db = get_database()
        op = db.update_ddl(create_ddl)
        op.result()
        logger.info("Created %d Spanner tables", len(create_ddl))
    else:
        logger.info("All Spanner tables already exist")

    # Create property graph if missing (requires Enterprise edition)
    if not _graph_exists():
        try:
            db = get_database()
            op = db.update_ddl([GRAPH_DDL])
            op.result()
            logger.info("Created CivicGraph property graph")
        except Exception as e:
            if "ENTERPRISE" in str(e) or "GRAPH" in str(e):
                logger.warning(
                    "Skipping CivicGraph creation — requires Spanner Enterprise edition. "
                    "All relational tables are functional without it."
                )
            else:
                raise


def ensure_seed_data() -> None:
    """Seed IssueCategories with default values (idempotent)."""
    db = get_database()

    with db.snapshot() as snapshot:
        results = snapshot.execute_sql("SELECT CategoryId FROM IssueCategories")
        existing_ids = {row[0] for row in results}

    missing = [c for c in DEFAULT_ISSUE_CATEGORIES if c.category_id not in existing_ids]
    if not missing:
        return

    with db.batch() as batch:
        batch.insert(
            "IssueCategories",
            columns=["CategoryId", "Name", "Description"],
            values=[[c.category_id, c.name, c.description] for c in missing],
        )
    logger.info("Seeded %d issue categories", len(missing))


# ---------------------------------------------------------------------------
# Haversine distance for GPS dedup
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Issue dedup (evolved from _find_nearby_hazard)
# ---------------------------------------------------------------------------

def _find_nearby_issue(category_id: str, gps_lat: float, gps_lon: float) -> str | None:
    """Find an unresolved Issue of the same category within dedup_radius_meters.
    Returns IssueId if found, else None.
    Uses Spanner native ST_DWITHIN geospatial indexing."""
    if not config.dedup_enabled:
        return None

    db = get_database()
    with db.snapshot() as snapshot:
        results = snapshot.execute_sql(
            "SELECT IssueId FROM Issues "
            "WHERE CategoryId = @cat AND Status != 'RESOLVED' "
            "AND ST_DWITHIN(Location, ST_GEOGPOINT(@lon, @lat), @radius)",
            params={
                "cat": category_id,
                "lat": gps_lat,
                "lon": gps_lon,
                "radius": float(config.dedup_radius_meters),
            },
            param_types={
                "cat": param_types.STRING,
                "lat": param_types.FLOAT64,
                "lon": param_types.FLOAT64,
                "radius": param_types.FLOAT64,
            },
        )
        for row in results:
            return row[0]

    return None


# ---------------------------------------------------------------------------
# Issue + Episode helpers
# ---------------------------------------------------------------------------

def _create_issue(
    category_id: str,
    title: str,
    description: str,
    lat: float,
    lon: float,
    severity: str,
) -> str:
    """Create a new Issue + initial CREATED episode. Returns issue_id."""
    issue_id = str(uuid.uuid4())
    episode_id = str(uuid.uuid4())
    db = get_database()

    with db.batch() as batch:
        batch.insert(
            "Issues",
            columns=[
                "IssueId", "CategoryId", "Title", "Description",
                "Location", "Severity", "Status", "Priority",
                "CreatedAt",
            ],
            values=[[
                issue_id, category_id, title, description,
                f"POINT({lon} {lat})", severity, "NEW", 0,
                spanner.COMMIT_TIMESTAMP,
            ]],
        )
        batch.insert(
            "IssueEpisodes",
            columns=["IssueId", "EpisodeId", "ActorId", "Action", "NewValue", "Notes", "CreatedAt"],
            values=[[
                issue_id, episode_id, None, "CREATED",
                "NEW", description, spanner.COMMIT_TIMESTAMP,
            ]],
        )

    logger.info("Created new issue %s: %s (%s)", issue_id, title, category_id)
    return issue_id


def _add_sighting_episode(issue_id: str, description: str) -> None:
    """Append a SIGHTING episode to an existing Issue."""
    episode_id = str(uuid.uuid4())
    db = get_database()

    with db.batch() as batch:
        batch.insert(
            "IssueEpisodes",
            columns=["IssueId", "EpisodeId", "ActorId", "Action", "Notes", "CreatedAt"],
            values=[[
                issue_id, episode_id, None, "SIGHTING",
                description, spanner.COMMIT_TIMESTAMP,
            ]],
        )

    logger.info("Added sighting episode to issue %s", issue_id)


# ---------------------------------------------------------------------------
# Report + MediaBlob helpers
# ---------------------------------------------------------------------------

def _create_report(
    issue_id: str,
    description: str,
    lat: float,
    lon: float,
    confidence: float,
    segment_id: str | None,
    video_id: str | None,
) -> str:
    """Create an AI_DETECTION report linked to an Issue. Returns report_id."""
    report_id = str(uuid.uuid4())
    db = get_database()

    with db.batch() as batch:
        batch.insert(
            "Reports",
            columns=[
                "ReportId", "IssueId", "ReporterId", "ReportType",
                "Description", "Location", "Confidence",
                "SegmentId", "VideoId", "CreatedAt",
            ],
            values=[[
                report_id, issue_id, None, "AI_DETECTION",
                description, f"POINT({lon} {lat})", confidence,
                segment_id, video_id, spanner.COMMIT_TIMESTAMP,
            ]],
        )

    return report_id


def _create_media_blob(report_id: str, blob_type: str, gcs_url: str) -> str:
    """Create a MediaBlob linked to a Report. Returns blob_id."""
    blob_id = str(uuid.uuid4())
    db = get_database()

    with db.batch() as batch:
        batch.insert(
            "MediaBlobs",
            columns=["BlobId", "ReportId", "BlobType", "GcsUrl", "CreatedAt"],
            values=[[blob_id, report_id, blob_type, gcs_url, spanner.COMMIT_TIMESTAMP]],
        )

    return blob_id


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def insert_video(video_name: str, duration_sec: float | None = None) -> str:
    """Create a Videos row for the input file. Returns video_id."""
    video_id = str(uuid.uuid4())
    db = get_database()

    with db.batch() as batch:
        batch.insert(
            "Videos",
            columns=["VideoId", "SourceDevice", "UploadedBy", "GcsUrl", "DurationSec", "CreatedAt"],
            values=[[video_id, video_name, None, None, duration_sec, spanner.COMMIT_TIMESTAMP]],
        )

    logger.info("Created video record %s for %s", video_id, video_name)
    return video_id


def insert_segment(video_id: str, chunk: VideoChunk, gcs_url: str) -> str:
    """Create a VideoSegments row (interleaved under Videos). Returns segment_id."""
    segment_id = str(uuid.uuid4())
    db = get_database()

    with db.batch() as batch:
        batch.insert(
            "VideoSegments",
            columns=[
                "VideoId", "SegmentId", "SegmentIndex",
                "StartTime", "EndTime", "Location",
                "ClipGcsUrl", "CreatedAt",
            ],
            values=[[
                video_id, segment_id, chunk.chunk_index,
                chunk.start_time, chunk.end_time, f"POINT({chunk.gps_lon} {chunk.gps_lat})",
                gcs_url, spanner.COMMIT_TIMESTAMP,
            ]],
        )

    logger.info("Stored segment %s (chunk %d)", segment_id, chunk.chunk_index)
    return segment_id


def insert_detection(
    video_id: str,
    segment_id: str,
    clip_gcs_url: str,
    detection: HazardDetection,
    gps_lat: float,
    gps_lon: float,
) -> None:
    """Process a hazard detection: dedup → Issue → Report → MediaBlob."""
    category_id = normalize_category(detection.hazard_type)

    # Dedup: find existing Issue nearby with same category
    existing_issue_id = _find_nearby_issue(category_id, gps_lat, gps_lon)

    if existing_issue_id:
        issue_id = existing_issue_id
        _add_sighting_episode(issue_id, detection.description)
    else:
        issue_id = _create_issue(
            category_id=category_id,
            title=detection.hazard_type,
            description=detection.description,
            lat=gps_lat,
            lon=gps_lon,
            severity=detection.severity,
        )

    # Create Report linked to Issue
    report_id = _create_report(
        issue_id=issue_id,
        description=detection.description,
        lat=gps_lat,
        lon=gps_lon,
        confidence=detection.confidence,
        segment_id=segment_id,
        video_id=video_id,
    )

    # Create MediaBlob linking the clip
    _create_media_blob(report_id, "VIDEO_CLIP", clip_gcs_url)

    logger.info(
        "Detection stored: issue=%s, report=%s, category=%s",
        issue_id, report_id, category_id,
    )
