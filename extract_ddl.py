#!/usr/bin/env python3
import os
import subprocess
from config import config

def extract_ddl():
    print(f"Extracting DDL for project {config.gcp_project_id}, instance {config.spanner_instance_id}, database {config.spanner_database_id}...")
    
    cmd = [
        "gcloud", "spanner", "databases", "ddl", "describe",
        config.spanner_database_id,
        f"--instance={config.spanner_instance_id}",
        f"--project={config.gcp_project_id}"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        with open("current_schema.sql", "w") as f:
            f.write(result.stdout)
        print("\nSUCCESS! DDL extracted to current_schema.sql")
    except subprocess.CalledProcessError as e:
        print("\nERROR extracting DDL:")
        print(e.stderr)

if __name__ == "__main__":
    extract_ddl()
