# CivicAurAI

Civic AuRAI monorepo for the backend services, web frontend, and AR mobile app. The platform aggregates civic reporting from citizen mobile apps and autonomous vehicle edge AI, utilizing Google Cloud Spanner to deduplicate and route incidents for civic organizations.

## Key Features
* **Spanner RDBMS & Property Graph**: Integrates Graphity-style temporal tables to track issues while exposing cross-node graph edges (`CivicGraph`) for routing incidents to localized civic organizations.
* **Native Geospatial Indexing**: Utilizes Spanner `GEOGRAPHY` data types and native `ST_DWITHIN` indexing for extremely fast proximity-based deduplication of visual hazard constraints.
* **Vector Search**: Embeds incident `VideoSegments` and `Reports` into a dense 768-D space using Vertex AI's Gemini 2 Embeddings (`text-embedding-004`).
* **Synthetic AV Pipelines**: Features fully synthetic telemetry (`.json`) simulation routes for Waymo tests in SF's Tenderloin and SOMA districts across pre-fix, during-fix, and post-fix states.

## Setup & Backfill
1. Place `.env` file credentials.
2. Initialize database schema and native geography layouts using the standard Spanner APIs.
3. Run `python seed_and_embed.py` to seed hackathon test data (`dist-tenderloin`, `dist-soma`) and automatically compute and backfill the vector embeddings via Vertex AI!
