import json
import os

def generate_route(filename, start_lat, start_lon, lat_step, lon_step, heading, frames=40, start_ts=1774144614131):
    data = {"frames": []}
    ts = start_ts
    lat = start_lat
    lon = start_lon
    for i in range(frames):
        data["frames"].append({
            "timestamp": ts,
            "screenRotationDegrees": 0,
            "latitude": lat,
            "longitude": lon,
            "altitude": -17.0,
            "heading": heading,
            "headingAccuracy": 2.8,
            "horizontalAccuracy": 2.6,
            "verticalAccuracy": 1.8
        })
        ts += 200  # 200 ms per frame (5 FPS)
        lat += lat_step
        lon += lon_step
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)

out_dir = "/home/csaba/repos/AIML/CivicAurAI/CivicAurAI/synthetic"
os.makedirs(out_dir, exist_ok=True)

# Tenderloin video: driving North
generate_route(
    os.path.join(out_dir, "waymo_tl.json"), 
    37.7833, -122.4167, 
    0.00002, 0.0, 
    0.0
)

# SOMA video: driving South-East
generate_route(
    os.path.join(out_dir, "waymo_soma.json"), 
    37.7810, -122.4000, 
    -0.000015, 0.000015, 
    135.0
)

print("Generated waymo_tl.json and waymo_soma.json.")
