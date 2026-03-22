from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # GCP
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"

    # Gemini Vision (Vertex AI)
    gemini_model: str = "gemini-2.5-flash"

    # Chunking
    chunk_duration_sec: float = 10.0
    sample_frames_per_chunk: int = 4

    # Cloud Storage
    gcs_bucket_name: str = ""
    gcs_clips_prefix: str = "clips/"

    # Spanner
    spanner_instance_id: str = ""
    spanner_database_id: str = ""

    # Detection
    confidence_threshold: float = 0.7

    # Deduplication (GPS + hazard type)
    dedup_radius_meters: float = 20.0
    dedup_enabled: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


config = Settings()
