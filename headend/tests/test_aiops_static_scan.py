"""
Kontrakt-test for `_aiops_scan_should_skip_path()` i `headend/main.py` — hjælpefunktionen
der afgør hvilke stier AI Ops' lette SAST-scanner (`_aiops_static_scan()`) springer over.

Baggrund (2026-07-05, Claude periodisk tjek — VPEN-006 "SAST backlog triage", 73 signaler):
`skip_parts`-tjekket krævede tidligere en EKSAKT match på en hel path-del ("venv",
"node_modules" osv.). Det fangede ikke den lokale, .gitignore'ede
`artifacts/edge-qa-training/.venv-edge-qa-train-py312/lib/python3.12/site-packages/...`
(en hel vendored virtualenv med sympy/onnxruntime/onnx/fsspec m.fl., efterladt af en tidligere
trænings-kørsel). Konsekvens: en reproduktion af scanneren i denne runde viste at 72 af 80
(capped) "SAST-signaler" reelt var tredjeparts-bibliotekskode, ikke TimeLapse Pro-kode — og at
det hårde 80-fund-loft blev brugt op af denne støj FØR resten af repoet nåede at blive scannet,
så eventuelle reelle fund andre steder i repoet reelt kunne forsvinde fra snapshottet.

Fix: `_aiops_scan_should_skip_path()` er udtrukket til en ren, sideeffektfri funktion der også
springer "artifacts" (eksakt del), enhver del der starter med ".venv" og enhver del der
INDEHOLDER "site-packages"/"dist-packages" over. Denne test er en ren funktionstest (ingen
filsystem, ingen DB, ingen FastAPI-app) og kan køres med kun `pytest` installeret — importerer
`_aiops_scan_should_skip_path` direkte fra `headend/main.py`.

OBS: Da `main.py` importerer en del af projektets egne moduler ved modul-load (database,
routers osv.), kræver selve importen samme afhængigheder som resten af test-suiten
(fastapi, sqlalchemy, python-jose, bcrypt, passlib, slowapi, python-multipart, python-dotenv,
httpx) — men testen selv rører hverken DB eller netværk.

Kør (fra headend/, i et miljø med disse pakker + pytest installeret):
    python3 -m pytest tests/test_aiops_static_scan.py -v
"""
import os
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent.parent  # headend/
sys.path.insert(0, str(HERE))

# VIGTIGT: DATABASE_URL skal sættes FØR `database`/`main` importeres første gang, ellers
# forsøger database.py at oprette en postgres-engine (kræver psycopg2 + en kørende server).
# Samme mønster som test_report_update_rollup.py/test_update_lifecycle.py.
_TMP_DB = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB.name}")

from main import (  # noqa: E402
    _aiops_scan_is_secret_value_literal,
    _aiops_scan_should_skip_line,
    _aiops_scan_should_skip_path,
    _aiops_static_scan,
)


class TestAiopsScanShouldSkipPath:
    def test_real_world_vendored_venv_is_skipped(self):
        """Det konkrete tilfælde der udløste denne fix: en navngivet, ikke-'venv'-kaldet
        virtualenv under den lokale, .gitignore'ede 'artifacts/'-mappe."""
        parts = (
            "artifacts", "edge-qa-training", ".venv-edge-qa-train-py312",
            "lib", "python3.12", "site-packages", "sympy", "utilities", "autowrap.py",
        )
        assert _aiops_scan_should_skip_path(parts) is True

    def test_artifacts_top_level_is_skipped_even_without_venv(self):
        parts = ("artifacts", "some_training_run", "notes.py")
        assert _aiops_scan_should_skip_path(parts) is True

    def test_dotted_venv_variant_without_site_packages_is_skipped(self):
        parts = (".venv-foo", "bar.py")
        assert _aiops_scan_should_skip_path(parts) is True

    def test_literal_venv_still_skipped(self):
        """Regression: den oprindelige eksakte 'venv'-match må ikke gå tabt."""
        assert _aiops_scan_should_skip_path(("venv", "lib", "x.py")) is True
        assert _aiops_scan_should_skip_path(("node_modules", "x.js")) is True
        assert _aiops_scan_should_skip_path(("__pycache__", "x.py")) is True

    def test_own_product_code_is_not_skipped(self):
        """Reelle TimeLapse Pro-filer skal fortsat scannes — fixet må ikke blive for grådigt."""
        assert _aiops_scan_should_skip_path(("headend", "main.py")) is False
        assert _aiops_scan_should_skip_path(("claude_proxy.py",)) is False
        assert _aiops_scan_should_skip_path(("e2e_test.sh",)) is False
        assert _aiops_scan_should_skip_path(("timelapse-ui", "src", "pages", "UpdatesPage.tsx")) is False

    def test_venvironments_style_directory_is_not_falsely_skipped(self):
        """Sikrer at prefix-tjekket er '.venv', ikke bare 'venv' som substring — en mappe der
        bare TILFÆLDIGVIS indeholder 'venv' i navnet (uden at være en dotfile-venv) skal IKKE
        blive fejlagtigt sprunget over."""
        assert _aiops_scan_should_skip_path(("my_venvironments_helper.py",)) is False


class TestAiopsScanShouldSkipLine:
    """Baggrund (2026-07-05, periodisk tjek #18 — første reelle triage-runde af VPEN-006's
    SAST-signaler efter VPEN-2026-008's scanner-fix): `_aiops_static_scan()`'s egen
    `patterns`-dict indeholder nødvendigvis needle-strengene som bogstavelig tekst (fx
    "token=", "subprocess.run", "unlink(", "git pull"). Uden denne markør ville scanneren
    derfor matche sin EGEN pattern-definition som 4 garanterede selvreferentielle falske
    positive ved hver eneste kørsel — ét pr. kategori — helt uafhængigt af resten af repoet."""

    def test_marker_line_is_skipped(self):
        assert _aiops_scan_should_skip_line(
            '        "hardcoded_secret_terms": ["password=", "token="],  # AIOPS-SCAN-IGNORE-SELF'
        ) is True

    def test_ordinary_code_line_is_not_skipped(self):
        assert _aiops_scan_should_skip_line("    token_record = db.query(BootstrapToken)") is False
        assert _aiops_scan_should_skip_line("result = subprocess.run(cmd)") is False


class TestAiopsStaticScanSelfReferenceRegression:
    """Kører den fulde `_aiops_static_scan()` mod det virkelige repo (samme mønster som
    VPEN-2026-008's before/after-reproduktion) og bekræfter at ingen af de 4 garanterede
    selvreferentielle fund fra scannerens egen pattern-definition i `headend/main.py` længere
    optræder i resultatet."""

    def test_own_pattern_definition_lines_are_not_reported_as_findings(self):
        result = _aiops_static_scan()
        self_referential = [
            f for f in result["findings"]
            if any(
                marker in f["snippet"]
                for marker in ('"hardcoded_secret_terms":', '"shell_execution":', '"dangerous_file_ops":', '"legacy_update_paths":')
            )
        ]
        assert self_referential == []


class TestAiopsScanIsSecretValueLiteral:
    """Baggrund (2026-07-05, periodisk tjek #18/#19 -> denne runde): under VPEN-006-triagen
    blev alle 10 daværende `hardcoded_secret_terms`-signaler manuelt vurderet false positive —
    samtlige var variabel-/kwarg-referencer (fx `token=req.bootstrap_token`,
    `wifi_password=wifi_password`), ikke bogstavelige hemmelige værdier. Forbedringsforslaget
    fra den runde ("kun flage når højresiden ligner en streng-literal"), som blev noteret men
    IKKE udført dengang, er implementeret her som `_aiops_scan_is_secret_value_literal()`."""

    def test_quoted_literal_is_flagged(self):
        assert _aiops_scan_is_secret_value_literal('password="hunter2"', "password=") is True
        assert _aiops_scan_is_secret_value_literal("api_key='sk-abc123'", "api_key=") is True

    def test_variable_reference_is_not_flagged(self):
        assert _aiops_scan_is_secret_value_literal(
            "bootstrap_token=req.bootstrap_token", "token="
        ) is False
        assert _aiops_scan_is_secret_value_literal(
            "wifi_password=wifi_password", "password="
        ) is False

    def test_needle_not_present_returns_false(self):
        assert _aiops_scan_is_secret_value_literal("no needle here", "password=") is False

    def test_whitespace_before_quote_is_tolerated(self):
        assert _aiops_scan_is_secret_value_literal('secret=   "abc"', "secret=") is True


class TestAiopsStaticScanHardcodedSecretTermsPrecision:
    """Integrationstest: bekræfter at `_aiops_static_scan()`'s filter for
    `hardcoded_secret_terms` rent faktisk anvendes i den fulde scan, ikke kun i den isolerede
    hjælpefunktion ovenfor."""

    def test_variable_reference_pattern_is_not_reported_as_finding(self):
        """Regressionsværn mod at VPEN-006's konkrete false-positive-mønster
        (`token=req.bootstrap_token`-stil variabel-referencer) dukker op igen som et
        `hardcoded_secret_terms`-fund i en fremtidig scan."""
        result = _aiops_static_scan()
        secret_term_findings = [
            f for f in result["findings"] if f["category"] == "hardcoded_secret_terms"
        ]
        for finding in secret_term_findings:
            snippet = finding["snippet"]
            assert "=" in snippet
            # Redigeret snippet skal enten indeholde den maskerede '***'-erstatning
            # (bogstavelig literal-værdi) eller en quote-karakter tæt på tildelingen — ikke en
            # bar variabel-/kwarg-reference uden citationstegn.
            assert "***" in snippet or "'" in snippet or '"' in snippet
