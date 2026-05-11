import json
import pandas as pd
from pathlib import Path
from src.python.core.harmonizer import BaseHarmonizer

class EEGBIDSHarmonizer(BaseHarmonizer):
    """
    BIDS-native plugin for EEG metadata harmonization.
    Handles EEG sidecar metadata (.json) in BIDS format.
    
    BIDS-First: ALL fields are preserved. BIDS field names are kept as-is
    since they ARE the standard. Any non-BIDS fields get prefixed with
    'nonstandard_' but are never dropped.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        if not source_path.suffix == '.json':
            self.logger.error(f"EEG BIDS metadata expected in .json format, got {source_path.suffix}")
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
        
        # Tag modality
        result['modality_category'] = 'eeg'
        
        return result
