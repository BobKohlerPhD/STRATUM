import pandas as pd
from pathlib import Path
import nibabel as nib
import numpy as np
from src.python.core.harmonizer import BaseHarmonizer

class fMRINilearnHarmonizer(BaseHarmonizer):
    """
    Computational plug-in for fMRI BOLD signal processing.
    Ingests a 4D fMRI NIfTI, processes the BOLD signals across time,
    and extracts the global amplitude as a derived feature.
    
    BIDS-First: Output features are preserved alongside any BIDS metadata.
    Computed fields use BIDS-compatible naming where applicable.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        if not str(source_path).endswith('.nii') and not str(source_path).endswith('.nii.gz'):
            self.logger.error(f"fMRI Nilearn requires a NIfTI file, got: {source_path}")
            return pd.DataFrame()
            
        self.logger.info(f"Nilearn Engine computing BOLD amplitudes for {source_path.name}...")
        try:
            # Load the 4D fMRI data
            img = nib.load(str(source_path))
            data = img.get_fdata()
            
            # For demonstration: We compute a global mean timeseries (taking mean across spatial dimensions)
            # For a more advanced implementation, we'd use nilearn.maskers.NiftiMasker with a brain mask
            # data shape is (x, y, z, time)
            if len(data.shape) == 4:
                global_timeseries = np.mean(data, axis=(0, 1, 2))
                
                # We calculate the amplitude (Standard Deviation of the BOLD signal)
                fmri_amplitude = np.std(global_timeseries)
                
                row = {
                    "fmri_amplitude": fmri_amplitude,
                    "modality_category": "functional_mri_bold_signal"
                }
                
                # Extract BIDS entities (participant_id, session) from path
                row.update(self.extract_bids_entities(source_path))
                
                return pd.DataFrame([row])
            else:
                self.logger.error("fMRI requires 4-Dimensional NIfTI data.")
                return pd.DataFrame()
                
        except Exception as e:
            self.logger.error(f"Nilearn computation failed: {e}")
            return pd.DataFrame()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        # Apply BIDS-first harmonization (preserve everything)
        result = self.harmonize_columns(df)
        
        return result
