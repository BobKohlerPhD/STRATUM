"""
HL7 FHIR R4 Bundle Harmonizer.

Parses FHIR JSON Bundles and extracts structured clinical data from:
  - Patient (demographics)
  - Observation (vitals, labs)
  - Condition (diagnoses)
  - MedicationRequest (pharmacy)
  - Encounter (visit context)
  - Procedure (surgical/procedural history)

Maps LOINC codes, ICD-10 codes, and SNOMED-CT codes to canonical names.
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime
from src.python.core.harmonizer import BaseHarmonizer

# Common LOINC code → human-readable name map
LOINC_MAP = {
    "8867-4":  "heart_rate",
    "8480-6":  "systolic_bp",
    "8462-4":  "diastolic_bp",
    "8310-5":  "body_temperature",
    "9279-1":  "respiratory_rate",
    "2708-6":  "spo2",
    "29463-7": "body_weight",
    "8302-2":  "body_height",
    "39156-5": "bmi",
    "2345-7":  "glucose",
    "2160-0":  "creatinine",
    "2093-3":  "total_cholesterol",
    "2571-8":  "triglycerides",
    "2085-9":  "hdl_cholesterol",
    "13457-7": "ldl_cholesterol",
    "718-7":   "hemoglobin",
    "4544-3":  "hematocrit",
    "6690-2":  "wbc_count",
    "26515-7": "platelet_count",
    "1742-6":  "alt",
    "1920-8":  "ast",
    "1975-2":  "bilirubin_total",
    "2951-2":  "sodium",
    "2823-3":  "potassium",
    "17861-6": "calcium",
    "2339-0":  "glucose_fasting",
    "4548-4":  "hba1c",
    "33914-3": "egfr",
    "14749-6": "glucose_urine",
    "5803-2":  "ph_urine",
    "2947-0":  "bun",
}


class FHIRHarmonizer(BaseHarmonizer):
    """
    Plugin for HL7 FHIR R4 Bundle harmonization.
    Extracts Patient, Observation, Condition, MedicationRequest,
    and Procedure resources into tabular format.
    """
    
    def ingest(self, source_path: Path) -> pd.DataFrame:
        with open(source_path, 'r') as f:
            bundle = json.load(f)
        
        if bundle.get('resourceType') != 'Bundle':
            self.logger.warning(f"{source_path.name} is not a FHIR Bundle")
            return pd.DataFrame()
        
        entries = bundle.get('entry', [])
        rows = []
        
        for entry in entries:
            resource = entry.get('resource', {})
            rtype = resource.get('resourceType', '')
            
            if rtype == 'Patient':
                rows.extend(self._parse_patient(resource))
            elif rtype == 'Observation':
                rows.extend(self._parse_observation(resource))
            elif rtype == 'Condition':
                rows.extend(self._parse_condition(resource))
            elif rtype == 'MedicationRequest':
                rows.extend(self._parse_medication(resource))
            elif rtype == 'Procedure':
                rows.extend(self._parse_procedure(resource))
            elif rtype == 'Encounter':
                rows.extend(self._parse_encounter(resource))
        
        if not rows:
            return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # Extract participant_id
        entities = self.extract_bids_entities(source_path)
        for key, val in entities.items():
            df[key] = val
        
        return df
    
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        return self.harmonize_columns(df)
    
    def _parse_patient(self, resource: dict) -> list:
        """Extract demographics from a FHIR Patient resource."""
        row = {
            "fhir_resource_type": "Patient",
            "modality_category": "demographics",
            "patient_fhir_id": resource.get('id', ''),
            "participant_sex": resource.get('gender', 'unknown'),
            "birth_date": resource.get('birthDate', ''),
        }
        
        # Calculate age if birthDate is available
        if row['birth_date']:
            try:
                birth = datetime.strptime(row['birth_date'], '%Y-%m-%d')
                row['participant_age'] = (datetime.now() - birth).days // 365
            except (ValueError, TypeError):
                pass
        
        # Extract race/ethnicity from extensions (US Core profile)
        for ext in resource.get('extension', []):
            url = ext.get('url', '')
            if 'race' in url:
                for sub in ext.get('extension', []):
                    if sub.get('url') == 'ombCategory':
                        coding = sub.get('valueCoding', {})
                        row['participant_race'] = coding.get('display', '')
            elif 'ethnicity' in url:
                for sub in ext.get('extension', []):
                    if sub.get('url') == 'ombCategory':
                        coding = sub.get('valueCoding', {})
                        row['participant_ethnicity'] = coding.get('display', '')
        
        # Name (for PII flagging — will be redacted by de-id pipeline)
        names = resource.get('name', [])
        if names:
            name = names[0]
            row['_pii_patient_name'] = f"{' '.join(name.get('given', []))} {name.get('family', '')}"
        
        return [row]
    
    def _parse_observation(self, resource: dict) -> list:
        """Extract observations (vitals, labs) from FHIR."""
        row = {"fhir_resource_type": "Observation"}
        
        # Extract LOINC code
        code_obj = resource.get('code', {})
        codings = code_obj.get('coding', [])
        loinc_code = ''
        display = code_obj.get('text', '')
        
        for coding in codings:
            system = coding.get('system', '')
            if 'loinc' in system.lower():
                loinc_code = coding.get('code', '')
                display = coding.get('display', display)
        
        # Map LOINC code to canonical name
        canonical_name = LOINC_MAP.get(loinc_code, display.lower().replace(' ', '_') if display else f"obs_{loinc_code}")
        row['observation_name'] = canonical_name
        row['loinc_code'] = loinc_code
        
        # Extract value
        if 'valueQuantity' in resource:
            vq = resource['valueQuantity']
            row['observation_value'] = vq.get('value')
            row['observation_unit'] = vq.get('unit', '')
        elif 'valueCodeableConcept' in resource:
            cc = resource['valueCodeableConcept']
            row['observation_value'] = cc.get('text', str(cc.get('coding', [{}])[0].get('display', '')))
            row['observation_unit'] = 'categorical'
        elif 'valueString' in resource:
            row['observation_value'] = resource['valueString']
            row['observation_unit'] = 'text'
        
        # Status and timestamp
        row['observation_status'] = resource.get('status', '')
        row['observation_datetime'] = resource.get('effectiveDateTime', '')
        
        # Determine modality_category based on content
        vital_signs = {'heart_rate', 'systolic_bp', 'diastolic_bp', 'body_temperature',
                       'respiratory_rate', 'spo2', 'body_weight', 'body_height', 'bmi'}
        
        if canonical_name in vital_signs:
            row['modality_category'] = 'vital_signs'
        else:
            row['modality_category'] = 'lab_results'
        
        return [row]
    
    def _parse_condition(self, resource: dict) -> list:
        """Extract diagnoses from FHIR Condition resource."""
        row = {
            "fhir_resource_type": "Condition",
            "modality_category": "diagnoses",
        }
        
        # Extract ICD-10 or SNOMED code
        code_obj = resource.get('code', {})
        codings = code_obj.get('coding', [])
        
        for coding in codings:
            system = coding.get('system', '')
            if 'icd' in system.lower():
                row['diagnosis_icd10'] = coding.get('code', '')
                row['diagnosis_display'] = coding.get('display', '')
            elif 'snomed' in system.lower():
                row['diagnosis_snomed'] = coding.get('code', '')
                row['diagnosis_display'] = coding.get('display', row.get('diagnosis_display', ''))
        
        if 'diagnosis_display' not in row:
            row['diagnosis_display'] = code_obj.get('text', '')
        
        row['diagnosis_status'] = resource.get('clinicalStatus', {}).get('coding', [{}])[0].get('code', '') if resource.get('clinicalStatus') else ''
        row['diagnosis_onset'] = resource.get('onsetDateTime', '')
        row['diagnosis_recorded'] = resource.get('recordedDate', '')
        
        return [row]
    
    def _parse_medication(self, resource: dict) -> list:
        """Extract medication data from FHIR MedicationRequest."""
        row = {
            "fhir_resource_type": "MedicationRequest",
            "modality_category": "pharmacy",
        }
        
        # Extract medication code (RxNorm, NDC)
        med_obj = resource.get('medicationCodeableConcept', {})
        codings = med_obj.get('coding', [])
        
        for coding in codings:
            system = coding.get('system', '')
            if 'rxnorm' in system.lower():
                row['medication_rxnorm'] = coding.get('code', '')
            elif 'ndc' in system.lower():
                row['medication_ndc'] = coding.get('code', '')
            row['medication_name'] = coding.get('display', med_obj.get('text', ''))
        
        if not codings:
            row['medication_name'] = med_obj.get('text', '')
        
        row['medication_status'] = resource.get('status', '')
        row['medication_intent'] = resource.get('intent', '')
        
        # Dosage
        dosage = resource.get('dosageInstruction', [{}])
        if dosage:
            d = dosage[0]
            row['medication_dose_text'] = d.get('text', '')
            dose_qty = d.get('doseAndRate', [{}])
            if dose_qty:
                dq = dose_qty[0].get('doseQuantity', {})
                row['medication_dose_value'] = dq.get('value', '')
                row['medication_dose_unit'] = dq.get('unit', '')
        
        row['medication_authored'] = resource.get('authoredOn', '')
        
        return [row]
    
    def _parse_procedure(self, resource: dict) -> list:
        """Extract procedure data from FHIR Procedure resource."""
        row = {
            "fhir_resource_type": "Procedure",
            "modality_category": "procedures",
        }
        
        code_obj = resource.get('code', {})
        codings = code_obj.get('coding', [])
        
        for coding in codings:
            system = coding.get('system', '')
            if 'cpt' in system.lower() or 'hcpcs' in system.lower():
                row['procedure_cpt'] = coding.get('code', '')
            elif 'snomed' in system.lower():
                row['procedure_snomed'] = coding.get('code', '')
            row['procedure_display'] = coding.get('display', code_obj.get('text', ''))
        
        if not codings:
            row['procedure_display'] = code_obj.get('text', '')
        
        row['procedure_status'] = resource.get('status', '')
        
        performed = resource.get('performedDateTime', resource.get('performedPeriod', {}).get('start', ''))
        row['procedure_date'] = performed
        
        return [row]
    
    def _parse_encounter(self, resource: dict) -> list:
        """Extract encounter/visit context from FHIR."""
        row = {
            "fhir_resource_type": "Encounter",
            "modality_category": "encounters",
        }
        
        row['encounter_id'] = resource.get('id', '')
        row['encounter_status'] = resource.get('status', '')
        row['encounter_class'] = resource.get('class', {}).get('code', '') if isinstance(resource.get('class'), dict) else ''
        
        period = resource.get('period', {})
        row['encounter_start'] = period.get('start', '')
        row['encounter_end'] = period.get('end', '')
        
        types = resource.get('type', [])
        if types:
            row['encounter_type'] = types[0].get('text', str(types[0].get('coding', [{}])[0].get('display', '')))
        
        return [row]
