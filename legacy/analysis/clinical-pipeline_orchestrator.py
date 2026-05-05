import subprocess
import os
import pandas as pd
from pathlib import Path

def run_step(name, cmd):
    print(f"\n>>> [REAL-L] STEP: {name}")
    print(f"Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"SUCCESS: {name}")
        if result.stdout:
            print(result.stdout.strip())
    else:
        print(f"FAILED: {name}")
        print(result.stderr)
        exit(1)

def main():
    # READ: Verify Registry Integrity
    run_step("READ (Integrity Check)", ["python3", "src/python/data_dictionary/registry_integrity_check.py"])
    
    # EVALUATE & ACT: Ingest FHIR
    run_step("ACT (FHIR Harmonization)", [
        "python3", "src/python/variables/clinical-fhir_harmonizer.py", 
        "sample_fhir_bundle.json", "--output", "harmonized_fhir.csv"
    ])
    
    # EVALUATE & ACT: Ingest BIDS
    # Rename sample to follow BIDS naming for ID extraction test
    bids_file = "sub-001_ses-01_task-rest_bold.json"
    if os.path.exists("sample_bids_sidecar.json"):
        os.rename("sample_bids_sidecar.json", bids_file)
        
    run_step("ACT (BIDS Harmonization)", [
        "python3", "src/python/variables/clinical-bids_harmonizer.py", 
        bids_file, "--output", "harmonized_bids.csv"
    ])
    
    # ACT: Merge and Redact (Simulating Silver -> Gold tier transition)
    print("\n>>> [REAL-L] STEP: Merge Tier (Silver)")
    df_fhir = pd.read_csv("harmonized_fhir.csv")
    df_bids = pd.read_csv("harmonized_bids.csv")
    
    # Simple merge on participant_id for demonstration
    df_merged = pd.concat([df_fhir, df_bids], axis=0, ignore_index=True)
    df_merged.to_csv("silver_merged_data.csv", index=False)
    print(f"Merged {len(df_merged)} records into silver_merged_data.csv")
    
    # ACT: Privacy Redaction
    run_step("ACT (Privacy Redaction)", [
        "python3", "src/python/data_dictionary/clinical-privacy_redactor.py", 
        "silver_merged_data.csv", "--epsilon", "0.05", "--output", "gold_redacted_data.csv"
    ])
    
    # VERIFY: Final automated summary
    run_step("VERIFY (Registry Summary)", ["python3", "src/python/data_dictionary/check_datadictionary_summary.py"])

    print("\n" + "="*40)
    print("STRATUM PIPELINE COMPLETE: Gold Tier Data Ready.")
    print("="*40)

if __name__ == "__main__":
    main()
