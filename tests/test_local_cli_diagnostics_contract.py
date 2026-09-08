"""The local TOTP UI must expose the existing read-only JSON diagnosis."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "edge/scripts/totp-service.py").read_text(encoding="utf-8")


def test_doctor_json_is_allowed_by_local_management_cli():
    start = SOURCE.index("CLI_ALLOWED_FLAGS = {")
    end = SOURCE.index("}\n", start) + 2
    assert '"--doctor-json"' in SOURCE[start:end]


def test_doctor_json_remains_read_only_diagnostic_command():
    cli = (ROOT / "edge/tools/bootstrap_cli.py").read_text(encoding="utf-8")
    assert 'parser.add_argument("--doctor-json"' in cli
    assert "if args.doctor_json:" in cli
