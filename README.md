# STRATUM
## Agent-Driven Orchestration of Multimodal Clinical Data


**WIP, currently using this architecture to eventually merge with a tool for MRI and EEG**


STRATUM is designed to harmonize high-dimensional, heterogeneous clinical datasets into longitudinal cohorts. It utilizes a tiered skeletal architecture—aligned with the Medallion Data Pattern—to automate the processing of Multi-Omics, EHR (FHIR), and high-frequency digital biomarkers.

---

The STRATUM environment is engineered for unidirectional data flow across three tiers

#### Tiering Model for Data
The platform enforces a rigorous separation of concerns through its storage layers:
*   **Bronze (Source)**: Repository for raw, de-identified clinical data, includes fastq-derived variants, REDCap survey extracts, raw wearable telemetry, and HL7 FHIR R4 bundles.
*   **Silver (Harmonized)**: Modality-specific derivatives validated against  Registry. All variables are mapped to standard clinical conventions, including LOINC, SNOMED CT, and RxNorm.
*   **Gold (Analytics)**: Single-record-per-subject-per-session format.

#### Skeletal Engine and Plugin Architecture
Orchestration is managed by `StratumEngine`. Modular design isolates the transformation logic for varied clinical streams—such as unstructured narrative NLP or mass-spec proteomics—while maintaining a unified de-identification and merge pipeline.

---

### Clinical Modalities and Governance

STRATUM implements physics-informed feature extraction and ontological mapping to bridge the gap between raw telemetry and clinical insights.

#### Supported Modalities
*   **Clinical EHR (FHIR)**: Dynamically parses complex FHIR resources to extract longitudinal diagnostics and pharmacokinetic records.
*   **Multi-Omics**: Standardizes VCF zygosity and UniProt protein abundances into the clinical timeline.
*   **Digital Biomarkers**: Deconstructs high-frequency wearable sensor arrays into validated clinical scalars, such as sleep efficiency and heart rate variability.
*   **Clinical NLP**: Translates physician free-text into computable numerical features through entity extraction and SNOMED-CT mapping.

#### Privacy and De-identification (Zero-Trust)
All explicit identifiers are suppressed, age-bounding is applied for subjects over 89, and birth dates are truncated. Furthermore, W3C-PROV compliant SHA-256 hashes are appended to all data records.

---

### Operational Deployment

#### Implementation via FastMCP
The orchestrator is deployed as a Model Context Protocol (MCP) server. To ensure environment isolation, `uv` is recommended.

```bash
uv run --with fastmcp python stratum_server.py
```

#### Agentic Integration
Integration with LLM agents is achieved by configuring the MCP server in the agent's host environment. For Claude Desktop, the configuration follows the standard protocol:

```json
{
  "mcpServers": {
    "stratum": {
      "command": "uv",
      "args": ["run", "--with", "fastmcp", "python", "/path/to/stratum_server.py"]
    }
  }
}
```

#### The REAL-L Orchestration Loop
Agents operating within the STRATUM environment are instructed to follow the REAL-L protocol (Read, Evaluate, Act, Verify, Log) to ensure zero schema drift during ingestion and cohort generation.

