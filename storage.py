"""Upload video clips to Google Cloud Storage."""

from __future__ import annotations

import logging
import os

from google.cloud import storage

from config import config

logger = logging.getLogger(__name__)

_client = None


def _get_client() -> storage.Client:
    global _client
    if _client is None:
        _client = storage.Client(project=config.gcp_project_id)
    return _client


def upload_clip(local_path: str, source_video: str, chunk_index: int) -> str:
    """Upload a clip .mp4 to GCS.

    Args:
        local_path: Path to the local temp .mp4 file.
        source_video: Name of the source video (used in the GCS path).
        chunk_index: Index of the chunk within the source video.

    Returns:
        The gs:// URL of the uploaded clip.
    """
    client = _get_client()
    bucket = client.bucket(config.gcs_bucket_name)

    # Clean up source video name for use as a folder
    video_name = os.path.splitext(os.path.basename(source_video))[0]
    blob_name = f"{config.gcs_clips_prefix}{video_name}/{chunk_index}.mp4"

    blob = bucket.blob(blob_name)
    blob.upload_from_filename(local_path, content_type="video/mp4")

    gcs_url = f"gs://{config.gcs_bucket_name}/{blob_name}"
    logger.info("Uploaded clip to %s", gcs_url)
    return gcs_url
