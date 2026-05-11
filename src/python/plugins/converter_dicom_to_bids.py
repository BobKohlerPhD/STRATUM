"""
DICOM → BIDS NIfTI Converter.

Wraps dcm2niix to convert DICOM series into BIDS-compatible
NIfTI files with JSON sidecars. Falls back to pydicom for
metadata-only extraction when dcm2niix is unavailable.
"""
import json
import subprocess
import logging
from pathlib import Path
from src.python.core.converter import BaseConverter

class DICOMToBIDSConverter(BaseConverter):
    """
    Converts DICOM series to BIDS-compliant NIfTI + JSON sidecars.
    
    Primary method: dcm2niix (produces NIfTI + JSON automatically)
    Fallback: pydicom header extraction (metadata-only, no NIfTI)
    """
    
    def convert(self, source_path: Path, output_dir: Path) -> Path:
        self.logger.info(f"Converting DICOM: {source_path} → BIDS NIfTI...")
        
        # Determine if source is a single file or directory of DICOMs
        dicom_dir = source_path if source_path.is_dir() else source_path.parent
        
        # Try dcm2niix first
        try:
            result = subprocess.run(
                [
                    "dcm2niix",
                    "-z", "y",            # gzip compress
                    "-b", "y",            # generate BIDS sidecar
                    "-ba", "y",           # anonymize BIDS
                    "-f", "%p_%s",        # filename pattern: protocol_series
                    "-o", str(output_dir),
                    str(dicom_dir)
                ],
                capture_output=True, text=True, timeout=120
            )
            
            if result.returncode == 0:
                # Find the generated JSON sidecar
                json_files = list(output_dir.glob("*.json"))
                newest = max(json_files, key=lambda f: f.stat().st_mtime) if json_files else None
                if newest:
                    self.logger.info(f"dcm2niix conversion successful: {newest.name}")
                    return newest
            
            self.logger.warning(f"dcm2niix returned code {result.returncode}: {result.stderr}")
            
        except FileNotFoundError:
            self.logger.info("dcm2niix not found, falling back to pydicom header extraction")
        except subprocess.TimeoutExpired:
            self.logger.warning("dcm2niix timed out, falling back to pydicom")
        except Exception as e:
            self.logger.warning(f"dcm2niix failed: {e}, falling back to pydicom")
        
        # Fallback: pydicom metadata-only extraction
        return self._extract_with_pydicom(source_path, output_dir)
    
    def _extract_with_pydicom(self, source_path: Path, output_dir: Path) -> Path:
        """Extract DICOM header metadata and generate a BIDS-like JSON sidecar."""
        try:
            import pydicom
            
            # Find a DICOM file
            if source_path.is_dir():
                dicom_files = list(source_path.glob("*.dcm")) + list(source_path.glob("*.DCM"))
                if not dicom_files:
                    # Try files without extension (common for DICOM)
                    dicom_files = [f for f in source_path.iterdir() if f.is_file()]
                if not dicom_files:
                    raise ValueError(f"No DICOM files found in {source_path}")
                dcm_file = dicom_files[0]
            else:
                dcm_file = source_path
            
            ds = pydicom.dcmread(str(dcm_file), stop_before_pixels=True)
            
            metadata = {
                "Modality": str(getattr(ds, 'Modality', 'n/a')),
                "MagneticFieldStrength": float(getattr(ds, 'MagneticFieldStrength', 0)) or "n/a",
                "Manufacturer": str(getattr(ds, 'Manufacturer', 'n/a')),
                "ManufacturerModelName": str(getattr(ds, 'ManufacturersModelName', 'n/a')),
                "InstitutionName": str(getattr(ds, 'InstitutionName', 'n/a')),
                "SeriesDescription": str(getattr(ds, 'SeriesDescription', 'n/a')),
                "RepetitionTime": float(getattr(ds, 'RepetitionTime', 0)) / 1000.0 if hasattr(ds, 'RepetitionTime') else "n/a",
                "EchoTime": float(getattr(ds, 'EchoTime', 0)) / 1000.0 if hasattr(ds, 'EchoTime') else "n/a",
                "FlipAngle": float(getattr(ds, 'FlipAngle', 0)) if hasattr(ds, 'FlipAngle') else "n/a",
                "SliceThickness": float(getattr(ds, 'SliceThickness', 0)) if hasattr(ds, 'SliceThickness') else "n/a",
                "AcquisitionTime": str(getattr(ds, 'AcquisitionTime', 'n/a')),
                "PatientID": str(getattr(ds, 'PatientID', 'n/a')),
                "StudyDate": str(getattr(ds, 'StudyDate', 'n/a')),
                "PixelSpacing": [float(x) for x in getattr(ds, 'PixelSpacing', [])] if hasattr(ds, 'PixelSpacing') else "n/a",
                "Rows": int(getattr(ds, 'Rows', 0)) if hasattr(ds, 'Rows') else "n/a",
                "Columns": int(getattr(ds, 'Columns', 0)) if hasattr(ds, 'Columns') else "n/a",
                "ConversionTool": "STRATUM-DICOMConverter-pydicom",
                "_warning": "Metadata-only conversion (no NIfTI generated). Install dcm2niix for full conversion.",
            }
            
            # Determine modality-specific BIDS fields
            modality = getattr(ds, 'Modality', '')
            if modality == 'PT':  # PET
                metadata.update({
                    "TracerName": str(getattr(ds, 'RadiopharmaceuticalInformationSequence', [{}])[0].get('Radiopharmaceutical', 'n/a')) if hasattr(ds, 'RadiopharmaceuticalInformationSequence') else "n/a",
                    "BodyPartExamined": str(getattr(ds, 'BodyPartExamined', 'n/a')),
                })
            elif modality == 'CT':
                metadata.update({
                    "KVP": float(getattr(ds, 'KVP', 0)) if hasattr(ds, 'KVP') else "n/a",
                    "XRayTubeCurrent": float(getattr(ds, 'XRayTubeCurrent', 0)) if hasattr(ds, 'XRayTubeCurrent') else "n/a",
                })
            
            # Write JSON sidecar
            stem = dcm_file.stem if not source_path.is_dir() else source_path.name
            output_json = output_dir / f"{stem}_converted.json"
            with open(output_json, 'w') as f:
                json.dump(metadata, f, indent=4)
            
            self.logger.info(f"Generated BIDS sidecar from DICOM headers: {output_json.name}")
            return output_json
            
        except ImportError:
            self.logger.error("Neither dcm2niix nor pydicom available. Cannot convert DICOM.")
            # Generate a minimal placeholder
            output_json = output_dir / f"{source_path.stem}_unconverted.json"
            with open(output_json, 'w') as f:
                json.dump({
                    "ConversionTool": "STRATUM-DICOMConverter-stub",
                    "_error": "Neither dcm2niix nor pydicom installed",
                }, f, indent=4)
            return output_json
