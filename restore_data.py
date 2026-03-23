#!/usr/bin/env python3
import os
import glob
os.environ["SPANNER_DISABLE_BUILTIN_METRICS"] = "true"
from google.cloud import spanner

def load_env():
    env = {}
    if os.path.exists('.env'):
        with open('.env') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    env[key] = val
    return env

def main():
    env = load_env()
    project = env.get('GCP_PROJECT_ID', 'waybackhome-t3nafn8idj7dzub9t5')
    instance_id = env.get('SPANNER_INSTANCE_ID', 'hazard-detection')
    database_id = env.get('SPANNER_DATABASE_ID', 'hazard-db')

    print(f"Restoring Data into Project: {project} -> {instance_id} -> {database_id}")
    
    client = spanner.Client(project=project)
    instance = client.instance(instance_id)
    database = instance.database(database_id)

    # Use the specific backup specified
    backup_dir = "spanner_sql_backup_20260322_162807"
    sql_files = sorted(glob.glob(os.path.join(backup_dir, "*_data.sql")))

    for file_path in sql_files:
        print(f" -> Processing {os.path.basename(file_path)}...")
        with open(file_path, 'r') as f:
            content = f.read()

        statements = [s.strip() for s in content.split(';') if s.strip() and not s.strip().startswith("--")]
        if not statements:
            continue

        success_count = 0
        for stmt in statements:
            def execute_single(transaction, sql_stmt):
                transaction.execute_update(sql_stmt)
            
            try:
                database.run_in_transaction(execute_single, stmt)
                success_count += 1
            except Exception as e:
                err_str = str(e)
                if "Already exists" not in err_str and "409" not in err_str:
                    print(f"      [!] Error executing insert: {err_str[:120]}")
        
        if success_count > 0:
            print(f"    Successfully drove {success_count} isolated insert transactions.")

    print("\nData Import Component Completed!")

if __name__ == "__main__":
    main()
