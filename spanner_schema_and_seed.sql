-- ==========================================
-- DDL FOR CLOUD SPANNER (GRAPH & RDBMS)
-- ==========================================

-- 1. Organizations table (City agencies, volunteer groups, etc.)
CREATE TABLE Organizations (
    OrgId STRING(36) NOT NULL,
    Name STRING(MAX) NOT NULL,
    OrgType STRING(50) NOT NULL, -- 'CITY_AGENCY', 'COMMUNITY_GROUP', 'CONTRACTOR'
    Capabilities ARRAY<STRING(MAX)> -- E.g., ['HEAVY_LIFTING', 'BIOHAZARD', 'TRAFFIC_CONTROL']
) PRIMARY KEY(OrgId);

-- 2. Users table (Citizens, City Workers, or AI Systems)
CREATE TABLE Users (
    UserId STRING(36) NOT NULL,
    Name STRING(MAX),
    Role STRING(50) NOT NULL, -- 'CITIZEN', 'CITY_WORKER', 'AI_SYSTEM', 'PARTNER'
    IsAnonymous BOOL NOT NULL,
    CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(UserId);

-- 3. Issues table (The confirmed ground-truth problem on the street)
CREATE TABLE Issues (
    IssueId STRING(36) NOT NULL,
    Category STRING(50) NOT NULL, -- e.g., 'GARBAGE_WASTE', 'HOMELESS_OUTREACH', 'STREET_LIGHT_POTHOLE'
    Severity STRING(20), -- 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    Latitude FLOAT64 NOT NULL,
    Longitude FLOAT64 NOT NULL,
    Status STRING(20) NOT NULL, -- 'NEW', 'OPEN', 'IN_PROGRESS', 'RESOLVED', 'SNOOZED'
    CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    ResolvedAt TIMESTAMP,
    AssignedOrgId STRING(36)
) PRIMARY KEY(IssueId);

-- 4. IssueUpdates (Temporal tracking of an issue's lifecycle, interleaved for performance)
CREATE TABLE IssueUpdates (
    IssueId STRING(36) NOT NULL,
    UpdateId STRING(36) NOT NULL,
    ActorId STRING(36),          -- Could be User or System
    PreviousStatus STRING(20),
    NewStatus STRING(20) NOT NULL,
    Comment STRING(MAX),
    UpdatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(IssueId, UpdateId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE;

-- 5. IssueUpvotes (Tracks explicit +1s from human users, prevents AI upvote spam)
CREATE TABLE IssueUpvotes (
    IssueId STRING(36) NOT NULL,
    UserId STRING(36) NOT NULL,
    UpvotedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(IssueId, UserId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE;

-- 6. Videos (The original video from an AV/Robot)
CREATE TABLE Videos (
    VideoId STRING(36) NOT NULL,
    SourceDevice STRING(MAX), -- e.g., 'WAYMO_AV_101', 'STARSHIP_ROBOT_45'
    GcsUri STRING(MAX) NOT NULL,
    CaptureStartTime TIMESTAMP,
    CaptureEndTime TIMESTAMP,
    UploadedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(VideoId);

-- 6. VideoTelemetry (~200ms updates, tightly interleaved with Videos for fast spatial/temporal queries)
CREATE TABLE VideoTelemetry (
    VideoId STRING(36) NOT NULL,
    TelemetryTime TIMESTAMP NOT NULL,
    Latitude FLOAT64 NOT NULL,
    Longitude FLOAT64 NOT NULL,
    Heading FLOAT64, -- 0-360 degrees
    Pitch FLOAT64,
    Roll FLOAT64
) PRIMARY KEY(VideoId, TelemetryTime),
  INTERLEAVE IN PARENT Videos ON DELETE CASCADE;

-- 7. VideoSegments (Splits of interesting events)
CREATE TABLE VideoSegments (
    SegmentId STRING(36) NOT NULL,
    VideoId STRING(36) NOT NULL,
    StartTimeOffset FLOAT64 NOT NULL, -- in seconds
    EndTimeOffset FLOAT64 NOT NULL,   -- in seconds
    AiSummary STRING(MAX),
    GcsUri STRING(MAX)                -- Link to the clipped segment
) PRIMARY KEY(SegmentId);

-- 8. Reports (An instance of reporting an issue, from AI or Citizen)
CREATE TABLE Reports (
    ReportId STRING(36) NOT NULL,
    IssueId STRING(36) NOT NULL,  -- Link to the unified problem
    ReporterId STRING(36),        -- User/AI who reported
    SegmentId STRING(36),         -- Segment it was extracted from (if AI)
    SourceType STRING(20) NOT NULL, -- 'AI_VISION', 'CITIZEN_APP', 'WORKER_APP'
    Description STRING(MAX),
    AiMetadata JSON,              -- e.g., {"estimated_volume_cubic_yards": 2.5, "recommended_vehicle": "Heavy-loader truck"}
    ReportedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(ReportId);

-- 9. MediaBlobs (Photos or additional files for a report or update)
CREATE TABLE MediaBlobs (
    MediaId STRING(36) NOT NULL,
    ReportId STRING(36),          -- Attached to original report
    UpdateId STRING(36),          -- Or attached to a fix/update (e.g. "verified resolution" photo)
    GcsUri STRING(MAX) NOT NULL,
    MediaType STRING(20) NOT NULL, -- 'PHOTO', 'VIDEO_THUMBNAIL'
    UploadedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(MediaId);


-- ==========================================
-- SPANNER PROPERTY GRAPH (CivicGraph)
-- ==========================================
CREATE PROPERTY GRAPH CivicGraph
    NODE TABLES (
        Users,
        Organizations,
        Issues,
        Videos,
        VideoSegments,
        Reports,
        MediaBlobs
    )
    EDGE TABLES (
        -- Issue makes sense to be assigned to an Organization
        Issues AS AssignedTo
            SOURCE KEY (IssueId) REFERENCES Issues
            DESTINATION KEY (AssignedOrgId) REFERENCES Organizations
            LABEL ASSIGNED_TO,
            
        -- Report relates to Issue (multiple reports can point to one semantic issue)
        Reports AS RelatesToIssue
            SOURCE KEY (ReportId) REFERENCES Reports
            DESTINATION KEY (IssueId) REFERENCES Issues
            LABEL RELATES_TO,
            
        -- Report was submitted by a User (Citizen, Worker, or AI System)
        Reports AS SubmittedBy
            SOURCE KEY (ReportId) REFERENCES Reports
            DESTINATION KEY (ReporterId) REFERENCES Users
            LABEL SUBMITTED_BY,
            
        -- User explicitly upvoted (+1) an Issue
        IssueUpvotes AS Upvoted
            SOURCE KEY (UserId) REFERENCES Users
            DESTINATION KEY (IssueId) REFERENCES Issues
            LABEL UPVOTED,
            
            
        -- Report was identified in a Video Segment
        Reports AS IdentifiedIn
            SOURCE KEY (ReportId) REFERENCES Reports
            DESTINATION KEY (SegmentId) REFERENCES VideoSegments
            LABEL IDENTIFIED_IN,
            
        -- Segment was extracted from Video
        VideoSegments AS SegmentOf
            SOURCE KEY (SegmentId) REFERENCES VideoSegments
            DESTINATION KEY (VideoId) REFERENCES Videos
            LABEL EXTRACTED_FROM
    );


-- ==========================================
-- DML: SEED DATA FOR DEMOS/HACKATHON
-- ==========================================

-- 1. Insert Organizations (Agencies, Communities)
INSERT INTO Organizations (OrgId, Name, OrgType, Capabilities) VALUES
('org-dpw-09', 'DPW / RECOLOGY', 'CITY_AGENCY', ['GARBAGE', 'HEAVY_LIFTING', 'GRAFFITI']),
('org-hot-soma', 'Homeless Outreach Team (HOT-SOMA)', 'COMMUNITY_GROUP', ['SOCIAL_SERVICES', 'MEDICAL_RESPONSE', 'SHELTER_ROUTING']),
('org-muni-fix', 'SF-MUNI-FIX', 'CITY_AGENCY', ['ELECTRICAL', 'ROAD_REPAIR', 'SIGNAL_MAINTENANCE']),
('org-sfpd-amb', 'SFPD-AMB', 'CITY_AGENCY', ['PUBLIC_SAFETY', 'EMERGENCY_RESPONSE']),
('org-community-care', 'Mission Neighborhood Cleaners', 'VOLUNTEER_GROUP', ['STREET_SWEEP', 'LIGHT_TRASH']),
('org-code-enf', 'DBI / CODE ENFORCEMENT', 'CITY_AGENCY', ['PERMIT_ISSUES', 'CONSTRUCTION_SAFETY']);

-- 2. Insert Users (AI, Citizens, Partners)
INSERT INTO Users (UserId, Name, Role, IsAnonymous, CreatedAt) VALUES
('user-ai-vision', 'CivicGuardian Vision System', 'AI_SYSTEM', false, CURRENT_TIMESTAMP()),
('user-anon-guest', 'Guest User', 'CITIZEN', true, CURRENT_TIMESTAMP()),
('user-citizen-jane', 'Jane Doe', 'CITIZEN', false, CURRENT_TIMESTAMP()),
('user-worker-bob', 'Bob (DPW)', 'CITY_WORKER', false, CURRENT_TIMESTAMP());

-- 3. Insert Unified Issues (These exist independently of how many reports they receive)
INSERT INTO Issues (IssueId, Category, Severity, Latitude, Longitude, Status, CreatedAt, AssignedOrgId) VALUES
('iss-2026-03521', 'GARBAGE_WASTE', 'HIGH', 37.7648, -122.4195, 'NEW', TIMESTAMP '2026-03-21T18:00:00Z', 'org-dpw-09'),
('iss-2026-03522', 'GARBAGE_WASTE', 'MEDIUM', 37.7610, -122.4215, 'IN_PROGRESS', TIMESTAMP '2026-03-21T16:00:00Z', 'org-dpw-09'),
('iss-2026-03489', 'GARBAGE_WASTE', 'LOW', 37.7590, -122.4265, 'RESOLVED', TIMESTAMP '2026-03-19T10:00:00Z', 'org-community-care'),
('iss-2026-03530', 'STREET_LIGHT_POTHOLE', 'MEDIUM', 37.7710, -122.4130, 'SNOOZED', TIMESTAMP '2026-03-21T19:00:00Z', 'org-muni-fix');

-- 4. Temporal Aspect: Issue Updates (Lifecycle progression)
INSERT INTO IssueUpdates (IssueId, UpdateId, ActorId, PreviousStatus, NewStatus, Comment, UpdatedAt) VALUES
('iss-2026-03521', 'upd-1', 'user-ai-vision', NULL, 'NEW', 'Issue automatically detected via Waymo video feed sweep. Confidence 98%.', TIMESTAMP '2026-03-21T18:00:00Z'),
('iss-2026-03522', 'upd-2', 'user-citizen-jane', NULL, 'NEW', 'Overflowing bin on Valencia St corner.', TIMESTAMP '2026-03-21T16:00:00Z'),
('iss-2026-03522', 'upd-3', 'user-worker-bob', 'NEW', 'IN_PROGRESS', 'Dispatched DPW truck #42.', TIMESTAMP '2026-03-21T17:00:00Z'),
('iss-2026-03530', 'upd-4', 'user-anon-guest', NULL, 'NEW', 'Warning: construction debris blocking lane.', TIMESTAMP '2026-03-21T19:00:00Z'),
('iss-2026-03530', 'upd-5', 'user-worker-bob', 'NEW', 'SNOOZED', 'Known PG&E construction zone. Temporary permitted dirt pile. Checking back next week.', TIMESTAMP '2026-03-21T19:30:00Z'),
('iss-2026-03489', 'upd-6', 'user-citizen-jane', NULL, 'NEW', 'Trash on Dolores Park East side.', TIMESTAMP '2026-03-19T10:00:00Z'),
('iss-2026-03489', 'upd-7', 'user-worker-bob', 'IN_PROGRESS', 'RESOLVED', 'Cleaned up by volunteer group MNC.', TIMESTAMP '2026-03-20T14:00:00Z');

-- 4b. Human Upvotes (+1s) on Issues (No AI allowed here to prevent ping spam)
INSERT INTO IssueUpvotes (IssueId, UserId, UpvotedAt) VALUES
('iss-2026-03521', 'user-citizen-jane', TIMESTAMP '2026-03-21T18:25:00Z'),
('iss-2026-03521', 'user-anon-guest', TIMESTAMP '2026-03-21T18:30:00Z');

-- 5. Videos
INSERT INTO Videos (VideoId, SourceDevice, GcsUri, CaptureStartTime, CaptureEndTime, UploadedAt) VALUES
('vid-waymo-101', 'WAYMO_AV_101', 'gs://civic-aurai-hack/videos/raw/waymo_101_20260321.mp4', TIMESTAMP '2026-03-21T17:50:00Z', TIMESTAMP '2026-03-21T18:10:00Z', CURRENT_TIMESTAMP());

-- 6. Video Telemetry (Simulated ~200ms ping frequency)
INSERT INTO VideoTelemetry (VideoId, TelemetryTime, Latitude, Longitude, Heading, Pitch, Roll) VALUES
('vid-waymo-101', TIMESTAMP '2026-03-21T17:59:59.000Z', 37.7648, -122.4195, 270.5, 0.1, 0.0),
('vid-waymo-101', TIMESTAMP '2026-03-21T17:59:59.200Z', 37.76481, -122.41951, 270.5, 0.2, -0.1),
('vid-waymo-101', TIMESTAMP '2026-03-21T17:59:59.400Z', 37.76482, -122.41952, 270.5, 0.1, 0.0),
('vid-waymo-101', TIMESTAMP '2026-03-21T17:59:59.600Z', 37.76483, -122.41953, 270.6, 0.0, 0.0),
('vid-waymo-101', TIMESTAMP '2026-03-21T17:59:59.800Z', 37.76484, -122.41954, 270.6, 0.1, 0.0);

-- 7. Video Segments (Interesting splits mapped to issues)
INSERT INTO VideoSegments (SegmentId, VideoId, StartTimeOffset, EndTimeOffset, AiSummary, GcsUri) VALUES
('seg-101-dumping', 'vid-waymo-101', 598.0, 603.5, 'Large pile of furniture and construction debris blocking sidewalk. Estimated volume 2.5 cubic yards.', 'gs://civic-aurai-hack/videos/segments/seg_101_dumping.mp4');

-- 8. Reports (AI Vision vs Citizen apps - Both can point to the same issue through geo/semantic matching)
INSERT INTO Reports (ReportId, IssueId, ReporterId, SegmentId, SourceType, Description, AiMetadata, ReportedAt) VALUES
('rep-001', 'iss-2026-03521', 'user-ai-vision', 'seg-101-dumping', 'AI_VISION', 'AI discovered dumping during routine AV sweep.', '{"estimated_volume_cubic_yards": 2.5, "recommended_vehicle": "Heavy-loader truck"}', TIMESTAMP '2026-03-21T18:00:00Z'),
('rep-002', 'iss-2026-03521', 'user-anon-guest', NULL, 'CITIZEN_APP', 'Someone dumped a couch and a bunch of trash here at 16th/Mission!', NULL, TIMESTAMP '2026-03-21T18:15:00Z'); -- Matches to same issue Semantic/Geo

-- 9. Media Blobs (Images attached to reports or status updates)
INSERT INTO MediaBlobs (MediaId, ReportId, UpdateId, GcsUri, MediaType, UploadedAt) VALUES
('media-img-1', 'rep-001', NULL, 'gs://civic-aurai-hack/images/rep_001_frame.jpg', 'PHOTO', CURRENT_TIMESTAMP()),
('media-img-2', 'rep-002', NULL, 'gs://civic-aurai-hack/images/anon_submission_1.jpg', 'PHOTO', CURRENT_TIMESTAMP()),
('media-img-3', NULL, 'upd-7', 'gs://civic-aurai-hack/images/resolved_03489.jpg', 'PHOTO', CURRENT_TIMESTAMP());
