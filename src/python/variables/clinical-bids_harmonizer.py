import json
import pandas as pd
import argparse
import os
import logging
from datetime import datetime

# Set up logging for BIDS Ingestion
logger = logging.getLogger("STRATUM-BIDS")

def main():
    parser = argparse.ArgumentParser(description="STRATUM BIDS Harmonization Engine")
    parser.add_argument("sidecar_json", help="Path to the BIDS sidecar JSON file.")
    parser.add_argument("--registry", default="clinical_registry_master.csv", help="Master Registry for mapping.")
    parser.add_argument("--output", default="harmonized_bids_records.csv", help="Output CSV path.")

    args = parser.parse_args()

    if not os.path.exists(args.sidecar_json):
        print(f"Error: BIDS sidecar {args.sidecar_json} not found.")
        return

    with open(args.sidecar_json, 'r') as f:
        sidecar = json.load(f)

    print(f"Parsing BIDS Sidecar: {args.sidecar_json}...")

    # Load registry to identify mapped variables
    try:
        registry = pd.read_csv(args.registry)
        mapped_vars = registry['original_variable_name'].tolist()
    except Exception as e:
        print(f"Error loading registry: {e}")
        return

    data_rows = []
    
    # Extract mapped variables from sidecar
    for key, value in sidecar.items():
        if key in mapped_vars:
            # Handle potential list values by joining or taking first
            val = value[0] if isinstance(value, list) else value
            
            data_rows.append({
                'original_variable_name': key,
                'value': val,
                'timestamp': datetime.now().isoformat()
            })
            print(f" - Mapped BIDS field: {key} -> {val}")

    if not data_rows:
        print("Warning: No mapped variables found in sidecar.")
        return

    # Convert to DataFrame
    df_harmonized = pd.DataFrame(data_rows)
    
    # Pivot data so each variable is a column
    df_pivot = df_harmonized.pivot(index='timestamp', columns='original_variable_name', values='value').reset_index()
    
    # Extract subject ID from filename if possible (BIDS standard: sub-<label>_...)
    filename = os.path.basename(args.sidecar_json)
    if filename.startswith("sub-"):
        subject_id = filename.split("_")[0]
        df_pivot['participant_id'] = subject_id
    else:
        # Default or derived from somewhere else
        df_pivot['participant_id'] = "unknown_bids_subject"

    # Save
    df_pivot.to_csv(args.output, index=False)
    print(f"\nSUCCESS: Harmonized {len(data_rows)} BIDS data points into {args.output}")

if __name__ == "__main__":
    main()
