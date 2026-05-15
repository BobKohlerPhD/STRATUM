import pandas as pd
from pathlib import Path
from src.python.core.harmonizer import BaseHarmonizer

class ClinicalAssessmentHarmonizer(BaseHarmonizer):
    """
    Standard Plugin for Clinical Assessment and Survey Data.
    Handles data from external survey tools like REDCap, Qualtrics, or native CRFs.
    
    Standard modality: field names are mapped to registry-standard names
    where a registry mapping exists. Unmapped fields are preserved with
    a 'nonstandard_' prefix.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        if source_path.suffix == '.csv':
             return pd.read_csv(source_path)
        else:
             self.logger.error(f"Unsupported survey format: {source_path.suffix}")
             return pd.DataFrame()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        # Standardize Modality Tagging
        if 'phq9_total' in df.columns or 'gad7_total' in df.columns:
             df['modality_category'] = 'clinical_survey_psychometrics'
        else:
             df['modality_category'] = 'clinical_survey_general'
        
        # Apply registry-standard harmonization (preserve everything, rename mapped fields)
        result = self.harmonize_columns(df)
             
        return result
