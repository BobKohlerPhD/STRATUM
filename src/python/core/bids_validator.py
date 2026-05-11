"""
BIDS Compliance Validator.

Checks whether a subject's data follows BIDS naming conventions,
required file structures, and sidecar metadata completeness.
"""
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger("STRATUM-BIDSValidator")

# BIDS required fields by modality
BIDS_REQUIRED_FIELDS = {
    "eeg": {
        "required": ["TaskName", "SamplingFrequency", "EEGReference", "EEGChannelCount"],
        "recommended": ["PowerLineFrequency", "RecordingDuration", "RecordingType", 
                        "EEGGround", "EEGPlacementScheme", "SoftwareFilters"],
        "expected_files": ["_eeg.json", "_channels.tsv", "_events.tsv"],
    },
    "func": {
        "required": ["RepetitionTime", "TaskName"],
        "recommended": ["MagneticFieldStrength", "Manufacturer", "SliceThickness",
                        "EchoTime", "FlipAngle", "PhaseEncodingDirection"],
        "expected_files": ["_bold.json", "_bold.nii.gz", "_events.tsv"],
    },
    "anat": {
        "required": [],
        "recommended": ["MagneticFieldStrength", "Manufacturer", "MRAcquisitionType",
                        "RepetitionTime", "EchoTime", "FlipAngle", "SliceThickness"],
        "expected_files": ["_T1w.json", "_T1w.nii.gz"],
    },
    "dwi": {
        "required": [],
        "recommended": ["MagneticFieldStrength", "Manufacturer"],
        "expected_files": ["_dwi.json", "_dwi.nii.gz", "_dwi.bval", "_dwi.bvec"],
    },
}

# BIDS naming regex: sub-<label>[_ses-<label>][_task-<label>][_acq-<label>][_run-<index>]_<suffix>
BIDS_FILENAME_PATTERN = re.compile(
    r'^sub-[a-zA-Z0-9]+(?:_ses-[a-zA-Z0-9]+)?(?:_task-[a-zA-Z0-9]+)?'
    r'(?:_acq-[a-zA-Z0-9]+)?(?:_run-[0-9]+)?(?:_space-[a-zA-Z0-9]+)?_[a-zA-Z0-9]+\.\w+$'
)


@dataclass
class ValidationIssue:
    severity: str  # "error", "warning", "info"
    category: str  # "naming", "structure", "metadata", "completeness"
    message: str
    file: Optional[str] = None


@dataclass
class ValidationReport:
    subject_id: str
    is_compliant: bool
    score: float  # 0.0 - 1.0
    issues: List[ValidationIssue] = field(default_factory=list)
    summary: str = ""
    
    def to_dict(self) -> dict:
        return {
            "subject_id": self.subject_id,
            "is_compliant": self.is_compliant,
            "compliance_score": round(self.score, 2),
            "summary": self.summary,
            "error_count": len([i for i in self.issues if i.severity == "error"]),
            "warning_count": len([i for i in self.issues if i.severity == "warning"]),
            "issues": [asdict(i) for i in self.issues],
        }


def _detect_modality(filepath: Path) -> Optional[str]:
    """Detect BIDS modality from file naming."""
    name = filepath.name
    if '_bold' in name:
        return 'func'
    elif '_T1w' in name or '_T2w' in name or '_FLAIR' in name:
        return 'anat'
    elif '_dwi' in name:
        return 'dwi'
    elif '_eeg' in name or '_meg' in name:
        return 'eeg'
    return None


def validate_bids_subject(subject_dir: Path, subject_id: str) -> ValidationReport:
    """
    Validate a subject's data for BIDS compliance.
    
    Checks:
    1. Filename conventions (sub-XXX_ses-XX_suffix.ext)
    2. Required sidecar metadata fields
    3. Recommended metadata completeness
    4. Expected companion files
    """
    issues: List[ValidationIssue] = []
    total_checks = 0
    passed_checks = 0
    
    all_files = list(subject_dir.rglob("*"))
    data_files = [f for f in all_files if f.is_file()]
    
    if not data_files:
        return ValidationReport(
            subject_id=subject_id,
            is_compliant=False,
            score=0.0,
            issues=[ValidationIssue("error", "structure", "No data files found")],
            summary="Empty subject directory"
        )
    
    # Check 1: Filename conventions
    for f in data_files:
        total_checks += 1
        if BIDS_FILENAME_PATTERN.match(f.name):
            passed_checks += 1
        else:
            issues.append(ValidationIssue(
                "warning", "naming",
                f"Non-BIDS filename: '{f.name}' — expected pattern: sub-<label>[_ses-<label>]_<suffix>.<ext>",
                file=f.name
            ))
    
    # Check 2: JSON sidecar metadata
    json_files = [f for f in data_files if f.suffix == '.json']
    for jf in json_files:
        modality = _detect_modality(jf)
        if modality and modality in BIDS_REQUIRED_FIELDS:
            try:
                with open(jf, 'r') as f:
                    data = json.load(f)
                keys = set(data.keys())
                
                spec = BIDS_REQUIRED_FIELDS[modality]
                
                # Required fields
                for req in spec["required"]:
                    total_checks += 1
                    if req in keys and data[req] not in [None, "n/a", ""]:
                        passed_checks += 1
                    elif req in keys and data[req] in ["n/a", ""]:
                        issues.append(ValidationIssue(
                            "warning", "metadata",
                            f"Required field '{req}' is present but set to '{data[req]}' (should have a real value)",
                            file=jf.name
                        ))
                        passed_checks += 0.5
                    else:
                        issues.append(ValidationIssue(
                            "error", "metadata",
                            f"Missing required BIDS field: '{req}'",
                            file=jf.name
                        ))
                
                # Recommended fields
                for rec in spec["recommended"]:
                    total_checks += 1
                    if rec in keys:
                        passed_checks += 1
                    else:
                        issues.append(ValidationIssue(
                            "info", "completeness",
                            f"Recommended BIDS field not present: '{rec}'",
                            file=jf.name
                        ))
                        passed_checks += 0.5  # Half credit for recommended
                        
            except Exception as e:
                issues.append(ValidationIssue(
                    "error", "metadata",
                    f"Failed to parse JSON: {str(e)}",
                    file=jf.name
                ))
    
    # Check 3: Companion files
    for f in data_files:
        modality = _detect_modality(f)
        if modality and modality in BIDS_REQUIRED_FIELDS and f.suffix == '.json':
            spec = BIDS_REQUIRED_FIELDS[modality]
            prefix = f.stem.rsplit('_', 1)[0]  # sub-120_task-rest
            for expected_suffix in spec["expected_files"]:
                total_checks += 1
                expected_name = prefix + expected_suffix
                if any(df.name == expected_name for df in data_files):
                    passed_checks += 1
                else:
                    issues.append(ValidationIssue(
                        "warning", "completeness",
                        f"Expected companion file not found: '{expected_name}'",
                        file=f.name
                    ))
    
    score = passed_checks / max(total_checks, 1)
    is_compliant = score >= 0.7 and not any(i.severity == "error" for i in issues)
    
    error_count = len([i for i in issues if i.severity == "error"])
    warn_count = len([i for i in issues if i.severity == "warning"])
    info_count = len([i for i in issues if i.severity == "info"])
    
    summary = (
        f"BIDS compliance score: {score:.0%} | "
        f"{error_count} errors, {warn_count} warnings, {info_count} info | "
        f"{'COMPLIANT' if is_compliant else 'NON-COMPLIANT'}"
    )
    
    return ValidationReport(
        subject_id=subject_id,
        is_compliant=is_compliant,
        score=score,
        issues=issues,
        summary=summary
    )
