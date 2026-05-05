import nibabel as nib
import json
from pathlib import Path
from src.python.core.converter import BaseConverter

class NibabelConverter(BaseConverter):
    """
    Converter using Nibabel to handle NIfTI (.nii), Analyze (.hdr), and MGH/MGZ.
    Extracts geometric headers and sequence parameters if available.
    """
    
    def convert(self, source_path: Path, output_dir: Path) -> Path:
        self.logger.info(f"Converting {source_path.name} via Nibabel...")
        
        try:
            img = nib.load(str(source_path))
            header = img.header
            
            # Extract basic metadata from the header
            metadata = {
                "SeriesDescription": f"Converted from {source_path.suffix}",
                "Dim1": int(header.get_data_shape()[0]),
                "Dim2": int(header.get_data_shape()[1]),
                "Dim3": int(header.get_data_shape()[2]),
                "SliceThickness": float(header.get_zooms()[2]),
                "MRAcquisitionType": "3D" if len(header.get_data_shape()) > 2 else "2D",
                "ConversionTool": "Nibabel-STRATUM"
            }
            
            # Save as JSON sidecar in the requested output directory
            output_json = output_dir / f"{source_path.stem}.json"
            with open(output_json, 'w') as f:
                json.dump(metadata, f, indent=4)
                
            return output_json
            
        except Exception as e:
            self.logger.error(f"Nibabel conversion failed: {e}")
            raise
