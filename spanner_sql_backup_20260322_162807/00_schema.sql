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

CREATE PROPERTY GRAPH CivicGraph
  NODE TABLES(
    Districts
      KEY(DistrictId)
      LABEL Districts PROPERTIES(
        DistrictId,
        Name),

    IssueCategories
      KEY(CategoryId)
      LABEL IssueCategories PROPERTIES(
        CategoryId,
        DisplayName),

    IssueEpisodes
      KEY(IssueId, EpisodeId)
      LABEL IssueEpisodes PROPERTIES(
        ActorId,
        Comment,
        EpisodeId,
        EpisodeTimestamp,
        IssueId,
        NewStatus,
        PreviousStatus),

    Issues
      KEY(IssueId)
      LABEL Issues PROPERTIES(
        AssignedOrgId,
        CategoryId,
        CreatedAt,
        DistrictId,
        IssueId,
        Latitude,
        Longitude,
        ResolvedAt,
        Severity,
        Status),

    MediaBlobs
      KEY(MediaId)
      LABEL MediaBlobs PROPERTIES(
        Embedding,
        EpisodeId,
        GcsUri,
        MediaId,
        MediaType,
        ReportId,
        UploadedAt),

    Organizations
      KEY(OrgId)
      LABEL Organizations PROPERTIES(
        Capabilities,
        Name,
        OrgId,
        OrgType),

    Reports
      KEY(ReportId)
      LABEL Reports PROPERTIES(
        AiMetadata,
        Description,
        Embedding,
        IssueId,
        ReportedAt,
        ReporterId,
        ReportId,
        SegmentId,
        SourceType),

    Users
      KEY(UserId)
      LABEL Users PROPERTIES(
        CreatedAt,
        IsAnonymous,
        Name,
        Role,
        UserId),

    Videos
      KEY(VideoId)
      LABEL Videos PROPERTIES(
        CaptureEndTime,
        CaptureStartTime,
        GcsUri,
        SourceDevice,
        UploadedAt,
        VideoId),

    VideoSegments
      KEY(SegmentId)
      LABEL VideoSegments PROPERTIES(
        AiSummary,
        Embedding,
        EndTimeOffset,
        GcsUri,
        SegmentId,
        StartTimeOffset,
        VideoId),

    VideoTelemetry
      KEY(VideoId, TelemetryTime)
      LABEL VideoTelemetry PROPERTIES(
        Heading,
        Latitude,
        Longitude,
        Pitch,
        Roll,
        TelemetryTime,
        VideoId)
  )
  EDGE TABLES(
    IssueEpisodes AS ActedBy
      KEY(IssueId, EpisodeId)
      SOURCE KEY(EpisodeId, IssueId) REFERENCES IssueEpisodes(EpisodeId, IssueId)
      DESTINATION KEY(ActorId) REFERENCES Users(UserId)
      LABEL ACTED_BY PROPERTIES(
        ActorId,
        Comment,
        EpisodeId,
        EpisodeTimestamp,
        IssueId,
        NewStatus,
        PreviousStatus),

    Issues AS AssignedTo
      KEY(IssueId)
      SOURCE KEY(IssueId) REFERENCES Issues(IssueId)
      DESTINATION KEY(AssignedOrgId) REFERENCES Organizations(OrgId)
      LABEL ASSIGNED_TO PROPERTIES(
        AssignedOrgId,
        CategoryId,
        CreatedAt,
        DistrictId,
        IssueId,
        Latitude,
        Longitude,
        ResolvedAt,
        Severity,
        Status),

    MediaBlobs AS BlobOfReport
      KEY(MediaId)
      SOURCE KEY(MediaId) REFERENCES MediaBlobs(MediaId)
      DESTINATION KEY(ReportId) REFERENCES Reports(ReportId)
      LABEL BLOB_OF PROPERTIES(
        Embedding,
        EpisodeId,
        GcsUri,
        MediaId,
        MediaType,
        ReportId,
        UploadedAt),

    IssueEpisodes AS EpisodeOf
      KEY(IssueId, EpisodeId)
      SOURCE KEY(EpisodeId, IssueId) REFERENCES IssueEpisodes(EpisodeId, IssueId)
      DESTINATION KEY(IssueId) REFERENCES Issues(IssueId)
      LABEL EPISODE_OF PROPERTIES(
        ActorId,
        Comment,
        EpisodeId,
        EpisodeTimestamp,
        IssueId,
        NewStatus,
        PreviousStatus),

    Issues AS HasCategory
      KEY(IssueId)
      SOURCE KEY(IssueId) REFERENCES Issues(IssueId)
      DESTINATION KEY(CategoryId) REFERENCES IssueCategories(CategoryId)
      LABEL HAS_CATEGORY PROPERTIES(
        AssignedOrgId,
        CategoryId,
        CreatedAt,
        DistrictId,
        IssueId,
        Latitude,
        Longitude,
        ResolvedAt,
        Severity,
        Status),

    Reports AS IdentifiedIn
      KEY(ReportId)
      SOURCE KEY(ReportId) REFERENCES Reports(ReportId)
      DESTINATION KEY(SegmentId) REFERENCES VideoSegments(SegmentId)
      LABEL IDENTIFIED_IN PROPERTIES(
        AiMetadata,
        Description,
        Embedding,
        IssueId,
        ReportedAt,
        ReporterId,
        ReportId,
        SegmentId,
        SourceType),

    UserInterests AS InterestedIn
      KEY(UserId, CategoryId)
      SOURCE KEY(UserId) REFERENCES Users(UserId)
      DESTINATION KEY(CategoryId) REFERENCES IssueCategories(CategoryId)
      LABEL INTERESTED_IN PROPERTIES(
        CategoryId,
        UserId),

    UserDistricts AS LivesIn
      KEY(UserId, DistrictId)
      SOURCE KEY(UserId) REFERENCES Users(UserId)
      DESTINATION KEY(DistrictId) REFERENCES Districts(DistrictId)
      LABEL LIVES_IN PROPERTIES(
        DistrictId,
        UserId),

    Issues AS LocatedIn
      KEY(IssueId)
      SOURCE KEY(IssueId) REFERENCES Issues(IssueId)
      DESTINATION KEY(DistrictId) REFERENCES Districts(DistrictId)
      LABEL LOCATED_IN PROPERTIES(
        AssignedOrgId,
        CategoryId,
        CreatedAt,
        DistrictId,
        IssueId,
        Latitude,
        Longitude,
        ResolvedAt,
        Severity,
        Status),

    OrgDistricts AS OperatesIn
      KEY(OrgId, DistrictId)
      SOURCE KEY(OrgId) REFERENCES Organizations(OrgId)
      DESTINATION KEY(DistrictId) REFERENCES Districts(DistrictId)
      LABEL OPERATES_IN PROPERTIES(
        DistrictId,
        OrgId),

    Reports AS RelatesToIssue
      KEY(ReportId)
      SOURCE KEY(ReportId) REFERENCES Reports(ReportId)
      DESTINATION KEY(IssueId) REFERENCES Issues(IssueId)
      LABEL RELATES_TO PROPERTIES(
        AiMetadata,
        Description,
        Embedding,
        IssueId,
        ReportedAt,
        ReporterId,
        ReportId,
        SegmentId,
        SourceType),

    VideoSegments AS SegmentOf
      KEY(SegmentId)
      SOURCE KEY(SegmentId) REFERENCES VideoSegments(SegmentId)
      DESTINATION KEY(VideoId) REFERENCES Videos(VideoId)
      LABEL EXTRACTED_FROM PROPERTIES(
        AiSummary,
        Embedding,
        EndTimeOffset,
        GcsUri,
        SegmentId,
        StartTimeOffset,
        VideoId),

    Reports AS SubmittedBy
      KEY(ReportId)
      SOURCE KEY(ReportId) REFERENCES Reports(ReportId)
      DESTINATION KEY(ReporterId) REFERENCES Users(UserId)
      LABEL SUBMITTED_BY PROPERTIES(
        AiMetadata,
        Description,
        Embedding,
        IssueId,
        ReportedAt,
        ReporterId,
        ReportId,
        SegmentId,
        SourceType),

    VideoTelemetry AS TelemetryOf
      KEY(VideoId, TelemetryTime)
      SOURCE KEY(TelemetryTime, VideoId) REFERENCES VideoTelemetry(TelemetryTime, VideoId)
      DESTINATION KEY(VideoId) REFERENCES Videos(VideoId)
      LABEL TELEMETRY_OF PROPERTIES(
        Heading,
        Latitude,
        Longitude,
        Pitch,
        Roll,
        TelemetryTime,
        VideoId),

    IssueUpvotes AS Upvoted
      KEY(IssueId, UserId)
      SOURCE KEY(UserId) REFERENCES Users(UserId)
      DESTINATION KEY(IssueId) REFERENCES Issues(IssueId)
      LABEL UPVOTED PROPERTIES(
        IssueId,
        UpvotedAt,
        UserId)
  );

