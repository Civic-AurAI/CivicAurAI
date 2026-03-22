# CivicAurAI - Spanner Graph & RDBMS Design Document

This document outlines the schema design for Cloud Spanner to support the Civic AurAI application. The system requires relational robustness for temporal constraints combined with elaborate Graph semantics for querying relationships and personalization routing.

## 1. High-Level Taxonomy
From the architectural specs, we can categorize our actors and actions into following domains:
1. **Core Entities (Graph Nodes):** `Users`, `Organizations`, `Districts`, `IssueCategories`.
2. **Issue Lifecycle:** `Issues` (unified problems), `Reports` (instances of a bug being noticed).
3. **Media & Telemetry:** `Videos` (raw feeds), `VideoSegments` (clipped splits), `MediaBlobs` (GCS Blob References).
4. **Temporal Tracking (Episodes):** `IssueEpisodes` (Interleaved within Issues, following Graphity temporal modeling), `VideoTelemetry` (Interleaved within Videos).

## 2. Temporal Handling & De-Duplication
- **The "Snooze" & Resolution Flow (Episodes):** We don't simply overwrite an `Issue` status. We manage it through the fully chronological `IssueEpisodes` RDBMS table. This adopts the Graphity temporal modeling approach, where each change in state or significant update is appended as an "Episode" in the issue's lifecycle.
- **Merging AI vs Human Reports:** AI identifies the `VideoSegment` and generates a `Report`. An hour later, a citizen reports the same pile of trash via the mobile app (`Report`). Through Geo-proximity + Semantic similarity matching, these two independent `Reports` point to the exact same *unified* `Issue`.
- **The "+1" / Upvote Priority Mechanic:** To prevent autonomous vehicles from artificially inflating the priority of an issue simply by repeatedly driving past it, priority amplification (+1s) is restricted to manual human entries (Citizens and City Workers). This is securely modeled via the `IssueUpvotes` interleaved table.

## 3. Personalization & Graph Routing
The schema auto-personalizes and improves routing by establishing relationship edges dynamically:
- **Organization Service Areas:** `(Organizations)-[:OPERATES_IN]->(Districts)`. The system learns if a specific civic group strictly handles issues within its boundaries.
- **User Location & Interests:** `(Users)-[:LIVES_IN]->(Districts)` and `(Users)-[:INTERESTED_IN]->(IssueCategories)`. Allows the app feed to highlight nearby issues or issues the user cares about.

## 4. Spanner Property Graph (CivicGraph)
**Nodes:** `Users`, `Organizations`, `Districts`, `IssueCategories`, `Issues`, `Videos`, `VideoSegments`, `IssueEpisodes`, `VideoTelemetry`, `Reports`, `MediaBlobs`

**Edges:**
- `HAS_CATEGORY`, `LOCATED_IN`, `ASSIGNED_TO`, `EXTRACTED_FROM`, `EPISODE_OF`, `ACTED_BY`, `TELEMETRY_OF`, `RELATES_TO`, `SUBMITTED_BY`, `IDENTIFIED_IN`, `BLOB_OF`, `LIVES_IN`, `INTERESTED_IN`, `OPERATES_IN`, `UPVOTED`.

### Example Spanner GQL Queries

**Query 1: Agency View - List all issues an Organization can handle in their District**
*Find unresolved "Biohazard" and "Encampment" issues specifically located in the districts where the humanitarian organization operates.*
```cypher
GRAPH CivicGraph
MATCH (org:Organizations {Name: 'Tenderloin Care Providers'})-[:OPERATES_IN]->(d:Districts)<-[:LOCATED_IN]-(i:Issues)
WHERE i.Status IN ('NEW', 'OPEN', 'IN_PROGRESS')
  AND i.CategoryId IN ('BIOHAZARD', 'HOMELESS_OUTREACH')
RETURN i.IssueId, i.CategoryId, i.Latitude, i.Longitude
ORDER BY i.CreatedAt DESC
```

**Query 2: Matchmaking / Ranking Organizations for a Specific Issue**
*Find the best organizations to handle an Illegal Dumping issue in the Mission, prioritizing those who specifically operate in the Mission and have 'HEAVY_LIFTING' capabilities.*
```cypher
GRAPH CivicGraph
MATCH (i:Issues {IssueId: 'iss-mission-dumping'})-[:LOCATED_IN]->(d:Districts)<-[:OPERATES_IN]-(org:Organizations)
WHERE 'HEAVY_LIFTING' IN UNNEST(org.Capabilities)
RETURN org.Name, org.OrgType
```

**Query 3: Tracing the Origin of an AI Detection (Video Chain of Custody)**
*Trace an exact AI proof snippet back to the source video and determine which vehicle/system uploaded it.*
```cypher
GRAPH CivicGraph
MATCH (mb:MediaBlobs {MediaId: 'target-blob-id'})-[:BLOB_OF]->(r:Reports)
      -[:IDENTIFIED_IN]->(vs:VideoSegments)
      -[:EXTRACTED_FROM]->(v:Videos)
      -[:UPLOADED_BY]->(u:Users)
RETURN v.SourceDevice, v.UploadedAt, u.Name as UploadingSystem, vs.StartTimeOffset, vs.AiSummary
```

**Query 4: Temporal Episode Timeline with Actor Context**
*Fetch the full chronological history of a specific Issue, tracking exactly who executed which status transitions.*
```cypher
GRAPH CivicGraph
MATCH (i:Issues {IssueId: 'iss-soma-pothole'})<-[:EPISODE_OF]-(ep:IssueEpisodes)
OPTIONAL MATCH (ep)-[:ACTED_BY]->(actor:Users)
RETURN ep.EpisodeTimestamp, ep.PreviousStatus, ep.NewStatus, ep.Comment, actor.Name as ActorName
ORDER BY ep.EpisodeTimestamp ASC
```

**Query 5: Assessing Community Priority vs AI Consensus**
*Observe how many distinct human upvotes align with AI-generated reports on a single problem.*
```cypher
GRAPH CivicGraph
MATCH (i:Issues {Status: 'NEW'})
OPTIONAL MATCH (voter:Users)-[:UPVOTED]->(i)
OPTIONAL MATCH (reporter:Users)<-[:SUBMITTED_BY]-(r:Reports)-[:RELATES_TO]->(i)
RETURN i.IssueId, count(DISTINCT voter.UserId) AS HumanUpvotes, count(DISTINCT r.ReportId) AS AI_or_User_Reports
ORDER BY HumanUpvotes DESC
```
