# CivicAurAI - Spanner Graph & RDBMS Design Document

This document outlines the schema design for Cloud Spanner to support the Civic AurAI application. The system requires relational robustness for temporal constraints combined with Graph semantics for querying relationships and personalization routing.

## 1. High-Level Taxonomy
From the architectural specs, we can categorize our actors and actions into following domains:
1. **Core Entities (Graph Nodes):** `Users`, `Organizations`, `Districts`, `IssueCategories`.
2. **Issue Lifecycle:** `Issues` (unified problems), `Reports` (instances of a bug being noticed).
3. **Media & Telemetry:** `Videos` (raw feeds), `VideoSegments` (clipped splits), `MediaBlobs` (GCS Blob References).
4. **Temporal Tracking (Episodes):** `IssueEpisodes` (Interleaved within Issues, following Graphity temporal modeling), `VideoTelemetry` (Interleaved within Videos).

## 2. Temporal Handling & De-Duplication
- **The "Snooze" & Resolution Flow (Episodes):** We don't simply overwrite an `Issue` status. We manage it through the fully chronological `IssueEpisodes` RDBMS table. This adopts the Graphity temporal modeling approach, where each change in state or significant update is appended as an "Episode" in the issue's lifecycle.
- **Merging AI vs Human Reports:** AI identifies the `VideoSegment` and generates a `Report`. An hour later, a citizen reports the same pile of trash via the mobile app (`Report`). Through **native Spanner `GEOGRAPHY` spatial indexing (`ST_DWITHIN`)** combined with semantic similarity matching, these two independent `Reports` point to the exact same *unified* `Issue` without fetching payload coordinates back to Python.
- **The "+1" / Upvote Priority Mechanic:** To prevent autonomous vehicles from artificially inflating the priority of an issue simply by repeatedly driving past it, priority amplification (+1s) is restricted to manual human entries (Citizens and City Workers). This is modeled securely via an `IssueUpvotes` table that tracks the `UserId`.

## 3. Personalization & Graph Routing
The schema auto-personalizes and improves routing by establishing relationship edges automatically over time (or via explicit user settings):
- **Organization Service Areas:** `(Organizations)-[:OPERATES_IN]->(Districts)`. The system learns if a specific civic group (e.g., Tenderloin Care Providers) strictly handles issues within its boundaries.
- **User Location & Interests:** `(Users)-[:LIVES_IN]->(Districts)` and `(Users)-[:INTERESTED_IN]->(IssueCategories)`. Allows the app feed to highlight nearby issues or issues the user cares about (e.g., a user heavily involved in reporting and upvoting "Homeless Outreach" gets personalized feed ranking).

## 4. Spanner Property Graph (CivicGraph)
**Nodes:** `Users, Organizations, Issues, Videos, VideoSegments, Reports, MediaBlobs, Districts, IssueCategories`

### Example Spanner GQL Queries

**Query 1: Agency View - List all issues an Organization can handle in their District**
*Find unresolved "Biohazard/Needle" and "Encampment" issues specifically located in the districts where the humanitarian organization operates.*
```cypher
GRAPH CivicGraph
MATCH (org:Organizations {Name: 'Tenderloin Care Providers'})-[:OPERATES_IN]->(d:Districts)<-[:LOCATED_IN]-(i:Issues)
WHERE i.Status IN ['NEW', 'OPEN', 'IN_PROGRESS']
  AND i.CategoryId IN ['BIOHAZARD', 'HOMELESS_OUTREACH']
RETURN i.IssueId, i.CategoryId, i.Location
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

## 5. Vector Search & Semantic Embeddings
To augment standard spatial mapping, CivicAurAI leverages Vertex AI's Gemini Embeddings (`text-embedding-004`).
During database ingestion (via `seed_and_embed.py`), any AI-analyzed `VideoSegments` and user-submitted `Reports` containing descriptive contexts have vector embeddings computed dynamically.

- **Storage**: Vectors are stored natively in Spanner as `ARRAY<FLOAT64>` columns (`Embedding`).
- **Semantic Search**: This allows similarity searching such that an autonomous vehicle recording an unstructured scene representation logically intersects with an existing `Issue` report that has varying linguistic traits.
