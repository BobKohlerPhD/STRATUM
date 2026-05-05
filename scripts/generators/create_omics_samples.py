import pandas as pd
import os
from pathlib import Path

def create_samples():
    root = Path("data/bronze/genomics")
    root.mkdir(parents=True, exist_ok=True)
    
    # Genomics Sample
    genomics_data = {
        "participant_id": ["sub-001", "sub-001"],
        "rsid": ["rs12345", "rs67890"],
        "genotype": ["0/1", "1/1"],
        "chromosome": ["chr1", "chr19"]
    }
    pd.DataFrame(genomics_data).to_csv(root / "sub-001_variants.csv", index=False)
    
    # Proteomics Sample
    prot_root = Path("data/bronze/proteomics")
    prot_root.mkdir(parents=True, exist_ok=True)
    proteomics_data = {
        "participant_id": ["sub-001", "sub-001"],
        "protein_id": ["P01023", "P02768"],
        "abundance_level": [12.5, -1.2]
    }
    pd.DataFrame(proteomics_data).to_csv(prot_root / "sub-001_mass_spec_report.csv", index=False)
    
    # Metabolomics Sample
    metab_root = Path("data/bronze/metabolomics")
    metab_root.mkdir(parents=True, exist_ok=True)
    metabolomics_data = {
        "participant_id": ["sub-001", "sub-001"],
        "metabolite_name": ["Glucose", "Lactate"],
        "concentration_value": [5.5, 2.1]
    }
    pd.DataFrame(metabolomics_data).to_csv(metab_root / "sub-001_metabolite_panel.csv", index=False)
    
    print("Created Multi-Omics sample datasets.")

if __name__ == "__main__":
    create_samples()
