import pandas as pd
import json
from typing import List, Dict, Any

def suggest_metadata(file_path: str, sample_rows: int = 5) -> List[Dict[str, Any]]:
    """
    Analyzes a raw data file and generates a skeleton for the clinical_registry_master.csv.
    
    BIDS-First: If a column name matches a known BIDS field, it is flagged as
    is_bids=true and the bids_standard_name is set to the original name.
    Non-BIDS fields get a placeholder bids_standard_name for manual review.
    
    Args:
        file_path (str): Path to the raw CSV file.
        sample_rows (int): Number of rows to analyze.
        
    Returns:
        List[Dict[str, Any]]: A list of metadata suggestion dictionaries.
    """
    # Common BIDS fields across modalities
    KNOWN_BIDS_FIELDS = {
        'MagneticFieldStrength', 'RepetitionTime', 'EchoTime', 'Manufacturer',
        'AcquisitionTime', 'MRAcquisitionType', 'ScanningSequence', 'FlipAngle',
        'SliceThickness', 'PhaseEncodingDirection', 'EffectiveEchoSpacing',
        'TotalReadoutTime', 'SeriesDescription', 'SamplingFrequency',
        'EEGChannelCount', 'EEGReference', 'TaskName', 'PowerLineFrequency',
        'SoftwareFilters', 'RecordingDuration', 'RecordingType', 'EEGGround',
        'EEGPlacementScheme', 'EOGChannelCount', 'ECGChannelCount',
        'EMGChannelCount', 'MiscChannelCount', 'TriggerChannelCount',
    }

    try:
        # Read only a few rows to analyze structure
        df = pd.read_csv(file_path, nrows=sample_rows)
        suggestions = []

        for col in df.columns:
            sample_vals = df[col].dropna().unique().tolist()
            
            # Basic type inference
            if df[col].dtype in ['int64', 'float64']:
                datatype = 'ratio' if len(sample_vals) > 10 else 'ordinal'
            else:
                datatype = 'nominal'

            is_bids = col in KNOWN_BIDS_FIELDS

            # Build a suggestion object
            suggestion = {
                "original_variable_name": col,
                "bids_standard_name": col if is_bids else col.lower().replace(" ", "_").replace("-", "_"),
                "datatype": datatype,
                "levels": json.dumps([str(v) for v in sample_vals[:10]]) if datatype in ['nominal', 'ordinal'] else "[]",
                "is_bids": is_bids,
                "sample_values": str(sample_vals[:3])
            }
            suggestions.append(suggestion)

        return suggestions
    except Exception as e:
        return [{"error": str(e)}]
