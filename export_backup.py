#!/usr/bin/env python3
import os
import subprocess
import datetime
import json
import os
os.environ["SPANNER_DISABLE_BUILTIN_METRICS"] = "true"
from google.cloud import spanner

def load_env():
    """Manually parse .env to avoid external library dependencies like pydantic_settings"""
    env = {}
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    env[key] = val
    return env

def format_value(val):
    if val is None:
        return "NULL"
    if isinstance(val, str):
        val = val.replace("'", "''")
        return f"'{val}'"
    if isinstance(val, (int, float)):
        return str(val)
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            return f"TIMESTAMP '{val.isoformat()}Z'"
        else:
            return f"TIMESTAMP '{val.isoformat()}'"
    if isinstance(val, list):
        items = [format_value(v) for v in val]
        return f"[{', '.join(items)}]"
    if isinstance(val, dict):
        val_str = json.dumps(val).replace("'", "''")
        return f"JSON '{val_str}'"
    return f"'{str(val)}'"

def main():
    env = load_env()
    project = env.get('GCP_PROJECT_ID', 'waybackhome-qdtl7yj6kghd4u340n')
    instance_id = env.get('SPANNER_INSTANCE_ID', 'hazard-detection')
    database_id = env.get('SPANNER_DATABASE_ID', 'hazard-db')

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"spanner_sql_backup_{timestamp}"
    os.makedirs(backup_dir, exist_ok=True)

    print(f"Connecting to {project} -> {instance_id} -> {database_id}")
    
    print(f"\n1. Extracting DDL schema to {backup_dir}/00_schema.sql...")
    cmd = [
        "gcloud", "spanner", "databases", "ddl", "describe",
        database_id, f"--instance={instance_id}", f"--project={project}"
    ]
    try:
        ddl_result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        with open(os.path.join(backup_dir, "00_schema.sql"), "w") as f:
            f.write(ddl_result.stdout)
    except Exception as e:
        print("Failed to get DDL via gcloud. Check auth.", e)
        return

    print("2. Connecting to Spanner to extract data (DML) into separate .sql files...")
    client = spanner.Client(project=project)
    instance = client.instance(instance_id)
    database = instance.database(database_id)

    # Tables defined in topological dependency order
    tables = [
        "Districts", "IssueCategories", "Users", "Organizations",
        "Issues", "Videos", "IssueEpisodes", "VideoTelemetry",
        "IssueUpvotes", "VideoSegments", "Reports", "MediaBlobs",
        "UserDistricts", "UserInterests", "OrgDistricts"
    ]

    for idx, table in enumerate(tables, start=1):
        print(f"   -> Exporting rows from {table}...")
        try:
            with database.snapshot() as snapshot:
                results = snapshot.execute_sql(f"SELECT * FROM {table}")
                rows = list(results)
                
                file_name = f"{idx:02d}_{table}_data.sql"
                with open(os.path.join(backup_dir, file_name), "w") as f:
                    if not rows:
                        f.write(f"-- No data found in {table}\n")
                        continue
                        
                    fields = [f.name for f in results.fields]
                    cols_str = ", ".join(fields)
                    
                    batch = []
                    for row in rows:
                        vals = [format_value(val) for val in row]
                        val_str = ", ".join(vals)
                        insert_stmt = f"INSERT INTO {table} ({cols_str}) VALUES ({val_str});\n"
                        batch.append(insert_stmt)
                    
                    f.writelines(batch)
                    
        except Exception as e:
            print(f"      [!] Error querying table {table}: {e}")

    print(f"\nSUCCESS! Complete backup successfully written to directory: '{backup_dir}'")

if __name__ == "__main__":
    main()
