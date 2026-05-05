import os
import sys
import subprocess
from pathlib import Path

# Add project root and src to path
# This script is now in scripts/setup/system_init.py
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.append(str(PROJECT_ROOT))

from src.python.core.engine import StratumEngine
from src.python.plugins.imaging_bids import BIDSHarmonizer
from src.python.plugins.converter_nibabel import NibabelConverter
from src.python.plugins.multi_omics import MultiOmicsHarmonizer
from src.python.plugins.clinical_assessments import ClinicalAssessmentHarmonizer
from src.python.plugins.biospecimens import BiospecimenHarmonizer
from src.python.plugins.wearables import WearableHarmonizer
from src.python.plugins.clinical_nlp import ClinicalNLPHarmonizer
from src.python.plugins.fmri_nilearn import fMRINilearnHarmonizer

def main():
    print("=== STRATUM Architecture: Federated Multi-Modal Data Engine ===")
    engine = StratumEngine(PROJECT_ROOT)
    
    # Register Plugins & Converters
    engine.register_plugin("bids", BIDSHarmonizer)
    engine.register_plugin("omics", MultiOmicsHarmonizer)
    engine.register_plugin("assessments", ClinicalAssessmentHarmonizer)
    engine.register_plugin("biospecimens", BiospecimenHarmonizer)
    engine.register_plugin("wearables", WearableHarmonizer)
    engine.register_plugin("nlp", ClinicalNLPHarmonizer)
    engine.register_plugin("fmri_signal", fMRINilearnHarmonizer)
    engine.register_converter(".nii", NibabelConverter())

    # Create samples if missing
    gen_dir = PROJECT_ROOT / "scripts" / "generators"
    if not (PROJECT_ROOT / "data" / "bronze" / "genomics" / "sub-001_variants.csv").exists():
        try:
            print(">>> Generating Synthetic Sample Data...")
            # Run generators from their new location
            for gen_script in gen_dir.glob("create_*.py"):
                subprocess.run(["python3", str(gen_script)], check=True, cwd=PROJECT_ROOT)
        except Exception as e:
            print(f"Sample generation failed: {e}")

    print("\n>>> Processing Multi-Modal Federated Data via Parallel Batching...")
    tasks = [
        ("bids", "imaging/sub-001_ses-01_task-rest_bold.json"),
        ("omics", "genomics/sub-001_variants.csv"),
        ("omics", "proteomics/sub-001_mass_spec_report.csv"),
        ("omics", "metabolomics/sub-001_metabolite_panel.csv"),
        ("assessments", "assessments/sub-001_mh_survey.csv"),
        ("biospecimens", "biospecimens/sub-001_blood_draw.csv"),
        ("biospecimens", "biospecimens/sub-001_saliva_swab.csv"),
        ("wearables", "wearables/sub-001_ses-01_actigraphy.json"),
        ("nlp", "ehr_notes/sub-001_ses-01_clinical_note.csv"),
        ("fmri_signal", "imaging/sub-001_ses-01_task-rest_bold.nii.gz")
    ]
    engine.batch_process(tasks)

    print("\n>>> Synchronizing Silver Tiers...")
    silver_files = list((PROJECT_ROOT / "data" / "silver").glob("harmonized_sub-001*.csv"))
    for f in silver_files:
        print(f" - Found Silver Asset: {f.name}")
        
    print("\n>>> Generating SOTA Gold Tier (Multi-Modal Cross-Join & Provenance Hashing)...")
    gold_df = engine.generate_gold_tier()
    if gold_df is not None:
        print("\nGold Tier Columns:")
        print(list(gold_df.columns))
        print(f"\nFinal Cohort Matrix Shape: {gold_df.shape}")

if __name__ == "__main__":
    main()
