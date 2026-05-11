from abc import ABC, abstractmethod
from pathlib import Path
import logging

class BaseConverter(ABC):
    """
    Base class for MRI format converters.
    Transitions data from raw (e.g. DICOM, NIfTI) to STRATUM-compatible JSON sidecars.
    """
    def __init__(self):
        self.logger = logging.getLogger(f"STRATUM-Converter-{self.__class__.__name__}")

    @abstractmethod
    def convert(self, source_path: Path, output_dir: Path) -> Path:
        """
        Converts a raw format to a standard BIDS-like JSON sidecar.
        Returns the path to the generated JSON.
        """
        pass
