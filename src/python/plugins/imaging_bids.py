import json
import pandas as pd
from pathlib import Path
from src.python.core.harmonizer import BaseHarmonizer

class BIDSHarmonizer(BaseHarmonizer):
    """
    BIDS-native plugin for MRI metadata harmonization.
    Handles T1w (sMRI), DWI/DTI, MRS, and other MRI sidecar metadata (.json).
    
    BIDS-First: ALL fields are preserved. BIDS field names are kept as-is
    since they ARE the standard. Any non-BIDS fields get prefixed with
    'nonstandard_' but are never dropped.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        if not source_path.suffix == '.json':
            self.logger.error("BIDS metadata expected in .json format.")
            return pd.DataFrame()
            
        with open(source_path, 'r') as f:
            data = json.load(f)
        
        df = pd.DataFrame([data])
        
        # Extract BIDS entities (participant_id, session) from path
        entities = self.extract_bids_entities(source_path)
        for key, val in entities.items():
            df[key] = val
        
        return df

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        # Apply BIDS-first harmonization (preserve everything, rename non-BIDS)
        result = self.harmonize_columns(df)
        
        # Infer sub-modality from BIDS fields and filename
        modality = 'imaging_mri' # Default base
        
        # Check filename first for strong BIDS indicators
        source_name = str(self.logger.name).lower() # Class logger might have info, but better check source path
        
        # Use filename logic if possible
        desc = ""
        if 'SeriesDescription' in result.columns:
            desc = str(result['SeriesDescription'].iloc[0]).lower()
            
        # Refined Modality Inference
        if 'TracerName' in result.columns or '_pet' in desc:
            modality = 'imaging_pet'
        elif 'PostLabelingDelay' in result.columns or 'asl' in desc:
            modality = 'imaging_asl'
        elif 't1' in desc or 't2' in desc or 'anat' in desc:
            modality = 'structural_mri'
        elif 'bold' in desc or 'fmri' in desc:
            modality = 'functional_mri'
        elif 'dwi' in desc or 'diff' in desc or 'dti' in desc:
            modality = 'diffusion_mri'
        elif 'mrs' in desc or 'spec' in desc:
            modality = 'magnetic_resonance_spectroscopy'
        
        result['modality_category'] = modality
        return result
