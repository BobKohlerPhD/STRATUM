import asyncio
import logging
import json
import os
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from fastmcp import FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from pydantic import BaseModel, Field

# Import the core Engine
from src.python.core.engine import StratumEngine

# Import Plugins
from src.python.plugins.imaging_bids import BIDSHarmonizer
from src.python.plugins.multi_omics import MultiOmicsHarmonizer
from src.python.plugins.wearables import WearableHarmonizer
from src.python.plugins.clinical_nlp import ClinicalNLPHarmonizer
from src.python.plugins.biospecimens import BiospecimenHarmonizer
from src.python.plugins.clinical_assessments import ClinicalAssessmentHarmonizer
from src.python.plugins.fmri_nilearn import fMRINilearnHarmonizer

# Import Converters
from src.python.plugins.converter_nibabel import NibabelConverter

# Import Tool Implementations
from src.python.data_dictionary.registry_integrity_check import check_integrity
from src.python.data_dictionary.clinical_metadata_suggester import suggest_metadata
from src.python.variables.clinical_variables_list import get_filtered_variable_names
from src.python.variables.generate_test_data import generate_synthetic_cohort_data
from src.python.variables.clinical_variables_gather import gather_clinical_variables

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/stratum_audit.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("STRATUM-Orchestrator")

# Initialize the STRATUM MCP Server
mcp = FastMCP("STRATUM Orchestrator", description="STRATUM: Agent-driven orchestration of multimodal clinical data")

# Initialize the Engine
PROJECT_ROOT = Path(os.environ.get("STRATUM_PROJECT_ROOT", Path(__file__).parent.resolve()))
engine = StratumEngine(PROJECT_ROOT)

# Register All Plugins
engine.register_plugin("bids", BIDSHarmonizer)
engine.register_plugin("omics", MultiOmicsHarmonizer)
engine.register_plugin("wearables", WearableHarmonizer)
engine.register_plugin("nlp", ClinicalNLPHarmonizer)
engine.register_plugin("biospecimens", BiospecimenHarmonizer)
engine.register_plugin("assessments", ClinicalAssessmentHarmonizer)
engine.register_plugin("fmri_signal", fMRINilearnHarmonizer)

# Register Converters
engine.register_converter(".nii", NibabelConverter())

# Models
class SuggestMetadataInput(BaseModel):
    file_path: str = Field(..., description="Path to the raw CSV file to analyze")
    sample_rows: Optional[int] = Field(default=5, description="Number of rows to sample", ge=1, le=100)

class ListVariablesInput(BaseModel):
    keyword: Optional[str] = Field(default=None, description="Keyword to search for in variable names")

# --- Modality Processing Tools ---

@mcp.tool()
async def process_imaging(filename: str) -> str:
    """Processes neuroimaging metadata (JSON/sidecars) using the BIDS plugin."""
    return await _run_process("bids", filename)

@mcp.tool()
async def process_fmri_signal(filename: str) -> str:
    """Processes 4D fMRI NIfTI files and computes BOLD signal amplitudes."""
    return await _run_process("fmri_signal", filename)

@mcp.tool()
async def process_omics(filename: str) -> str:
    """Processes multi-omics data (genomics, proteomics, metabolomics)."""
    return await _run_process("omics", filename)

@mcp.tool()
async def process_wearables(filename: str) -> str:
    """Processes digital biomarkers and wearable time-series data."""
    return await _run_process("wearables", filename)

@mcp.tool()
async def process_nlp(filename: str) -> str:
    """Processes unstructured clinical notes and extracts phenotypes."""
    return await _run_process("nlp", filename)

@mcp.tool()
async def process_biospecimens(filename: str) -> str:
    """Processes laboratory readouts and biospecimen metadata."""
    return await _run_process("biospecimens", filename)

@mcp.tool()
async def process_assessments(filename: str) -> str:
    """Processes clinical surveys and psychometric assessments."""
    return await _run_process("assessments", filename)

async def _run_process(plugin_name: str, filename: str) -> str:
    try:
        result_df = await asyncio.to_thread(engine.process_modality, plugin_name, filename)
        if result_df is not None and not result_df.empty:
            return f"Successfully processed {filename} via {plugin_name} plugin."
        else:
            return f"Failed to process {filename} or no mapped variables found."
    except Exception as e:
        logger.exception(f"Error processing {filename} with {plugin_name}: {e}")
        return f"Error: {str(e)}"

# --- Data Management Tools ---

@mcp.tool()
async def list_data_tiers() -> str:
    """Lists the current contents of Bronze, Silver, and Gold tiers."""
    summary = []
    for tier in ["bronze", "silver", "gold"]:
        tier_path = PROJECT_ROOT / "data" / tier
        if not tier_path.exists():
            continue
        files = list(tier_path.glob("**/*"))
        files = [f for f in files if f.is_file()]
        summary.append(f"### {tier.upper()} TIER")
        summary.append(f"Total Files: {len(files)}")
        for f in files[:5]:
            summary.append(f" - {f.relative_to(tier_path)}")
        if len(files) > 5:
            summary.append(" - ...")
        summary.append("")
    return "\n".join(summary)

@mcp.tool()
async def generate_gold_tier() -> str:
    """Aggregates all silver data into a unified Gold Tier multi-modal cohort."""
    try:
        df = await asyncio.to_thread(engine.generate_gold_tier)
        if df is not None:
            return f"Successfully generated Gold Tier. Shape: {df.shape}. File: data/gold/gold_multimodal_cohort.csv"
        return "Failed to generate Gold Tier (no silver data found?)"
    except Exception as e:
        logger.exception(f"Error generating gold tier: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def check_registry_integrity() -> str:
    """Automated verification of the Master Clinical Registry."""
    try:
        registry_path = PROJECT_ROOT / "clinical_registry_master.csv"
        is_valid, message = await asyncio.to_thread(check_integrity, str(registry_path))
        return message
    except Exception as e:
        logger.exception(f"Error checking registry integrity: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def generate_synthetic_cohort() -> str:
    """High-fidelity orchestration of synthetic digital twins."""
    try:
        registry_path = PROJECT_ROOT / "clinical_registry_master.csv"
        result = await asyncio.to_thread(generate_synthetic_cohort_data, str(registry_path))
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.exception(f"Error generating synthetic cohort: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def suggest_metadata_from_raw(params: SuggestMetadataInput) -> str:
    """AI-assisted inference of metadata from cryptic raw headers."""
    try:
        full_file_path = PROJECT_ROOT / params.file_path
        if not full_file_path.exists():
            return f"Error: File not found at {full_file_path}"
        result = await asyncio.to_thread(suggest_metadata, str(full_file_path), params.sample_rows)
        return json.dumps(result, indent=2)
    except Exception as e:
        logger.exception(f"Error suggesting metadata: {e}")
        return f"Error: {str(e)}"

@mcp.tool()
async def list_registry_variables(params: ListVariablesInput) -> str:
    """Resilient discovery of clinical variables with fuzzy matching."""
    try:
        current_cwd = os.getcwd()
        os.chdir(PROJECT_ROOT)
        try:
            result = await asyncio.to_thread(get_filtered_variable_names, params.keyword)
        finally:
            os.chdir(current_cwd)
        if not result:
            return f"No variables found matching keyword: {params.keyword}" if params.keyword else "No variables found."
        return "\n".join([f"- {v}" for v in result])
    except Exception as e:
        logger.exception(f"Error listing registry variables: {e}")
        return f"Error: {str(e)}"

# --- Resources ---

@mcp.resource("clinical-registry://master")
def get_registry_master() -> str:
    """Returns the contents of the master clinical registry CSV."""
    return engine.registry_path.read_text()

@mcp.resource("data://gold-cohort-summary")
def get_gold_summary() -> str:
    """Returns a summary of the gold tier cohort if it exists."""
    path = PROJECT_ROOT / "data" / "gold" / "gold_multimodal_cohort.csv"
    if path.exists():
        df = pd.read_csv(path, nrows=10)
        return f"Gold Tier Summary (First 10 rows):\n{df.to_string()}"
    return "Gold tier not yet generated."

if __name__ == "__main__":
    mcp.run()



