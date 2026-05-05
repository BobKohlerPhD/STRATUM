import nibabel as nib
import numpy as np
import os
from pathlib import Path

def create_4d_fmri(path: Path):
    """Creates a 4D NIfTI file with varying signal to simulate a BOLD time-series."""
    # (x, y, z, time) -> (16, 16, 16, 100 volumes)
    # Generate some random brain signal with an artificial temporal amplitude
    np.random.seed(42)
    # Background noise
    data = np.random.normal(0, 1, size=(16, 16, 16, 100))
    # Inject a strong signal in the center to simulate activation
    baseline = 1000
    activation = np.sin(np.linspace(0, 8 * np.pi, 100)) * 50
    for t in range(100):
        data[6:10, 6:10, 6:10, t] += (baseline + activation[t])
    
    img = nib.Nifti1Image(data, affine=np.eye(4))
    img.header.set_zooms((3.0, 3.0, 3.0, 2.0)) # 3mm iso, TR=2.0s
    nib.save(img, str(path))
    print(f"Created 4D BOLD Sim NIfTI: {path}")

if __name__ == "__main__":
    bronze_imaging = Path("data/bronze/imaging")
    bronze_imaging.mkdir(parents=True, exist_ok=True)
    # Saving as .nii.gz to bypass the STRATUM Nibabel Structural Converter 
    create_4d_fmri(bronze_imaging / "sub-001_ses-01_task-rest_bold.nii.gz")
