import pandas as pd
from pathlib import Path

def create_samples():
    # Clinical Survey Data
    assess1 = {
        "participant_id": ["sub-001"],
        "survey_name": ["Mental Health Battery Q1"],
        "phq9_total": [14.0],  # Moderate Depression
        "gad7_total": [10.0]   # Moderate Anxiety
    }
    pd.DataFrame(assess1).to_csv("data/bronze/assessments/sub-001_mh_survey.csv", index=False)
    
    # Biospecimen Data - Blood Panel
    bio1 = {
        "participant_id": ["sub-001"],
        "specimen_type": ["blood"],
        "blood_wbc": [7.5],  # 10^3/uL
        "collection_time": ["2026-04-16T10:00:00Z"]
    }
    pd.DataFrame(bio1).to_csv("data/bronze/biospecimens/sub-001_blood_draw.csv", index=False)
    
    # Biospecimen Data - Saliva 
    bio2 = {
        "participant_id": ["sub-001"],
        "specimen_type": ["saliva"],
        "saliva_cortisol": [12.4], # nmol/L
        "collection_time": ["2026-04-16T10:30:00Z"]
    }
    pd.DataFrame(bio2).to_csv("data/bronze/biospecimens/sub-001_saliva_swab.csv", index=False)

    print("Successfully generated Clinical Survey and Biospecimen sample files.")

if __name__ == '__main__':
    create_samples()
