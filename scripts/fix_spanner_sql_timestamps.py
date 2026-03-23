#!/usr/bin/env python3
import glob
import re
import os
import sys

def fix_timestamps(backup_dir):
    if not os.path.exists(backup_dir):
        print(f"Error: Directory {backup_dir} not found.")
        sys.exit(1)

    sql_files = glob.glob(os.path.join(backup_dir, "*.sql"))
    if not sql_files:
        print(f"No SQL files found in {backup_dir}")
        return

    # Matches a timezone like +00:00 or -07:00 immediately followed by Z'
    # E.g. +00:00Z' -> +00:00'
    pattern = re.compile(r'([+-]\d{2}:\d{2})Z\'')
    
    total_patched = 0
    for file_path in sql_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content, count = pattern.subn(r"\1'", content)
        
        if count > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Patched {count} invalid timestamp literals in {os.path.basename(file_path)}")
            total_patched += count
            
    print(f"Cleanup complete. Total invalid literals patched: {total_patched}")

if __name__ == "__main__":
    target_dir = sys.argv[1] if len(sys.argv) > 1 else "spanner_sql_backup_20260322_162807"
    fix_timestamps(target_dir)
