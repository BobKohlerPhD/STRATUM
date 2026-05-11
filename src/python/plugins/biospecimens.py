import pandas as pd
from pathlib import Path
from src.python.core.harmonizer import BaseHarmonizer

class BiospecimenHarmonizer(BaseHarmonizer):
    """
    Standard Plugin for Biological Specimen Handling.
    Processes Laboratory Information Management System (LIMS) extracts,
    blood panel readouts, and biobank catalog sheets.
    
    Non-BIDS modality: field names are mapped to BIDS-compatible names
    where a registry mapping exists. Unmapped fields are preserved with
    a 'nonstandard_' prefix.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        if source_path.suffix == '.csv':
            return pd.read_csv(source_path)
        else:
            self.logger.error(f"Unsupported biospecimen file format: {source_path.suffix}")
            return pd.DataFrame()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        # Dynamic modality tagging based on specimen type
        if 'specimen_type' in df.columns:
            specimen = str(df['specimen_type'].iloc[0]).lower()
            if 'blood' in specimen:
                df['modality_category'] = 'biospecimen_blood'
            elif 'saliva' in specimen:
                df['modality_category'] = 'biospecimen_saliva'
            elif 'urine' in specimen:
                df['modality_category'] = 'biospecimen_urine'
            elif 'csf' in specimen:
                 df['modality_category'] = 'biospecimen_csf'
            else:
                 df['modality_category'] = 'biospecimen_unknown'
        else:
            df['modality_category'] = 'biospecimen_unspecified'
        
        # Apply BIDS-first harmonization (preserve everything, rename non-BIDS)
        result = self.harmonize_columns(df)
            
        return result
