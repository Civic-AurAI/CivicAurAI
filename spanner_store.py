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
    "Districts": """\
CREATE TABLE Districts (
  DistrictId STRING(50) NOT NULL,
  Name STRING(MAX) NOT NULL,
) PRIMARY KEY(DistrictId)""",

    "IssueCategories": """\
CREATE TABLE IssueCategories (
  CategoryId STRING(50) NOT NULL,
  DisplayName STRING(MAX) NOT NULL,
) PRIMARY KEY(CategoryId)""",

    "Issues": """\
CREATE TABLE Issues (
  IssueId STRING(36) NOT NULL,
  CategoryId STRING(50) NOT NULL,
  DistrictId STRING(50),
  Severity STRING(20),
  Latitude FLOAT64 NOT NULL,
  Longitude FLOAT64 NOT NULL,
  Status STRING(20) NOT NULL,
  CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
  ResolvedAt TIMESTAMP OPTIONS (allow_commit_timestamp = true),
  AssignedOrgId STRING(36),
) PRIMARY KEY(IssueId)""",

    "IssueEpisodes": """\
CREATE TABLE IssueEpisodes (
  IssueId STRING(36) NOT NULL,
  EpisodeId STRING(36) NOT NULL,
  ActorId STRING(36),
  PreviousStatus STRING(20),
  NewStatus STRING(20) NOT NULL,
  Comment STRING(MAX),
  EpisodeTimestamp TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
) PRIMARY KEY(IssueId, EpisodeId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE""",

    "IssueUpvotes": """\
CREATE TABLE IssueUpvotes (
  IssueId STRING(36) NOT NULL,
  UserId STRING(36) NOT NULL,
  UpvotedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
) PRIMARY KEY(IssueId, UserId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE""",

    "MediaBlobs": """\
CREATE TABLE MediaBlobs (
  MediaId STRING(36) NOT NULL,
  ReportId STRING(36),
  EpisodeId STRING(36),
  GcsUri STRING(MAX) NOT NULL,
  MediaType STRING(20) NOT NULL,
  UploadedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
  Embedding ARRAY<FLOAT64>,
) PRIMARY KEY(MediaId)""",

    "OrgDistricts": """\
CREATE TABLE OrgDistricts (
  OrgId STRING(36) NOT NULL,
  DistrictId STRING(50) NOT NULL,
) PRIMARY KEY(OrgId, DistrictId)""",

    "Organizations": """\
CREATE TABLE Organizations (
  OrgId STRING(36) NOT NULL,
  Name STRING(MAX) NOT NULL,
  OrgType STRING(50) NOT NULL,
  Capabilities ARRAY<STRING(MAX)>,
) PRIMARY KEY(OrgId)""",

    "Reports": """\
CREATE TABLE Reports (
  ReportId STRING(36) NOT NULL,
  IssueId STRING(36) NOT NULL,
  ReporterId STRING(36),
  SegmentId STRING(36),
  SourceType STRING(20) NOT NULL,
  Description STRING(MAX),
  AiMetadata JSON,
  ReportedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
  Embedding ARRAY<FLOAT64>,
) PRIMARY KEY(ReportId)""",

    "UserDistricts": """\
CREATE TABLE UserDistricts (
  UserId STRING(36) NOT NULL,
  DistrictId STRING(50) NOT NULL,
) PRIMARY KEY(UserId, DistrictId)""",

    "UserInterests": """\
CREATE TABLE UserInterests (
  UserId STRING(36) NOT NULL,
  CategoryId STRING(50) NOT NULL,
) PRIMARY KEY(UserId, CategoryId)""",

    "Users": """\
CREATE TABLE Users (
  UserId STRING(36) NOT NULL,
  Name STRING(MAX),
  Role STRING(50) NOT NULL,
  IsAnonymous BOOL NOT NULL,
  CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
) PRIMARY KEY(UserId)""",

    "VideoSegments": """\
CREATE TABLE VideoSegments (
  SegmentId STRING(36) NOT NULL,
  VideoId STRING(36) NOT NULL,
  StartTimeOffset FLOAT64 NOT NULL,
  EndTimeOffset FLOAT64 NOT NULL,
  AiSummary STRING(MAX),
  GcsUri STRING(MAX),
  Embedding ARRAY<FLOAT64>,
) PRIMARY KEY(SegmentId)""",

    "Videos": """\
CREATE TABLE Videos (
  VideoId STRING(36) NOT NULL,
  SourceDevice STRING(MAX),
  GcsUri STRING(MAX) NOT NULL,
  CaptureStartTime TIMESTAMP,
  CaptureEndTime TIMESTAMP,
  UploadedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp = true),
) PRIMARY KEY(VideoId)""",

    "VideoTelemetry": """\
CREATE TABLE VideoTelemetry (
  VideoId STRING(36) NOT NULL,
  TelemetryTime TIMESTAMP NOT NULL,
  Latitude FLOAT64 NOT NULL,
  Longitude FLOAT64 NOT NULL,
  Heading FLOAT64,
  Pitch FLOAT64,
  Roll FLOAT64,
) PRIMARY KEY(VideoId, TelemetryTime),
  INTERLEAVE IN PARENT Videos ON DELETE CASCADE""",
}

# Ordered list ensures dependency-safe creation
TABLE_ORDER = [
    # Phase 1
    "Districts", "IssueCategories", "Users", "Organizations",
    # Phase 2
    "Issues", "Videos",
    # Phase 3 (interleaved)
    "IssueEpisodes", "VideoTelemetry", "IssueUpvotes",
    # Phase 4
    "VideoSegments", "Reports", "MediaBlobs",
    # Phase 5 (edge tables)
    "UserDistricts", "UserInterests", "OrgDistricts",
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
    IssueEpisodes,
    VideoTelemetry,
    Reports,
    MediaBlobs
  )
  EDGE TABLES (
    Issues AS HasCategory
      SOURCE KEY (IssueId) REFERENCES Issues
      DESTINATION KEY (CategoryId) REFERENCES IssueCategories
      LABEL HAS_CATEGORY,
    Issues AS LocatedIn
      SOURCE KEY (IssueId) REFERENCES Issues
      DESTINATION KEY (DistrictId) REFERENCES Districts
      LABEL LOCATED_IN,
    Issues AS AssignedTo
      SOURCE KEY (IssueId) REFERENCES Issues
      DESTINATION KEY (AssignedOrgId) REFERENCES Organizations
      LABEL ASSIGNED_TO,
    VideoSegments AS SegmentOf
      SOURCE KEY (SegmentId) REFERENCES VideoSegments
      DESTINATION KEY (VideoId) REFERENCES Videos
      LABEL EXTRACTED_FROM,
    IssueEpisodes AS EpisodeOf
      SOURCE KEY (IssueId, EpisodeId) REFERENCES IssueEpisodes
      DESTINATION KEY (IssueId) REFERENCES Issues
      LABEL EPISODE_OF,
    IssueEpisodes AS ActedBy
      SOURCE KEY (IssueId, EpisodeId) REFERENCES IssueEpisodes
      DESTINATION KEY (ActorId) REFERENCES Users
      LABEL ACTED_BY,
    VideoTelemetry AS TelemetryOf
      SOURCE KEY (VideoId, TelemetryTime) REFERENCES VideoTelemetry
      DESTINATION KEY (VideoId) REFERENCES Videos
      LABEL TELEMETRY_OF,
    Reports AS RelatesToIssue
      SOURCE KEY (ReportId) REFERENCES Reports
      DESTINATION KEY (IssueId) REFERENCES Issues
      LABEL RELATES_TO,
    Reports AS SubmittedBy
      SOURCE KEY (ReportId) REFERENCES Reports
      DESTINATION KEY (ReporterId) REFERENCES Users
      LABEL SUBMITTED_BY,
    Reports AS IdentifiedIn
      SOURCE KEY (ReportId) REFERENCES Reports
      DESTINATION KEY (SegmentId) REFERENCES VideoSegments
      LABEL IDENTIFIED_IN,
    MediaBlobs AS BlobOfReport
      SOURCE KEY (MediaId) REFERENCES MediaBlobs
      DESTINATION KEY (ReportId) REFERENCES Reports
      LABEL BLOB_OF,
    UserDistricts AS LivesIn
      SOURCE KEY (UserId) REFERENCES Users
      DESTINATION KEY (DistrictId) REFERENCES Districts
      LABEL LIVES_IN,
    UserInterests AS InterestedIn
      SOURCE KEY (UserId) REFERENCES Users
      DESTINATION KEY (CategoryId) REFERENCES IssueCategories
      LABEL INTERESTED_IN,
    OrgDistricts AS OperatesIn
      SOURCE KEY (OrgId) REFERENCES Organizations
      DESTINATION KEY (DistrictId) REFERENCES Districts
      LABEL OPERATES_IN,
    IssueUpvotes AS Upvoted
      SOURCE KEY (UserId) REFERENCES Users
      DESTINATION KEY (IssueId) REFERENCES Issues
      LABEL UPVOTED
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
            columns=["CategoryId", "DisplayName"],
            values=[[c.category_id, c.name] for c in missing],
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
            "AND ST_DWITHIN(ST_GEOGPOINT(Longitude, Latitude), ST_GEOGPOINT(@lon, @lat), @radius)",
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
                "IssueId", "CategoryId", "Latitude", "Longitude", 
                "Severity", "Status", "CreatedAt",
            ],
            values=[[
                issue_id, category_id, lat, lon, 
                severity, "NEW", spanner.COMMIT_TIMESTAMP,
            ]],
        )
        batch.insert(
            "IssueEpisodes",
            columns=["IssueId", "EpisodeId", "NewStatus", "Comment", "EpisodeTimestamp"],
            values=[[
                issue_id, episode_id, "NEW", description, spanner.COMMIT_TIMESTAMP,
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
            columns=["IssueId", "EpisodeId", "NewStatus", "Comment", "EpisodeTimestamp"],
            values=[[
                issue_id, episode_id, "NEW", description, spanner.COMMIT_TIMESTAMP,
            ]],
        )

    logger.info("Added sighting episode to issue %s", issue_id)


# ---------------------------------------------------------------------------
# Report + MediaBlob helpers
# ---------------------------------------------------------------------------

def _create_report(
    issue_id: str,
    description: str,
    confidence: float,
    segment_id: str | None,
) -> str:
    """Create an AI_VISION report linked to an Issue. Returns report_id."""
    report_id = str(uuid.uuid4())
    db = get_database()
    import json

    with db.batch() as batch:
        batch.insert(
            "Reports",
            columns=[
                "ReportId", "IssueId", "SourceType",
                "Description", "SegmentId", "AiMetadata", "ReportedAt",
            ],
            values=[[
                report_id, issue_id, "AI_VISION",
                description, segment_id, json.dumps({"confidence": confidence}), spanner.COMMIT_TIMESTAMP,
            ]],
        )

    return report_id


def _create_media_blob(report_id: str, media_type: str, gcs_uri: str) -> str:
    """Create a MediaBlob linked to a Report. Returns media_id."""
    media_id = str(uuid.uuid4())
    db = get_database()

    with db.batch() as batch:
        batch.insert(
            "MediaBlobs",
            columns=["MediaId", "ReportId", "MediaType", "GcsUri", "UploadedAt"],
            values=[[media_id, report_id, media_type, gcs_uri, spanner.COMMIT_TIMESTAMP]],
        )

    return media_id


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
            columns=["VideoId", "SourceDevice", "GcsUri", "UploadedAt"],
            values=[[video_id, video_name, "gs://raw", spanner.COMMIT_TIMESTAMP]],
        )

    logger.info("Created video record %s for %s", video_id, video_name)
    return video_id


def insert_segment(video_id: str, chunk: VideoChunk, gcs_url: str) -> str:
    """Create a VideoSegments row. Returns segment_id."""
    segment_id = str(uuid.uuid4())
    db = get_database()

    with db.batch() as batch:
        batch.insert(
            "VideoSegments",
            columns=[
                "SegmentId", "VideoId", "StartTimeOffset", "EndTimeOffset", "GcsUri",
            ],
            values=[[
                segment_id, video_id, chunk.start_time, chunk.end_time, gcs_url,
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
        confidence=detection.confidence,
        segment_id=segment_id,
    )

    # Create MediaBlob linking the clip
    _create_media_blob(report_id, "VIDEO_CLIP", clip_gcs_url)

    logger.info(
        "Detection stored: issue=%s, report=%s, category=%s",
        issue_id, report_id, category_id,
    )
