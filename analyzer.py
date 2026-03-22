from __future__ import annotations

import json
import logging
import time

import cv2
import vertexai
from vertexai.generative_models import GenerativeModel, Part

from config import config
from models import FrameMeta, HazardDetection

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a city infrastructure inspection system analyzing dashcam video frames \
from an autonomous vehicle.

Your job is to identify hazards and infrastructure issues visible in these frames.

Look for:
- Potholes or road surface damage
- Debris, fallen objects, or obstructions on the road
- Damaged, missing, or obscured road signs
- Broken or non-functioning traffic lights
- Damaged guardrails or barriers
- Flooding or standing water on roads
- Fallen trees or branches in/near the roadway
- Damaged sidewalks or curbs
- Exposed utility covers or missing manhole covers
- Any other condition that poses a danger to drivers, cyclists, or pedestrians

For each issue found, respond ONLY with a JSON array. Each element must have:
{
  "hazard_type": "<category>",
  "description": "<1-2 sentence description of what you see and why it is dangerous>",
  "confidence": <float 0.0 to 1.0>,
  "severity": "<low|medium|high|critical>"
}

If no issues are visible, respond with an empty array: []

Rules:
- Be conservative: only flag things you are reasonably confident about (confidence > 0.6).
- Do NOT flag normal road wear, minor cracks, or cosmetic issues.
- Focus on things that pose actual safety risks.
- Respond ONLY with the JSON array, no other text."""

_initialized = False


def _ensure_init() -> None:
    global _initialized
    if not _initialized:
        vertexai.init(project=config.gcp_project_id, location=config.gcp_region)
        _initialized = True


def _frame_to_jpeg_bytes(frame: FrameMeta) -> bytes:
    """Encode an OpenCV frame as JPEG bytes."""
    _, buf = cv2.imencode(".jpg", frame.frame_image)
    return buf.tobytes()


def _parse_response(text: str) -> list[dict]:
    """Extract a JSON array from the model response text."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines[1:] if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


def analyze_frames(frames: list[FrameMeta]) -> list[HazardDetection]:
    """Send a batch of frames to Gemini Vision via Vertex AI and return detected hazards."""
    if not frames:
        return []

    _ensure_init()
    model = GenerativeModel(config.gemini_model)

    # Build multimodal content
    content: list = [SYSTEM_PROMPT]
    for i, frame in enumerate(frames):
        content.append(
            f"\nFrame {i + 1} — timestamp: {frame.timestamp.isoformat()}, "
            f"GPS: ({frame.gps_lat:.6f}, {frame.gps_lon:.6f}):"
        )
        content.append(Part.from_data(
            data=_frame_to_jpeg_bytes(frame),
            mime_type="image/jpeg",
        ))

    detections: list[HazardDetection] = []
    max_retries = 3

    for attempt in range(max_retries):
        try:
            response = model.generate_content(content)
            raw = _parse_response(response.text)

            for item in raw:
                det = HazardDetection(
                    hazard_type=item.get("hazard_type", "unknown"),
                    description=item.get("description", ""),
                    confidence=float(item.get("confidence", 0.0)),
                    severity=item.get("severity", "low"),
                    timestamp=frames[0].timestamp,
                    gps_lat=frames[0].gps_lat,
                    gps_lon=frames[0].gps_lon,
                    frame_index=frames[0].frame_index,
                )
                detections.append(det)
            break

        except json.JSONDecodeError:
            if attempt < max_retries - 1:
                logger.warning("JSON parse failed, retrying (attempt %d)", attempt + 1)
                content.append("\nPlease respond ONLY with a valid JSON array.")
                continue
            logger.error("Failed to parse Gemini response after %d attempts", max_retries)

        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "rate" in error_str or "quota" in error_str:
                wait = 2 ** (attempt + 1)
                logger.warning("Rate limited, waiting %ds (attempt %d)", wait, attempt + 1)
                time.sleep(wait)
                continue
            logger.error("Gemini API error: %s", e)
            break

    return detections
