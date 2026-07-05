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

from main import _aiops_scan_should_skip_path  # noqa: E402


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
