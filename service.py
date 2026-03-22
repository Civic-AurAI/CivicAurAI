"""Main orchestrator — chunks video, analyzes with Gemini Vision,
uploads clips to GCS, stores results in Spanner (CivicAurAI schema)."""

from __future__ import annotations

import logging
import os
import sys

from analyzer import analyze_frames
from chunker import chunk_video
from config import config
from spanner_store import (
    ensure_seed_data,
    ensure_tables,
    insert_detection,
    insert_segment,
    insert_video,
)
from storage import upload_clip

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run(video_path: str, gps_json_path: str) -> None:
    """Run the hazard detection pipeline on a video file."""
    ensure_tables()
    ensure_seed_data()
    video_name = os.path.basename(video_path)

    logger.info("Starting pipeline for %s", video_name)

    # Create a single Video record for the whole file
    video_id = insert_video(video_name)

    for chunk in chunk_video(video_path, gps_json_path):
        # Upload every chunk's clip to GCS
        gcs_url = upload_clip(chunk.temp_clip_path, video_name, chunk.chunk_index)

        # VideoSegment for every chunk (audit trail)
        segment_id = insert_segment(video_id, chunk, gcs_url)

        # Analyze sampled frames from this chunk
        logger.info(
            "Analyzing chunk %d (%d frames, t=%s)",
            chunk.chunk_index, len(chunk.frames), chunk.start_time.isoformat(),
        )
        detections = analyze_frames(chunk.frames)
        hazards = [d for d in detections if d.confidence >= config.confidence_threshold]

        if hazards:
            for det in hazards:
                insert_detection(
                    video_id, segment_id, gcs_url, det,
                    chunk.gps_lat, chunk.gps_lon,
                )
                logger.info(
                    "HAZARD: %s — %s (confidence=%.2f, severity=%s) → %s",
                    det.hazard_type, det.description,
                    det.confidence, det.severity, gcs_url,
                )
        else:
            logger.info("Chunk %d: no hazards detected", chunk.chunk_index)

        # Clean up temp clip file
        try:
            os.remove(chunk.temp_clip_path)
        except OSError:
            pass

    logger.info("Pipeline finished for %s", video_name)


def main() -> None:
    """Entry point.

    Usage: python service.py <video.mp4> <gps_timestamps.json>
    """
    if len(sys.argv) < 3:
        print("Usage: python service.py <video.mp4> <gps_timestamps.json>")
        sys.exit(1)

    video_path = sys.argv[1]
    gps_json_path = sys.argv[2]

    run(video_path, gps_json_path)


if __name__ == "__main__":
    main()
