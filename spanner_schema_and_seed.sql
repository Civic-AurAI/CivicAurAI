-- ==========================================
-- DDL FOR CLOUD SPANNER (GRAPH & RDBMS)
-- ==========================================

-- 1. Taxonomy / Reference Tables (For Graph Nodes)
CREATE TABLE Districts (
    DistrictId STRING(50) NOT NULL,
    Name STRING(MAX) NOT NULL
) PRIMARY KEY(DistrictId);

CREATE TABLE IssueCategories (
    CategoryId STRING(50) NOT NULL,
    DisplayName STRING(MAX) NOT NULL
) PRIMARY KEY(CategoryId);

-- 2. Actors
CREATE TABLE Organizations (
    OrgId STRING(36) NOT NULL,
    Name STRING(MAX) NOT NULL,
    OrgType STRING(50) NOT NULL, -- 'CITY_AGENCY', 'COMMUNITY_GROUP', 'CONTRACTOR'
    Capabilities ARRAY<STRING(MAX)>
) PRIMARY KEY(OrgId);

CREATE TABLE Users (
    UserId STRING(36) NOT NULL,
    Name STRING(MAX),
    Role STRING(50) NOT NULL, -- 'CITIZEN', 'CITY_WORKER', 'AI_SYSTEM', 'PARTNER'
    IsAnonymous BOOL NOT NULL,
    CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(UserId);

-- 3. Personalization & Routing Edges
CREATE TABLE OrgDistricts (
    OrgId STRING(36) NOT NULL,
    DistrictId STRING(50) NOT NULL
) PRIMARY KEY(OrgId, DistrictId);

CREATE TABLE UserDistricts (
    UserId STRING(36) NOT NULL,
    DistrictId STRING(50) NOT NULL
) PRIMARY KEY(UserId, DistrictId);

CREATE TABLE UserInterests (
    UserId STRING(36) NOT NULL,
    CategoryId STRING(50) NOT NULL
) PRIMARY KEY(UserId, CategoryId);

-- 4. Unified Issues (The Ground Truth problem)
CREATE TABLE Issues (
    IssueId STRING(36) NOT NULL,
    CategoryId STRING(50) NOT NULL, -- FK to IssueCategories
    DistrictId STRING(50),          -- FK to Districts
    Severity STRING(20), 
    Location GEOGRAPHY NOT NULL,
    Status STRING(20) NOT NULL, 
    CreatedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    ResolvedAt TIMESTAMP,
    AssignedOrgId STRING(36)
) PRIMARY KEY(IssueId);

-- 5. IssueEpisodes (Graphity-style temporal tracking of an issue's lifecycle)
CREATE TABLE IssueEpisodes (
    IssueId STRING(36) NOT NULL,
    EpisodeId STRING(36) NOT NULL,
    ActorId STRING(36),          
    PreviousStatus STRING(20),
    NewStatus STRING(20) NOT NULL,
    Comment STRING(MAX),
    EpisodeTimestamp TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(IssueId, EpisodeId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE;

-- 6. IssueUpvotes (Tracks explicit +1s from human users)
CREATE TABLE IssueUpvotes (
    IssueId STRING(36) NOT NULL,
    UserId STRING(36) NOT NULL,
    UpvotedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(IssueId, UserId),
  INTERLEAVE IN PARENT Issues ON DELETE CASCADE;

-- 7. Videos & Telemetry
CREATE TABLE Videos (
    VideoId STRING(36) NOT NULL,
    SourceDevice STRING(MAX), 
    GcsUri STRING(MAX) NOT NULL,
    CaptureStartTime TIMESTAMP,
    CaptureEndTime TIMESTAMP,
    UploadedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true)
) PRIMARY KEY(VideoId);

CREATE TABLE VideoTelemetry (
    VideoId STRING(36) NOT NULL,
    TelemetryTime TIMESTAMP NOT NULL,
    Location GEOGRAPHY NOT NULL,
    Heading FLOAT64, 
    Pitch FLOAT64,
    Roll FLOAT64
) PRIMARY KEY(VideoId, TelemetryTime),
  INTERLEAVE IN PARENT Videos ON DELETE CASCADE;

-- 8. VideoSegments (Splits of interesting events)
CREATE TABLE VideoSegments (
    SegmentId STRING(36) NOT NULL,
    VideoId STRING(36) NOT NULL,
    StartTimeOffset FLOAT64 NOT NULL,
    EndTimeOffset FLOAT64 NOT NULL,   
    AiSummary STRING(MAX),
    GcsUri STRING(MAX),
    Embedding ARRAY<FLOAT64>
) PRIMARY KEY(SegmentId);

-- 9. Reports & Media
CREATE TABLE Reports (
    ReportId STRING(36) NOT NULL,
    IssueId STRING(36) NOT NULL,  
    ReporterId STRING(36),        
    SegmentId STRING(36),         
    SourceType STRING(20) NOT NULL, 
    Description STRING(MAX),
    AiMetadata JSON,              
    ReportedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    Embedding ARRAY<FLOAT64>
) PRIMARY KEY(ReportId);

CREATE TABLE MediaBlobs (
    MediaId STRING(36) NOT NULL,
    ReportId STRING(36),          
    EpisodeId STRING(36),         
    GcsUri STRING(MAX) NOT NULL,
    MediaType STRING(20) NOT NULL, 
    UploadedAt TIMESTAMP NOT NULL OPTIONS (allow_commit_timestamp=true),
    Embedding ARRAY<FLOAT64>
) PRIMARY KEY(MediaId);


-- ==========================================
-- SPANNER PROPERTY GRAPH (CivicGraph)
-- ==========================================
CREATE PROPERTY GRAPH CivicGraph
    NODE TABLES (
        Users, Organizations, Issues, Videos, VideoSegments, Reports, MediaBlobs, Districts, IssueCategories
    )
    EDGE TABLES (
        Issues AS AssignedTo DESTINATION KEY (AssignedOrgId) REFERENCES Organizations LABEL ASSIGNED_TO,
        Issues AS LocatedIn DESTINATION KEY (DistrictId) REFERENCES Districts LABEL LOCATED_IN,
        Issues AS HasCategory DESTINATION KEY (CategoryId) REFERENCES IssueCategories LABEL HAS_CATEGORY,
        Reports AS RelatesToIssue DESTINATION KEY (IssueId) REFERENCES Issues LABEL RELATES_TO,
        Reports AS SubmittedBy DESTINATION KEY (ReporterId) REFERENCES Users LABEL SUBMITTED_BY,
        Reports AS IdentifiedIn DESTINATION KEY (SegmentId) REFERENCES VideoSegments LABEL IDENTIFIED_IN,
        IssueUpvotes AS Upvoted SOURCE KEY (UserId) REFERENCES Users DESTINATION KEY (IssueId) REFERENCES Issues LABEL UPVOTED,
        VideoSegments AS SegmentOf DESTINATION KEY (VideoId) REFERENCES Videos LABEL EXTRACTED_FROM,
        OrgDistricts AS OperatesIn SOURCE KEY (OrgId) REFERENCES Organizations DESTINATION KEY (DistrictId) REFERENCES Districts LABEL OPERATES_IN,
        UserDistricts AS LivesIn SOURCE KEY (UserId) REFERENCES Users DESTINATION KEY (DistrictId) REFERENCES Districts LABEL LIVES_IN,
        UserInterests AS InterestedIn SOURCE KEY (UserId) REFERENCES Users DESTINATION KEY (CategoryId) REFERENCES IssueCategories LABEL INTERESTED_IN
    );


-- ==========================================
-- DML: SEED DATA (SAN FRANCISCO HACKATHON)
-- ==========================================

-- 1. Districts & Categories
INSERT INTO Districts (DistrictId, Name) VALUES
('dist-tenderloin', 'Tenderloin'),
('dist-mission', 'Mission District'),
('dist-embarcadero', 'Embarcadero / Pier 39'),
('dist-soma', 'SOMA');

INSERT INTO IssueCategories (CategoryId, DisplayName) VALUES
('GARBAGE_WASTE', 'Garbage & Waste'),
('BIOHAZARD', 'Biohazard / Needles / Human Feces'),
('HOMELESS_OUTREACH', 'Homeless Outreach / Encampment'),
('PERSON_IN_DISTRESS', 'Person in Distress'),
('ANIMAL_WASTE', 'Dog Poop / Animal Waste'),
('STREET_LIGHT_POTHOLE', 'Street Light / Pothole');

-- 2. Organizations
INSERT INTO Organizations (OrgId, Name, OrgType, Capabilities) VALUES
('org-dpw-09', 'DPW / RECOLOGY', 'CITY_AGENCY', ['GARBAGE', 'HEAVY_LIFTING', 'BIOHAZARD', 'ANIMAL_WASTE']),
('org-hot-soma', 'Homeless Outreach Team (HOT-SOMA)', 'COMMUNITY_GROUP', ['SOCIAL_SERVICES', 'MEDICAL_RESPONSE', 'SHELTER_ROUTING']),
('org-tenderloin-care', 'Tenderloin Care Providers', 'COMMUNITY_GROUP', ['NEEDLE_CLEANUP', 'SOCIAL_SERVICES', 'PERSON_IN_DISTRESS']),
('org-mission-food', 'Mission Food & Housing Network', 'COMMUNITY_GROUP', ['FOOD_DISTRIBUTION', 'NECESSITY_PACKS']),
('org-muni-fix', 'SF-MUNI-FIX', 'CITY_AGENCY', ['ELECTRICAL', 'ROAD_REPAIR', 'SIGNAL_MAINTENANCE']),
('org-pier-maint', 'Port of SF Maintenance', 'CITY_AGENCY', ['PIER_CLEANUP', 'TOURIST_AREA_MAINTENANCE']);

INSERT INTO OrgDistricts (OrgId, DistrictId) VALUES
('org-tenderloin-care', 'dist-tenderloin'),
('org-mission-food', 'dist-mission'),
('org-hot-soma', 'dist-soma'),
('org-hot-soma', 'dist-tenderloin'),
('org-pier-maint', 'dist-embarcadero');

-- 3. Users (Developer Team & AI)
INSERT INTO Users (UserId, Name, Role, IsAnonymous, CreatedAt) VALUES
('user-ai-vision', 'CivicGuardian Vision System', 'AI_SYSTEM', false, CURRENT_TIMESTAMP()),
('user-anon-guest', 'Guest User', 'CITIZEN', true, CURRENT_TIMESTAMP()),
('user-dev-adit', 'Adit', 'PARTNER', false, CURRENT_TIMESTAMP()),
('user-dev-csaba', 'Csaba', 'PARTNER', false, CURRENT_TIMESTAMP()),
('user-dev-chili', 'Chili', 'PARTNER', false, CURRENT_TIMESTAMP()),
('user-dev-pryanka', 'Pryanka', 'PARTNER', false, CURRENT_TIMESTAMP());

-- Personalization Auto-Learning Setup
INSERT INTO UserDistricts (UserId, DistrictId) VALUES
('user-dev-csaba', 'dist-mission'),
('user-dev-pryanka', 'dist-tenderloin');

INSERT INTO UserInterests (UserId, CategoryId) VALUES
('user-dev-adit', 'HOMELESS_OUTREACH'),
('user-dev-chili', 'BIOHAZARD');

-- 4. Unified Issues (Tenderloin, Mission, Piers)
INSERT INTO Issues (IssueId, CategoryId, DistrictId, Severity, Location, Status, CreatedAt, AssignedOrgId) VALUES
('iss-tl-needle-1', 'BIOHAZARD', 'dist-tenderloin', 'HIGH', ST_GEOGPOINT(-122.4167, 37.7833), 'NEW', TIMESTAMP '2026-03-21T10:00:00Z', NULL),
('iss-tl-distress-1', 'PERSON_IN_DISTRESS', 'dist-tenderloin', 'CRITICAL', ST_GEOGPOINT(-122.4140, 37.7840), 'IN_PROGRESS', TIMESTAMP '2026-03-21T11:00:00Z', 'org-tenderloin-care'),
('iss-mission-encamp-1', 'HOMELESS_OUTREACH', 'dist-mission', 'MEDIUM', ST_GEOGPOINT(-122.4190, 37.7600), 'NEW', TIMESTAMP '2026-03-21T13:00:00Z', 'org-mission-food'),
('iss-mission-poop-1', 'ANIMAL_WASTE', 'dist-mission', 'LOW', ST_GEOGPOINT(-122.4210, 37.7620), 'RESOLVED', TIMESTAMP '2026-03-21T09:00:00Z', 'org-dpw-09'),
('iss-pier-trash-1', 'GARBAGE_WASTE', 'dist-embarcadero', 'MEDIUM', ST_GEOGPOINT(-122.4100, 37.8080), 'NEW', TIMESTAMP '2026-03-21T14:00:00Z', 'org-pier-maint'),
('iss-soma-pothole-1', 'STREET_LIGHT_POTHOLE', 'dist-soma', 'MEDIUM', ST_GEOGPOINT(-122.4000, 37.7810), 'VERIFIED', TIMESTAMP '2026-03-21T08:00:00Z', 'org-muni-fix');

-- 5. Temporal Aspect: Issue Episodes (Graphity style)
INSERT INTO IssueEpisodes (IssueId, EpisodeId, ActorId, PreviousStatus, NewStatus, Comment, EpisodeTimestamp) VALUES
('iss-tl-needle-1', 'ep-1', 'user-ai-vision', NULL, 'NEW', 'Discarded paraphrase/needles detected via street sweep.', TIMESTAMP '2026-03-21T10:00:00Z'),
('iss-tl-distress-1', 'ep-2', 'user-dev-pryanka', NULL, 'NEW', 'Man lying motionless on the sidewalk near Ellis st.', TIMESTAMP '2026-03-21T11:00:00Z'),
('iss-tl-distress-1', 'ep-3', 'user-dev-adit', 'NEW', 'IN_PROGRESS', 'Tenderloin Care Providers dispatched for welfare check.', TIMESTAMP '2026-03-21T11:15:00Z'),
('iss-mission-encamp-1', 'ep-4', 'user-ai-vision', NULL, 'NEW', 'Encampment identified. 2 Tents.', TIMESTAMP '2026-03-21T13:00:00Z'),
('iss-mission-poop-1', 'ep-5', 'user-dev-csaba', NULL, 'NEW', 'Stepped in dog poop. DPW please.', TIMESTAMP '2026-03-21T09:00:00Z'),
('iss-mission-poop-1', 'ep-6', 'user-dev-csaba', 'IN_PROGRESS', 'RESOLVED', 'Cleaned up by street sweeper.', TIMESTAMP '2026-03-21T09:45:00Z'),
('iss-pier-trash-1', 'ep-7', 'user-dev-chili', NULL, 'NEW', 'Overflowing trash cans at Pier 39 entrance.', TIMESTAMP '2026-03-21T14:00:00Z'),
('iss-soma-pothole-1', 'ep-pot-1', 'user-ai-vision', NULL, 'NEW', 'Deep pothole detected on 3rd St by Waymo AV camera.', TIMESTAMP '2026-03-21T08:00:00Z'),
('iss-soma-pothole-1', 'ep-pot-2', 'user-dev-adit', 'NEW', 'IN_PROGRESS', 'Dispatching MUNI-FIX road repair crew.', TIMESTAMP '2026-03-21T09:00:00Z'),
('iss-soma-pothole-1', 'ep-pot-3', 'user-dev-csaba', 'IN_PROGRESS', 'RESOLVED', 'Crew filled pothole with cold patch asphalt.', TIMESTAMP '2026-03-21T14:00:00Z'),
('iss-soma-pothole-1', 'ep-pot-4', 'user-ai-vision', 'RESOLVED', 'VERIFIED', 'Follow-up Waymo AV drive-by confirmed surface is smooth.', TIMESTAMP '2026-03-21T18:00:00Z');

-- 6. Upvotes (Deduplicated Human priority)
INSERT INTO IssueUpvotes (IssueId, UserId, UpvotedAt) VALUES
('iss-tl-needle-1', 'user-dev-pryanka', TIMESTAMP '2026-03-21T10:15:00Z'),
('iss-mission-encamp-1', 'user-dev-csaba', TIMESTAMP '2026-03-21T13:30:00Z'),
('iss-pier-trash-1', 'user-anon-guest', TIMESTAMP '2026-03-21T14:10:00Z');

-- 7. Videos & Telemetry
INSERT INTO Videos (VideoId, SourceDevice, GcsUri, CaptureStartTime, CaptureEndTime, UploadedAt) VALUES
('vid-waymo-tl-1', 'WAYMO_AV_TL', 'gs://civic-aurai/waymo_tl.mp4', TIMESTAMP '2026-03-21T09:50:00Z', TIMESTAMP '2026-03-21T10:10:00Z', CURRENT_TIMESTAMP()),
('vid-waymo-soma-1', 'WAYMO_AV_SOMA', 'gs://civic-aurai/waymo_soma_morning.mp4', TIMESTAMP '2026-03-21T07:50:00Z', TIMESTAMP '2026-03-21T08:10:00Z', CURRENT_TIMESTAMP()),
('vid-waymo-soma-2', 'WAYMO_AV_SOMA', 'gs://civic-aurai/waymo_soma_evening.mp4', TIMESTAMP '2026-03-21T17:50:00Z', TIMESTAMP '2026-03-21T18:10:00Z', CURRENT_TIMESTAMP());

-- 8. Video Segments & Reports
INSERT INTO VideoSegments (SegmentId, VideoId, StartTimeOffset, EndTimeOffset, AiSummary, GcsUri) VALUES
('seg-tl-needle-1', 'vid-waymo-tl-1', 450.0, 455.5, 'Biohazard: needles and paraphernalia detected on sidewalk.', 'gs://civic-aurai/seg_tl_needle.mp4'),
('seg-soma-pothole-1', 'vid-waymo-soma-1', 120.0, 125.5, 'Pothole detected in middle lane.', 'gs://civic-aurai/seg_soma_pothole_1.mp4'),
('seg-soma-pothole-2', 'vid-waymo-soma-2', 340.0, 345.5, 'Pothole previously reported is now filled and leveled.', 'gs://civic-aurai/seg_soma_pothole_2.mp4');

INSERT INTO Reports (ReportId, IssueId, ReporterId, SegmentId, SourceType, Description, AiMetadata, ReportedAt) VALUES
('rep-001', 'iss-tl-needle-1', 'user-ai-vision', 'seg-tl-needle-1', 'AI_VISION', 'AI discovered needles during Tenderloin sweep.', '{"confidence": 0.95}', TIMESTAMP '2026-03-21T10:00:00Z'),
('rep-002', 'iss-tl-distress-1', 'user-dev-pryanka', NULL, 'CITIZEN_APP', 'Person needs medical attention or housing help.', NULL, TIMESTAMP '2026-03-21T11:00:00Z'),
('rep-003', 'iss-soma-pothole-1', 'user-ai-vision', 'seg-soma-pothole-1', 'AI_VISION', 'Initial detection of pothole by Waymo AV.', '{"confidence": 0.92}', TIMESTAMP '2026-03-21T08:00:00Z'),
('rep-004', 'iss-soma-pothole-1', 'user-ai-vision', 'seg-soma-pothole-2', 'AI_VISION', 'Visual confirmation of completed repair by Waymo AV.', '{"confidence": 0.98, "repair_quality": "good"}', TIMESTAMP '2026-03-21T18:00:00Z');
