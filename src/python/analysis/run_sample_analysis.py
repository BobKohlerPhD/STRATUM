import pandas as pd
from pathlib import Path
import json
from typing import Dict, Any, List

def run_sample_analysis():
    """
    Sample script to demonstrate Advanced Analytics capabilities.
    """
    from src.python.analysis.cohort_explorer import CohortExplorer
    
    root = Path(".")
    explorer = CohortExplorer(root)
    
    print("--- STRATUM Advanced Analytics: Cohort Discovery ---")
    
    try:
        # 1. Discover participants with specific clinical profiles
        # Example: PHQ-9 > 5 (Mild Depression) OR specific biomarkers
        filters = {
            'clinical_survey_psychometrics.PHQ-9 Total Score': ('>', 5),
            'digital_biomarker_wearable.Device Brand': ('contains', 'apple')
        }
        
        matches = explorer.find_participants(filters)
        print(f"\n[1] Participants matching profile (PHQ9 > 5 & Apple Watch): {len(matches)}")
        if not matches.empty:
            print(matches[['participant_id', 'clinical_survey_psychometrics.PHQ-9 Total Score']].to_string(index=False))

        # 2. Get Statistical Summary for High-Impact Variables
        vars_to_analyze = [
            'clinical_survey_psychometrics.PHQ-9 Total Score',
            'clinical_survey_psychometrics.GAD-7 Total Score',
            'digital_biomarker_wearable.Heart Rate',
            'digital_biomarker_wearable.sleep_efficiency'
        ]
        stats = explorer.get_cohort_stats(vars_to_analyze)
        print("\n[2] Multi-modal Statistical Summary:")
        for var, data in stats.items():
            mean_val = data.get('mean', 'N/A')
            mean_str = f"{mean_val:.2f}" if isinstance(mean_val, (int, float)) else "N/A"
            print(f"  - {var}: Mean={mean_str}, Missing={data.get('missing_percent', 0):.1f}%")

        # 3. Correlation Discovery
        target = 'clinical_survey_psychometrics.PHQ-9 Total Score'
        corrs = explorer.list_correlations(target, threshold=0.1)
        print(f"\n[3] Variables correlating with {target}:")
        for var, val in corrs.items():
            print(f"  - {var}: {val:.3f}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    run_sample_analysis()
