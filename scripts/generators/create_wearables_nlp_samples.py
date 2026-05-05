import pandas as pd
import json
from pathlib import Path

def create_samples():
    # Wearable JSON
    wearable = {
        "participant_id": "sub-001",
        "visit_session": "ses-01",
        "device_brand": "apple_watch",
        "heart_rate_array": [60, 62, 59, 65, 70, 61, 58], # Mean ~ 62
        "sleep_stages_array": ["light", "deep", "deep", "rem", "light", "awake"] # Effic: 3/6 = 50%
    }
    with open("data/bronze/wearables/sub-001_ses-01_actigraphy.json", 'w') as f:
        json.dump(wearable, f)
        
    # NLP Note CSV
    nlp_data = {
        "participant_id": ["sub-001"],
        "visit_session": ["ses-01"],
        "clinical_note": ["Patient presents with acute anxiety and severe chronic insomnia. Vitals normal."]
    }
    pd.DataFrame(nlp_data).to_csv("data/bronze/ehr_notes/sub-001_ses-01_clinical_note.csv", index=False)

    print("Successfully generated Wearables and NLP sample files.")

if __name__ == '__main__':
    create_samples()
