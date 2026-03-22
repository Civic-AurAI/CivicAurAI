from datetime import datetime
from typing import Optional

import numpy as np
from pydantic import BaseModel, ConfigDict


class FrameMeta:
    """A video frame with associated metadata. Not a Pydantic model because it holds numpy arrays."""

    def __init__(
        self,
        frame_image: np.ndarray,
        timestamp: datetime,
        gps_lat: float,
        gps_lon: float,
        frame_index: int = 0,
        source_path: Optional[str] = None,
    ):
        self.frame_image = frame_image
        self.timestamp = timestamp
        self.gps_lat = gps_lat
        self.gps_lon = gps_lon
        self.frame_index = frame_index
        self.source_path = source_path


class HazardDetection(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    hazard_type: str
    description: str
    confidence: float
    severity: str  # low | medium | high | critical
    timestamp: datetime
    gps_lat: float
    gps_lon: float
    frame_index: int = 0


class VideoChunk:
    """A clip-sized segment of video with metadata."""

    def __init__(
        self,
        frames: list[FrameMeta],
        start_time: datetime,
        end_time: datetime,
        gps_lat: float,
        gps_lon: float,
        chunk_index: int,
        temp_clip_path: str,
    ):
        self.frames = frames
        self.start_time = start_time
        self.end_time = end_time
        self.gps_lat = gps_lat
        self.gps_lon = gps_lon
        self.chunk_index = chunk_index
        self.temp_clip_path = temp_clip_path


# ---------------------------------------------------------------------------
# CivicAurAI Spanner models
# ---------------------------------------------------------------------------


class User(BaseModel):
    user_id: str
    name: str
    email: Optional[str] = None
    role: str  # CITIZEN | CITY_WORKER | ADMIN | ORG_MEMBER
    district_id: Optional[str] = None


class Organization(BaseModel):
    org_id: str
    name: str
    org_type: str  # CITY_DEPT | NGO | CONTRACTOR
    capabilities: list[str] = []


class District(BaseModel):
    district_id: str
    name: str
    boundary_geojson: Optional[str] = None


class IssueCategory(BaseModel):
    category_id: str  # POTHOLE, BIOHAZARD, etc.
    name: str
    description: Optional[str] = None


class Issue(BaseModel):
    issue_id: str
    category_id: str
    title: str
    description: Optional[str] = None
    latitude: float
    longitude: float
    severity: Optional[str] = None
    status: str = "NEW"  # NEW | OPEN | IN_PROGRESS | RESOLVED | SNOOZED
    priority: int = 0


class Report(BaseModel):
    report_id: str
    issue_id: str
    reporter_id: Optional[str] = None  # None = AI detection
    report_type: str  # AI_DETECTION | CITIZEN | CITY_WORKER
    description: Optional[str] = None
    latitude: float
    longitude: float
    confidence: Optional[float] = None
    segment_id: Optional[str] = None
    video_id: Optional[str] = None


class Video(BaseModel):
    video_id: str
    source_device: Optional[str] = None
    uploaded_by: Optional[str] = None
    gcs_url: Optional[str] = None
    duration_sec: Optional[float] = None


class VideoSegment(BaseModel):
    video_id: str
    segment_id: str
    segment_index: int
    start_time: datetime
    end_time: datetime
    gps_lat: float
    gps_lon: float
    clip_gcs_url: Optional[str] = None


class IssueEpisode(BaseModel):
    issue_id: str
    episode_id: str
    actor_id: Optional[str] = None  # None = system/AI
    action: str  # CREATED | STATUS_CHANGE | SIGHTING | ASSIGNED | COMMENT
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    notes: Optional[str] = None


class MediaBlob(BaseModel):
    blob_id: str
    report_id: str
    blob_type: str  # VIDEO_CLIP | PHOTO | THUMBNAIL
    gcs_url: str


# ---------------------------------------------------------------------------
# Category mapping — AI free-form hazard_type → controlled CategoryId
# ---------------------------------------------------------------------------

HAZARD_TYPE_TO_CATEGORY: dict[str, str] = {
    "pothole": "POTHOLE",
    "potholes": "POTHOLE",
    "road surface damage": "ROAD_DAMAGE",
    "pothole or road surface damage": "POTHOLE",
    "potholes or road surface damage": "POTHOLE",
    "debris": "DEBRIS",
    "damaged road signs": "DAMAGED_SIGNS",
    "damaged, missing, or obscured road signs": "DAMAGED_SIGNS",
    "broken traffic lights": "BROKEN_TRAFFIC_LIGHT",
    "flooding": "FLOODING",
    "fallen trees": "FALLEN_TREE",
    "damaged sidewalks or curbs": "DAMAGED_SIDEWALK",
    "damaged sidewalk or curb": "DAMAGED_SIDEWALK",
    "damaged sidewalk": "DAMAGED_SIDEWALK",
    "damaged sidewalks": "DAMAGED_SIDEWALK",
    "exposed utility covers": "EXPOSED_UTILITY",
    "exposed utility cover": "EXPOSED_UTILITY",
    "missing manhole cover": "EXPOSED_UTILITY",
}

# Keywords used as fallback when exact match fails
_CATEGORY_KEYWORDS: dict[str, str] = {
    "pothole": "POTHOLE",
    "sidewalk": "DAMAGED_SIDEWALK",
    "curb": "DAMAGED_SIDEWALK",
    "manhole": "EXPOSED_UTILITY",
    "utility": "EXPOSED_UTILITY",
    "debris": "DEBRIS",
    "sign": "DAMAGED_SIGNS",
    "traffic light": "BROKEN_TRAFFIC_LIGHT",
    "flood": "FLOODING",
    "tree": "FALLEN_TREE",
    "biohazard": "BIOHAZARD",
    "needle": "BIOHAZARD",
}

DEFAULT_ISSUE_CATEGORIES: list[IssueCategory] = [
    IssueCategory(category_id="POTHOLE", name="Pothole or Road Surface Damage"),
    IssueCategory(category_id="ROAD_DAMAGE", name="Road Surface Damage"),
    IssueCategory(category_id="DEBRIS", name="Debris or Obstruction"),
    IssueCategory(category_id="DAMAGED_SIGNS", name="Damaged or Missing Road Signs"),
    IssueCategory(category_id="BROKEN_TRAFFIC_LIGHT", name="Broken Traffic Light"),
    IssueCategory(category_id="FLOODING", name="Flooding or Standing Water"),
    IssueCategory(category_id="FALLEN_TREE", name="Fallen Tree or Branch"),
    IssueCategory(category_id="DAMAGED_SIDEWALK", name="Damaged Sidewalk or Curb"),
    IssueCategory(category_id="EXPOSED_UTILITY", name="Exposed Utility or Missing Cover"),
    IssueCategory(category_id="BIOHAZARD", name="Biohazard"),
    IssueCategory(category_id="HOMELESS_OUTREACH", name="Homeless Outreach"),
    IssueCategory(category_id="OTHER", name="Other Hazard"),
]


def normalize_category(hazard_type: str) -> str:
    """Map AI hazard_type string to a CategoryId. Falls back to OTHER."""
    key = hazard_type.lower().strip()
    # Exact match first
    if key in HAZARD_TYPE_TO_CATEGORY:
        return HAZARD_TYPE_TO_CATEGORY[key]
    # Keyword fallback
    for keyword, cat in _CATEGORY_KEYWORDS.items():
        if keyword in key:
            return cat
    return "OTHER"
