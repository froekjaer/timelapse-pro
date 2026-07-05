"""
Kontrakt-test for `ai.gemini_service.validate_batch_bucket_region()` — den delte
GDPR-guard der forhindrer Vertex AI batch-jobs i at sende billeddata til et
GCS-bucket uden for EU (R12, se `Dokumentation/DPIA_SKABELON_OG_RETENTION_POLICY_v1.md`
§4: "Bekræft Gemini/Vertex AI's faktiske region-indstilling").

Baggrund (2026-07-05, Claude periodisk tjek): `headend/main.py` (API-stien bag
"Kør AI-batch nu" i UI'et) havde allerede dette tjek, men `headend/ai/ai_batch_submit.py`
(CLI-scriptet til manuel bulk re-tag) havde det IKKE — samme Vertex-batch-upload,
men uden guard. Logikken er nu udtrukket til én delt funktion, brugt begge steder,
så de to indgange ikke kan drifte fra hinanden igen.

Ren funktionstest — ingen DB, ingen FastAPI-app, ingen netværkskald. Kræver kun at
`ai.gemini_service` kan importeres (som igen kræver `httpx` installeret, samme som
`ollama_service.py` allerede kræver i produktion).

Kør (fra headend/, i et miljø med httpx + pytest installeret):
    python3 -m venv /tmp/gtest_venv
    /tmp/gtest_venv/bin/pip install httpx pytest
    /tmp/gtest_venv/bin/python3 -m pytest tests/test_gemini_region_guard.py -v
"""
import pathlib
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

from ai.gemini_service import validate_batch_bucket_region  # noqa: E402


class TestValidateBatchBucketRegion:
    def test_matching_region_family_passes(self):
        """Samme region-familie (begge 'europe-*') — intet rejses, selvom det ikke
        er BOGSTAVELIGT samme region (fx west1 vs. west4)."""
        validate_batch_bucket_region("europe-west1", "europe-west4")
        validate_batch_bucket_region("europe-west1", "europe-west1")

    def test_mismatched_region_family_raises(self):
        """Kernescenariet fra DPIA §4: Vertex kører i EU, men bucket er i US —
        skal stoppes, ikke bare logges."""
        with pytest.raises(ValueError, match="matcher ikke Vertex AI region"):
            validate_batch_bucket_region("europe-west1", "us-central1")

    def test_reverse_mismatch_also_raises(self):
        """Samme tjek, omvendt retning (Vertex i Asien, bucket i Europa) —
        guard'en er symmetrisk, ikke kun 'Europa er sikkert'-specifik."""
        with pytest.raises(ValueError):
            validate_batch_bucket_region("asia-southeast1", "europe-west1")

    def test_empty_bucket_region_is_noop_not_fail_closed(self):
        """Bevidst IKKE fail-closed: hvis operatøren aldrig har udfyldt det
        valgfrie 'gemini_gcs_bucket_region'-feltet, skal batch-jobbet fortsat
        kunne køre (se docstring i gemini_service.py for begrundelsen) —
        ikke blokeres af en indstilling der aldrig blev sat."""
        validate_batch_bucket_region("europe-west1", "")
        validate_batch_bucket_region("europe-west1", "   ")

    def test_empty_vertex_region_is_noop(self):
        """Symmetrisk edge case — tom vertex_region skal heller ikke krasje."""
        validate_batch_bucket_region("", "europe-west1")
        validate_batch_bucket_region("", "")

    def test_case_and_whitespace_insensitive(self):
        """Regionnavne sammenlignes uden hensyn til store/små bogstaver og
        omgivende whitespace — indstillinger kommer fra frie tekstfelter i UI'et
        (se `SystemAdminPage.tsx`), så brugerfejl i cases bør ikke udløse en falsk
        GDPR-blokering."""
        validate_batch_bucket_region(" Europe-West1 ", " EUROPE-WEST4 ")
        with pytest.raises(ValueError):
            validate_batch_bucket_region(" EUROPE-WEST1 ", " US-CENTRAL1 ")
