"""
EDF → BIDS Converter.

Reads EDF/EDF+ and BDF files using pyedflib (with mne fallback),
extracts header metadata, and generates BIDS-compliant JSON sidecars
plus _channels.tsv companion files.
"""
import json
import logging
from pathlib import Path
from src.python.core.converter import BaseConverter

class EDFToBIDSConverter(BaseConverter):
    """
    Converts EDF/EDF+/BDF files to BIDS-compliant sidecars.
    Generates:
      1. *_eeg.json  — BIDS sidecar with recording metadata
      2. *_channels.tsv — channel names, types, units, sampling rates
    """
    
    def convert(self, source_path: Path, output_dir: Path) -> Path:
        self.logger.info(f"Converting {source_path.name} (EDF/BDF → BIDS)...")
        
        metadata = {}
        channels = []
        
        try:
            # Try pyedflib first (lighter weight)
            import pyedflib
            f = pyedflib.EdfReader(str(source_path))
            try:
                n_channels = f.signals_in_file
                sample_rate = f.getSampleFrequency(0) if n_channels > 0 else 0
                duration = f.file_duration
                
                metadata = {
                    "TaskName": "unknown",
                    "SamplingFrequency": float(sample_rate),
                    "EEGChannelCount": 0,
                    "EOGChannelCount": 0,
                    "ECGChannelCount": 0,
                    "EMGChannelCount": 0,
                    "MiscChannelCount": 0,
                    "TriggerChannelCount": 0,
                    "RecordingDuration": float(duration),
                    "RecordingType": "continuous",
                    "PowerLineFrequency": 50,
                    "Manufacturer": f.getPatientAdditional() or "n/a",
                    "SoftwareFilters": "n/a",
                    "EEGReference": "n/a",
                    "EEGGround": "n/a",
                    "EEGPlacementScheme": "n/a",
                    "ConversionTool": "STRATUM-EDFConverter-pyedflib",
                }
                
                for i in range(n_channels):
                    label = f.getLabel(i).strip()
                    ch_type = self._classify_channel(label)
                    metadata[f"{ch_type}ChannelCount"] = metadata.get(f"{ch_type}ChannelCount", 0) + 1
                    
                    channels.append({
                        "name": label,
                        "type": ch_type,
                        "units": f.getPhysicalDimension(i).strip() or "uV",
                        "sampling_frequency": float(f.getSampleFrequency(i)),
                        "low_cutoff": "n/a",
                        "high_cutoff": "n/a",
                        "notch": "n/a",
                        "status": "good",
                    })
            finally:
                f.close()
                
        except ImportError:
            # Fallback: try mne
            try:
                import mne
                raw = mne.io.read_raw_edf(str(source_path), preload=False, verbose=False)
                
                metadata = {
                    "TaskName": "unknown",
                    "SamplingFrequency": float(raw.info['sfreq']),
                    "EEGChannelCount": len(mne.pick_types(raw.info, eeg=True)),
                    "EOGChannelCount": len(mne.pick_types(raw.info, eog=True)),
                    "ECGChannelCount": len(mne.pick_types(raw.info, ecg=True)),
                    "EMGChannelCount": len(mne.pick_types(raw.info, emg=True)),
                    "MiscChannelCount": len(mne.pick_types(raw.info, misc=True)),
                    "TriggerChannelCount": len(mne.pick_types(raw.info, stim=True)),
                    "RecordingDuration": float(raw.times[-1]) if len(raw.times) > 0 else 0,
                    "RecordingType": "continuous",
                    "PowerLineFrequency": raw.info.get('line_freq', 50) or 50,
                    "Manufacturer": "n/a",
                    "SoftwareFilters": "n/a",
                    "EEGReference": "n/a",
                    "EEGGround": "n/a",
                    "EEGPlacementScheme": "n/a",
                    "ConversionTool": "STRATUM-EDFConverter-mne",
                }
                
                for ch in raw.info['chs']:
                    channels.append({
                        "name": ch['ch_name'],
                        "type": self._mne_ch_type(ch),
                        "units": "uV",
                        "sampling_frequency": float(raw.info['sfreq']),
                        "status": "good",
                    })
            except ImportError:
                # Neither library available — generate minimal sidecar from filename
                self.logger.warning("Neither pyedflib nor mne available. Generating minimal BIDS sidecar.")
                metadata = {
                    "TaskName": "unknown",
                    "SamplingFrequency": "n/a",
                    "EEGChannelCount": "n/a",
                    "RecordingType": "continuous",
                    "ConversionTool": "STRATUM-EDFConverter-minimal",
                    "_warning": "Converted without pyedflib or mne — metadata is incomplete",
                }
        
        # Write BIDS JSON sidecar
        stem = source_path.stem
        output_json = output_dir / f"{stem}_eeg.json"
        with open(output_json, 'w') as f:
            json.dump(metadata, f, indent=4)
        
        # Write channels.tsv if we have channel data
        if channels:
            channels_tsv = output_dir / f"{stem}_channels.tsv"
            import csv
            with open(channels_tsv, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=channels[0].keys(), delimiter='\t')
                writer.writeheader()
                writer.writerows(channels)
            self.logger.info(f"Generated {channels_tsv.name} with {len(channels)} channels")
        
        self.logger.info(f"Generated BIDS sidecar: {output_json.name}")
        return output_json
    
    @staticmethod
    def _classify_channel(label: str) -> str:
        """Classify a channel label into BIDS channel type."""
        label_upper = label.upper()
        if any(x in label_upper for x in ['EOG', 'VEOG', 'HEOG']):
            return 'EOG'
        elif any(x in label_upper for x in ['ECG', 'EKG']):
            return 'ECG'
        elif any(x in label_upper for x in ['EMG']):
            return 'EMG'
        elif any(x in label_upper for x in ['TRIG', 'STI', 'STIM', 'STATUS', 'MARKER']):
            return 'Trigger'
        elif any(x in label_upper for x in ['MISC', 'AUX', 'OTHER']):
            return 'Misc'
        else:
            return 'EEG'
    
    @staticmethod
    def _mne_ch_type(ch_info: dict) -> str:
        """Map MNE channel kind to BIDS type string."""
        import mne
        kind = ch_info.get('kind', 0)
        type_map = {2: 'EEG', 202: 'EOG', 302: 'ECG', 602: 'EMG', 3: 'Trigger', 502: 'Misc'}
        return type_map.get(kind, 'EEG')
