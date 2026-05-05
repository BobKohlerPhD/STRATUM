import nibabel as nib
import numpy as np
import os
from pathlib import Path

def create_dummy_nifti(path: Path):
    """Creates a small valid NIfTI file for testing."""
    data = np.zeros((32, 32, 32), dtype=np.int16)
    img = nib.Nifti1Image(data, affine=np.eye(4))
    img.header.set_zooms((1.0, 1.0, 1.0))
    nib.save(img, str(path))
    print(f"Created dummy NIfTI: {path}")

if __name__ == "__main__":
    bronze_imaging = Path("data/bronze/imaging")
    bronze_imaging.mkdir(parents=True, exist_ok=True)
    create_dummy_nifti(bronze_imaging / "test_structural.nii")
