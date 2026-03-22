"""GPS timeline interpolation from JSON files."""

from __future__ import annotations

import bisect
import json
from datetime import datetime


class GpsTimeline:
    """Holds GPS+timestamp entries from a JSON file and interpolates
    GPS coordinates for any given timestamp.

    Supports two JSON formats:

    Format 1 (app recording):
    {"frames": [
      {"timestamp": 1774134410547, "latitude": 37.78, "longitude": -122.41, ...},
      ...
    ]}

    Format 2 (simple):
    [
      {"timestamp": "2026-03-21T10:00:00.000", "gps_lat": 40.7128, "gps_lon": -74.0060},
      ...
    ]
    """

    def __init__(self, entries: list[dict]):
        if not entries:
            raise ValueError("GPS timeline JSON is empty")

        self._times: list[float] = []  # seconds since epoch
        self._lats: list[float] = []
        self._lons: list[float] = []

        for entry in entries:
            if "latitude" in entry:
                ts_sec = float(entry["timestamp"]) / 1000.0
                self._times.append(ts_sec)
                self._lats.append(float(entry["latitude"]))
                self._lons.append(float(entry["longitude"]))
            else:
                ts = datetime.fromisoformat(entry["timestamp"])
                self._times.append(ts.timestamp())
                self._lats.append(float(entry["gps_lat"]))
                self._lons.append(float(entry["gps_lon"]))

        self.start_time: datetime = datetime.fromtimestamp(self._times[0])
        self.end_time: datetime = datetime.fromtimestamp(self._times[-1])

    def interpolate(self, ts: datetime) -> tuple[float, float]:
        """Return (lat, lon) for the given timestamp, interpolated between
        the two nearest GPS entries."""
        t = ts.timestamp()

        if t <= self._times[0]:
            return self._lats[0], self._lons[0]
        if t >= self._times[-1]:
            return self._lats[-1], self._lons[-1]

        idx = bisect.bisect_right(self._times, t)
        t0, t1 = self._times[idx - 1], self._times[idx]

        if t1 == t0:
            frac = 0.0
        else:
            frac = (t - t0) / (t1 - t0)

        lat = self._lats[idx - 1] + frac * (self._lats[idx] - self._lats[idx - 1])
        lon = self._lons[idx - 1] + frac * (self._lons[idx] - self._lons[idx - 1])
        return lat, lon

    @classmethod
    def from_file(cls, json_path: str) -> GpsTimeline:
        with open(json_path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict) and "frames" in data:
            data = data["frames"]
        return cls(data)
