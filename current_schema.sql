CREATE TABLE Districts (
  DistrictId STRING(50) NOT NULL,
  Name STRING(MAX) NOT NULL,
) PRIMARY KEY(DistrictId);

CREATE TABLE IssueCategories (
  CategoryId STRING(50) NOT NULL,
  DisplayName STRING(MAX) NOT NULL,
) PRIMARY KEY(CategoryId);

CREATE TABLE Issues (
  IssueId STRING(36) NOT NULL,
  CategoryId STRING(50) NOT NULL,
  DistrictId STRING(50),
  Severity STRING(20),
  Latitude FLOAT64 NOT NULL,
  Longitude FLOAT64 NOT NULL,
  Status STRING(20) NOT NULL,
  CreatedAt TIMESTAMP NOT NULL OPTIONS (
    allow_commit_timestamp = true
  ),
  ResolvedAt TIMESTAMP OPTIONS (
    allow_commit_timestamp = true
  ),
  AssignedOrgId STRING(36),
) PRIMARY KEY(IssueId);

CREATE TABLE IssueEpisodes (
  IssueId STRING(36) NOT NULL,
  EpisodeId STRING(36) NOT NULL,
  ActorId STRING(36),
  PreviousStatus STRING(20),
  NewStatus STRING(20) NOT NULL,
  Comment STRING(MAX),
  EpisodeTimestamp TIMESTAMP NOT NULL OPTIONS (
    allow_commit_timestamp = true
  ),
) PRIMARY KEY(IssueId, EpisodeId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE;

CREATE TABLE IssueUpvotes (
  IssueId STRING(36) NOT NULL,
  UserId STRING(36) NOT NULL,
  UpvotedAt TIMESTAMP NOT NULL OPTIONS (
    allow_commit_timestamp = true
  ),
) PRIMARY KEY(IssueId, UserId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE;

CREATE TABLE MediaBlobs (
  MediaId STRING(36) NOT NULL,
  ReportId STRING(36),
  EpisodeId STRING(36),
  GcsUri STRING(MAX) NOT NULL,
  MediaType STRING(20) NOT NULL,
  UploadedAt TIMESTAMP NOT NULL OPTIONS (
    allow_commit_timestamp = true
  ),
  Embedding ARRAY<FLOAT64>,
) PRIMARY KEY(MediaId);

CREATE TABLE OrgDistricts (
  OrgId STRING(36) NOT NULL,
  DistrictId STRING(50) NOT NULL,
) PRIMARY KEY(OrgId, DistrictId);

CREATE TABLE Organizations (
  OrgId STRING(36) NOT NULL,
  Name STRING(MAX) NOT NULL,
  OrgType STRING(50) NOT NULL,
  Capabilities ARRAY<STRING(MAX)>,
) PRIMARY KEY(OrgId);

CREATE TABLE Reports (
  ReportId STRING(36) NOT NULL,
  IssueId STRING(36) NOT NULL,
  ReporterId STRING(36),
  SegmentId STRING(36),
  SourceType STRING(20) NOT NULL,
  Description STRING(MAX),
  AiMetadata JSON,
  ReportedAt TIMESTAMP NOT NULL OPTIONS (
    allow_commit_timestamp = true
  ),
  Embedding ARRAY<FLOAT64>,
) PRIMARY KEY(ReportId);

CREATE TABLE UserDistricts (
  UserId STRING(36) NOT NULL,
  DistrictId STRING(50) NOT NULL,
) PRIMARY KEY(UserId, DistrictId);

CREATE TABLE UserInterests (
  UserId STRING(36) NOT NULL,
  CategoryId STRING(50) NOT NULL,
) PRIMARY KEY(UserId, CategoryId);

CREATE TABLE Users (
  UserId STRING(36) NOT NULL,
  Name STRING(MAX),
  Role STRING(50) NOT NULL,
  IsAnonymous BOOL NOT NULL,
  CreatedAt TIMESTAMP NOT NULL OPTIONS (
    allow_commit_timestamp = true
  ),
) PRIMARY KEY(UserId);

CREATE TABLE VideoSegments (
  SegmentId STRING(36) NOT NULL,
  VideoId STRING(36) NOT NULL,
  StartTimeOffset FLOAT64 NOT NULL,
  EndTimeOffset FLOAT64 NOT NULL,
  AiSummary STRING(MAX),
  GcsUri STRING(MAX),
  Embedding ARRAY<FLOAT64>,
) PRIMARY KEY(SegmentId);

CREATE TABLE Videos (
  VideoId STRING(36) NOT NULL,
  SourceDevice STRING(MAX),
  GcsUri STRING(MAX) NOT NULL,
  CaptureStartTime TIMESTAMP,
  CaptureEndTime TIMESTAMP,
  UploadedAt TIMESTAMP NOT NULL OPTIONS (
    allow_commit_timestamp = true
  ),
) PRIMARY KEY(VideoId);

CREATE TABLE VideoTelemetry (
  VideoId STRING(36) NOT NULL,
  TelemetryTime TIMESTAMP NOT NULL,
  Latitude FLOAT64 NOT NULL,
  Longitude FLOAT64 NOT NULL,
  Heading FLOAT64,
  Pitch FLOAT64,
  Roll FLOAT64,
) PRIMARY KEY(VideoId, TelemetryTime),
  INTERLEAVE IN PARENT Videos ON DELETE CASCADE;

