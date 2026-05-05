import json
import pandas as pd
import argparse
import os
import logging
from datetime import datetime

# Set up logging for FHIR Ingestion
logger = logging.getLogger("STRATUM-FHIR")

def extract_patient_info(bundle):
    """Extracts basic patient identifiers from a FHIR bundle."""
    for entry in bundle.get('entry', []):
        resource = entry.get('resource', {})
        if resource.get('resourceType') == 'Patient':
            return {
                'subject_id': resource.get('id'),
                'gender': resource.get('gender'),
                'birthDate': resource.get('birthDate')
            }
    return {}

def extract_observations(bundle):
    """Extracts Observation resources and flattens them."""
    observations = []
    for entry in bundle.get('entry', []):
        resource = entry.get('resource', {})
        if resource.get('resourceType') == 'Observation':
            obs = {
                'code': resource.get('code', {}).get('coding', [{}])[0].get('code'),
                'display': resource.get('code', {}).get('coding', [{}])[0].get('display'),
                'value': resource.get('valueQuantity', {}).get('value'),
                'unit': resource.get('valueQuantity', {}).get('unit'),
                'date': resource.get('effectiveDateTime')
            }
            observations.append(obs)
    return observations

def main():
    parser = argparse.ArgumentParser(description="STRATUM FHIR Harmonization Engine")
    parser.add_argument("bundle_json", help="Path to the FHIR Bundle JSON file.")
    parser.add_argument("--registry", default="clinical_registry_master.csv", help="Master Registry for mapping.")
    parser.add_argument("--output", default="harmonized_clinical_records.csv", help="Output CSV path.")

    args = parser.parse_args()

    if not os.path.exists(args.bundle_json):
        print(f"Error: FHIR bundle {args.bundle_json} not found.")
        return

    with open(args.bundle_json, 'r') as f:
        bundle = json.load(f)

    print(f"Parsing FHIR Bundle: {args.bundle_json}...")

    # Subject Identification
    patient = extract_patient_info(bundle)
    subject_id = patient.get('subject_id', 'unknown_subject')
    
    # Observation Extraction
    observations = extract_observations(bundle)
    print(f" - Found {len(observations)} Observation resources.")

    # Mapping to STRATUM Registry
    # (Simplified: in a real system, we would have a lookup table for LOINC -> generalized_name)
    data_rows = []
    
    # Basic patient metadata row
    data_rows.append({
        'original_variable_name': 'subject_id',
        'value': subject_id,
        'timestamp': datetime.now().isoformat()
    })

    if patient.get('gender'):
        data_rows.append({
            'original_variable_name': 'biological_sex',
            'value': 1 if patient['gender'] == 'male' else 2, # Mapping to our registry levels
            'timestamp': datetime.now().isoformat()
        })

    for obs in observations:
        # Example: mapping LOINC '8867-4' (Heart rate) or similar
        # For demonstration, we use the display name as the original_variable_name if it exists
        var_name = obs['display'].lower().replace(" ", "_") if obs['display'] else obs['code']
        
        data_rows.append({
            'original_variable_name': var_name,
            'value': obs['value'],
            'timestamp': obs['date']
        })

    # Convert to DataFrame
    df_harmonized = pd.DataFrame(data_rows)
    
    # Pivot data so each variable is a column (standard STRATUM silver-tier format)
    df_pivot = df_harmonized.pivot(index='timestamp', columns='original_variable_name', values='value').reset_index()
    df_pivot['participant_id'] = subject_id

    # Save
    df_pivot.to_csv(args.output, index=False)
    print(f"\nSUCCESS: Harmonized {len(data_rows)} data points into {args.output}")

if __name__ == "__main__":
    main()
