import pandas as pd
import numpy as np
from pathlib import Path
import mne
from src.python.core.harmonizer import BaseHarmonizer

class EEGMNEHarmonizer(BaseHarmonizer):
    """
    Computational plug-in for EEG signal processing.
    Ingests raw EEG data (e.g., .set, .edf), computes the Global Field Power (GFP),
    and extracts its mean amplitude as a derived feature.
    
    BIDS-First: Output features are preserved alongside any BIDS metadata.
    Computed fields use BIDS-compatible naming where applicable.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        ext = source_path.suffix.lower()
        if ext not in ['.set', '.edf', '.bdf', '.vhdr', '.fif']:
            self.logger.error(f"EEG MNE requires a valid EEG file format, got: {ext}")
            return pd.DataFrame()
            
        self.logger.info(f"MNE Engine computing Global Field Power for {source_path.name}...")
        try:
            # Load the EEG data
            if ext == '.set':
                raw = mne.io.read_raw_eeglab(str(source_path), preload=True, verbose=False)
            elif ext == '.edf':
                raw = mne.io.read_raw_edf(str(source_path), preload=True, verbose=False)
            elif ext == '.bdf':
                raw = mne.io.read_raw_bdf(str(source_path), preload=True, verbose=False)
            elif ext == '.vhdr':
                raw = mne.io.read_raw_brainvision(str(source_path), preload=True, verbose=False)
            elif ext == '.fif':
                raw = mne.io.read_raw_fif(str(source_path), preload=True, verbose=False)
            else:
                return pd.DataFrame()

            # Compute Global Field Power (GFP)
            # GFP is the standard deviation across all channels at each time point
            data = raw.get_data()  # shape (n_channels, n_times)
            gfp = np.std(data, axis=0)
            
            # Feature extraction: mean GFP amplitude
            eeg_amplitude = float(np.mean(gfp))
            
            row = {
                "eeg_amplitude": eeg_amplitude,
                "modality_category": "eeg_signal"
            }
            
            # Extract BIDS entities (participant_id, session) from path
            row.update(self.extract_bids_entities(source_path))
            
            return pd.DataFrame([row])
                
        except Exception as e:
            self.logger.error(f"MNE computation failed: {e}")
            return pd.DataFrame()

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        
        # Apply BIDS-first harmonization (preserve everything)
        result = self.harmonize_columns(df)
        
        return result
