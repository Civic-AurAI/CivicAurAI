"""Split a video into clip-sized chunks with GPS metadata."""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import timedelta
from typing import Iterator

import cv2
import numpy as np

from config import config
from ingest import GpsTimeline
from models import FrameMeta, VideoChunk

logger = logging.getLogger(__name__)


def chunk_video(video_path: str, gps_json_path: str) -> Iterator[VideoChunk]:
    """Split a video into fixed-duration chunks.

    For each chunk:
    - Writes a temp .mp4 clip file (to be uploaded to GCS)
    - Samples evenly-spaced frames for Gemini analysis
    - Interpolates GPS coordinates from the JSON timeline

    Yields VideoChunk objects.
    """
    gps = GpsTimeline.from_file(gps_json_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    chunk_frames = int(fps * config.chunk_duration_sec)

    logger.info(
        "Chunking %s: %.1f fps, %d total frames, %d frames/chunk",
        video_path, fps, total_frames, chunk_frames,
    )

    chunk_index = 0
    frame_index = 0

    while frame_index < total_frames:
        chunk_start_frame = frame_index
        chunk_end_frame = min(frame_index + chunk_frames, total_frames)

        # Calculate timestamps for this chunk
        start_elapsed = chunk_start_frame / fps
        end_elapsed = (chunk_end_frame - 1) / fps
        mid_elapsed = (start_elapsed + end_elapsed) / 2

        start_time = gps.start_time + timedelta(seconds=start_elapsed)
        end_time = gps.start_time + timedelta(seconds=end_elapsed)
        mid_time = gps.start_time + timedelta(seconds=mid_elapsed)

        # Interpolate GPS at chunk midpoint
        gps_lat, gps_lon = gps.interpolate(mid_time)

        # Determine which frames to sample for analysis
        n_chunk_frames = chunk_end_frame - chunk_start_frame
        sample_count = min(config.sample_frames_per_chunk, n_chunk_frames)
        if sample_count > 1:
            sample_indices = [
                chunk_start_frame + int(i * (n_chunk_frames - 1) / (sample_count - 1))
                for i in range(sample_count)
            ]
        else:
            sample_indices = [chunk_start_frame]
        sample_set = set(sample_indices)

        # Write chunk to temp file and collect sample frames
        temp_fd, temp_path = tempfile.mkstemp(suffix=".mp4")
        os.close(temp_fd)

        # Read first frame to get dimensions
        cap.set(cv2.CAP_PROP_POS_FRAMES, chunk_start_frame)
        ret, first_frame = cap.read()
        if not ret:
            os.remove(temp_path)
            break

        h, w = first_frame.shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"avc1")
        writer = cv2.VideoWriter(temp_path, fourcc, fps, (w, h))
        if not writer.isOpened():
            # Fallback: avc1 may not be available on all platforms
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(temp_path, fourcc, fps, (w, h))

        sampled_frames: list[FrameMeta] = []

        # Write first frame
        writer.write(first_frame)
        if chunk_start_frame in sample_set:
            frame_time = gps.start_time + timedelta(seconds=chunk_start_frame / fps)
            flat, flon = gps.interpolate(frame_time)
            sampled_frames.append(FrameMeta(
                frame_image=first_frame.copy(),
                timestamp=frame_time,
                gps_lat=flat,
                gps_lon=flon,
                frame_index=chunk_start_frame,
                source_path=video_path,
            ))

        # Write remaining frames in this chunk
        for fi in range(chunk_start_frame + 1, chunk_end_frame):
            ret, frame = cap.read()
            if not ret:
                break
            writer.write(frame)

            if fi in sample_set:
                frame_time = gps.start_time + timedelta(seconds=fi / fps)
                flat, flon = gps.interpolate(frame_time)
                sampled_frames.append(FrameMeta(
                    frame_image=frame.copy(),
                    timestamp=frame_time,
                    gps_lat=flat,
                    gps_lon=flon,
                    frame_index=fi,
                    source_path=video_path,
                ))

        writer.release()

        logger.info(
            "Chunk %d: frames %d-%d, %d sampled, GPS (%.6f, %.6f)",
            chunk_index, chunk_start_frame, chunk_end_frame - 1,
            len(sampled_frames), gps_lat, gps_lon,
        )

        yield VideoChunk(
            frames=sampled_frames,
            start_time=start_time,
            end_time=end_time,
            gps_lat=gps_lat,
            gps_lon=gps_lon,
            chunk_index=chunk_index,
            temp_clip_path=temp_path,
        )

        frame_index = chunk_end_frame
        chunk_index += 1

    cap.release()
    logger.info("Chunking complete: %d chunks produced", chunk_index)
