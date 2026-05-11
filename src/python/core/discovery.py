"""
STRATUM Auto-Discovery & Ingestion Engine.

Scans the bronze tier for all subjects and modalities, maps files to
the correct plugin, and processes everything automatically. This replaces
the manual task list in system_init.py.
"""
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("STRATUM-Discovery")

# File extension → plugin name mapping
# The engine uses this to automatically route files to the correct harmonizer
EXTENSION_PLUGIN_MAP: Dict[str, str] = {
    # BIDS neuroimaging sidecars (JSON)
    # Routing for JSON requires content inspection — handled in _classify_json()
    
    # Tabular formats
    ".csv":     None,  # Requires content inspection
    ".tsv":     None,  # BIDS tabular data
    ".parquet": "omics",
    
    # Neuroimaging raw data
    ".nii":     "fmri_signal",
    ".nii.gz":  "fmri_signal",
    
    # Electrophysiology
    ".edf":     "eeg_signal",
    ".bdf":     "eeg_signal",
    ".set":     "eeg_signal",      # EEGLAB format
    ".fif":     "eeg_signal",      # MNE-Python format
    ".vhdr":    "eeg_signal",      # BrainVision
    
    # Other
    ".json":    None,  # Requires content inspection
}

# Directory name → modality hints for CSV routing
DIRECTORY_MODALITY_MAP: Dict[str, str] = {
    "genomics":     "omics",
    "proteomics":   "omics",
    "metabolomics": "omics",
    "assessments":  "assessments",
    "biospecimens":  "biospecimens",
    "ehr_notes":    "nlp",
    "wearables":    "wearables",
    "imaging":      "bids",
    "eeg":          "eeg",
    "ehr":          None,   # FHIR — needs dedicated handler
    "pharmacy":     None,   # Future
    "demographics": None,   # Future
}


@dataclass
class DiscoveredAsset:
    """Represents a discovered data file with routing metadata."""
    subject_id: str
    session_id: Optional[str]
    modality_dir: str
    filename: str
    relative_path: str
    extension: str
    plugin: Optional[str]
    status: str = "pending"  # pending, processed, skipped, error
    message: str = ""


@dataclass
class SubjectManifest:
    """Full manifest for a discovered subject."""
    subject_id: str
    assets: List[DiscoveredAsset] = field(default_factory=list)
    
    @property
    def modalities(self) -> List[str]:
        return list(set(a.modality_dir for a in self.assets))
    
    @property
    def processable(self) -> List[DiscoveredAsset]:
        return [a for a in self.assets if a.plugin is not None]
    
    @property
    def skipped(self) -> List[DiscoveredAsset]:
        return [a for a in self.assets if a.plugin is None]
    
    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "modalities": self.modalities,
            "total_files": len(self.assets),
            "processable": len(self.processable),
            "skipped": len(self.skipped),
            "assets": [asdict(a) for a in self.assets]
        }


def _extract_subject_id(path: Path) -> str:
    """Extract subject ID from BIDS-style path or filename."""
    full = str(path)
    match = re.search(r'(sub-[a-zA-Z0-9]+)', full)
    return match.group(1) if match else "sub-unknown"


def _extract_session_id(path: Path) -> Optional[str]:
    """Extract session ID from BIDS-style path or filename."""
    full = str(path)
    match = re.search(r'(ses-[a-zA-Z0-9]+)', full)
    return match.group(1) if match else None


def _classify_json(filepath: Path, modality_dir: str) -> Optional[str]:
    """
    Inspect a JSON file's contents to determine which plugin should handle it.
    BIDS sidecars are classified by their field signatures.
    """
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        keys = set(data.keys())
        
        # EEG BIDS sidecar signature
        eeg_keys = {'EEGChannelCount', 'SamplingFrequency', 'EEGReference', 'TaskName', 'PowerLineFrequency'}
        if keys & eeg_keys:
            return "eeg"
        
        # MRI BIDS sidecar signature
        mri_keys = {'MagneticFieldStrength', 'RepetitionTime', 'EchoTime', 'MRAcquisitionType'}
        if keys & mri_keys:
            return "bids"
        
        # FHIR bundle signature
        if 'resourceType' in keys and data.get('resourceType') == 'Bundle':
            return None  # Future: FHIR harmonizer
        
        # Wearable data signature
        if 'heart_rate_array' in keys or 'sleep_stages_array' in keys or 'device_brand' in keys:
            return "wearables"
        
        # Coordinate system / events JSON (BIDS ancillary)
        if 'EEGCoordinateSystem' in keys or 'IntendedFor' in keys:
            return None  # Ancillary file, skip
        
        # Fall back to directory hint
        return DIRECTORY_MODALITY_MAP.get(modality_dir)
    except Exception:
        return None


def _classify_csv(filepath: Path, modality_dir: str) -> Optional[str]:
    """Route CSV files using directory context."""
    return DIRECTORY_MODALITY_MAP.get(modality_dir)


def _get_extension(filepath: Path) -> str:
    """Get full extension including compound ones like .nii.gz."""
    name = filepath.name
    if name.endswith('.nii.gz'):
        return '.nii.gz'
    return filepath.suffix


def discover_subjects(bronze_dir: Path) -> Dict[str, SubjectManifest]:
    """
    Scan the entire bronze tier and build a manifest of all subjects
    and their associated data files with plugin routing.
    """
    manifests: Dict[str, SubjectManifest] = {}
    
    for filepath in sorted(bronze_dir.rglob("*")):
        if filepath.is_dir():
            continue
        
        # Determine modality directory (first level under bronze)
        try:
            rel = filepath.relative_to(bronze_dir)
            modality_dir = rel.parts[0]
        except (ValueError, IndexError):
            continue
        
        subject_id = _extract_subject_id(filepath)
        session_id = _extract_session_id(filepath)
        ext = _get_extension(filepath)
        
        # Determine the plugin
        if ext == '.json':
            plugin = _classify_json(filepath, modality_dir)
        elif ext == '.csv':
            plugin = _classify_csv(filepath, modality_dir)
        elif ext in EXTENSION_PLUGIN_MAP:
            plugin = EXTENSION_PLUGIN_MAP[ext]
        else:
            plugin = None
        
        asset = DiscoveredAsset(
            subject_id=subject_id,
            session_id=session_id,
            modality_dir=modality_dir,
            filename=filepath.name,
            relative_path=str(rel),
            extension=ext,
            plugin=plugin,
            status="pending" if plugin else "skipped",
            message="" if plugin else f"No plugin mapped for {ext} in {modality_dir}/"
        )
        
        if subject_id not in manifests:
            manifests[subject_id] = SubjectManifest(subject_id=subject_id)
        manifests[subject_id].assets.append(asset)
    
    return manifests


def build_task_list(manifest: SubjectManifest) -> List[Tuple[str, str]]:
    """Convert a subject manifest into an engine-compatible task list."""
    tasks = []
    for asset in manifest.processable:
        tasks.append((asset.plugin, asset.relative_path))
    return tasks


def get_processing_status(bronze_dir: Path, silver_dir: Path, gold_dir: Path) -> dict:
    """
    Generate a comprehensive processing status report.
    Shows what's been discovered, processed, and what's pending.
    """
    manifests = discover_subjects(bronze_dir)
    
    # Check silver tier for processed files
    silver_files = set(f.stem.replace("harmonized_", "") for f in silver_dir.glob("harmonized_*.csv"))
    
    # Check gold tier
    gold_exists = (gold_dir / "gold_multimodal_cohort.csv").exists()
    
    status = {
        "subjects_discovered": len(manifests),
        "subjects": {},
        "silver_files": len(silver_files),
        "gold_generated": gold_exists,
    }
    
    total_processable = 0
    total_processed = 0
    total_skipped = 0
    
    for sid, manifest in manifests.items():
        subject_status = {
            "modalities": manifest.modalities,
            "total_files": len(manifest.assets),
            "processable": len(manifest.processable),
            "skipped": len(manifest.skipped),
            "skipped_files": [a.filename for a in manifest.skipped],
        }
        
        # Check which assets have been processed (have silver output)
        processed = []
        pending = []
        for asset in manifest.processable:
            stem = Path(asset.filename).stem
            if stem in silver_files or any(stem in sf for sf in silver_files):
                processed.append(asset.filename)
            else:
                pending.append(asset.filename)
        
        subject_status["processed"] = processed
        subject_status["pending"] = pending
        
        total_processable += len(manifest.processable)
        total_processed += len(processed)
        total_skipped += len(manifest.skipped)
        
        status["subjects"][sid] = subject_status
    
    status["total_processable"] = total_processable
    status["total_processed"] = total_processed
    status["total_skipped"] = total_skipped
    
    return status
