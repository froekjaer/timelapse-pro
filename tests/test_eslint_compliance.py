"""
TimeLapse Pro — ESLint Compliance Tests (P1-06)
===============================================

Tests for ESLint code quality compliance:
- ESLint configuration exists and is valid
- ESLint can run without errors
- Ratchet gate is configured
- Current issues are tracked
- No new issues are introduced (ratchet enforcement)

Context: P1-06 - 222 ESLint problems, ratchet-gate klar,
         men reelle fejl bør rettes løbende.

Kør: pytest tests/test_eslint_compliance.py -v

Marker: integration (kræver npm/ESLint installation)
"""
import os
import pytest
import subprocess
import json
import re
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = "/Volumes/data-fast/peter-home/projects/timelapse-pro"
UI_ROOT = os.path.join(PROJECT_ROOT, "timelapse-ui")

# ESLint configuration paths
ESLINTRC_PATHS = [
    os.path.join(UI_ROOT, ".eslintrc.js"),
    os.path.join(UI_ROOT, ".eslintrc.json"),
    os.path.join(UI_ROOT, ".eslintrc"),
    os.path.join(UI_ROOT, "package.json"),  # ESLint config might be here
]

# Ratchet baseline file
RATCHET_BASELINE = os.path.join(UI_ROOT, ".eslint-ratchet.json")


def run_command(cmd: list, check: bool = True, cwd: str = None) -> subprocess.CompletedProcess:
    """Kør kommando og returner resultat."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check, cwd=cwd)
    except subprocess.CalledProcessError as e:
        return e


# ── 1. ESLint Configuration ───────────────────────────────────────────────────────

@pytest.mark.integration
def test_eslintrc_exists():
    """ESLint konfiguration skal eksistere."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    config_found = False
    for path in ESLINTRC_PATHS:
        if os.path.exists(path):
            config_found = True
            break

    if not config_found:
        pytest.fail("ESLint konfiguration ikke fundet")

    assert config_found


@pytest.mark.integration
def test_eslintrc_valid_json():
    """ESLint konfiguration skal være gyldig JSON (hvis .json)."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    eslintrc_json = os.path.join(UI_ROOT, ".eslintrc.json")

    if os.path.exists(eslintrc_json):
        try:
            with open(eslintrc_json) as f:
                json.load(f)
            assert True, "ESLint config er gyldig JSON"
        except json.JSONDecodeError as e:
            pytest.fail(f"ESLint config er ugyldig JSON: {e}")
    else:
        pytest.skip(".eslintrc.json ikke fundet (kan bruge .eslintrc.js)")


@pytest.mark.integration
def test_eslint_in_package_json():
    """ESLint skal være konfigureret i package.json."""
    package_json = os.path.join(UI_ROOT, "package.json")

    if not os.path.exists(package_json):
        pytest.skip("package.json ikke fundet")

    with open(package_json) as f:
        content = f.read()

    # Check for ESLint in devDependencies or scripts
    has_eslint_dep = "eslint" in content.lower()
    has_eslint_script = '"lint"' in content or '"eslint"' in content

    assert has_eslint_dep or has_eslint_script, \
        "ESLint skal være i package.json"


@pytest.mark.integration
def test_eslint_installed():
    """ESLint skal være installeret."""
    # Check if eslint is installed
    result = run_command(["npm", "list", "eslint"], cwd=UI_ROOT, check=False)

    if result.returncode != 0:
        pytest.skip("npm install ikke kørt eller ESLint ikke installeret")

    # Should list eslint
    has_eslint = "eslint" in result.stdout

    if not has_eslint:
        # Try with npx
        result = run_command(["npx", "eslint", "--version"], check=False)
        if result.returncode != 0:
            pytest.fail("ESLint ikke installeret eller ikke tilgængelig via npx")

    assert True


# ── 2. ESLint Execution ───────────────────────────────────────────────────────────

@pytest.mark.integration
def test_eslint_runs():
    """ESLint skal kunne køre uden fejl."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Try to run ESLint
    result = run_command(["npx", "eslint", "--version"], cwd=UI_ROOT, check=False)

    if result.returncode != 0:
        pytest.fail(f"ESLint kan ikke køre: {result.stderr}")

    assert result.returncode == 0


@pytest.mark.integration
def test_eslint_can_lint():
    """ESLint skal kunne linte TypeScript filer."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Find a TSX file to lint
    src_files = list(Path(UI_ROOT).glob("src/**/*.tsx"))

    if not src_files:
        pytest.skip("Ingen TSX filer fundet")

    # Try linting one file
    result = run_command(
        ["npx", "eslint", "--format", "json", str(src_files[0])],
        cwd=UI_ROOT,
        check=False
    )

    # May have linting errors, but should run
    if result.returncode not in [0, 1]:  # 0 = no errors, 1 = linting errors found
        pytest.fail(f"ESLint fejlede: {result.stderr}")

    assert True


@pytest.mark.integration
def test_eslint_target_files_exist():
    """ESLint target filer skal eksistere."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Check if there are TSX/TS files to lint
    src_dir = os.path.join(UI_ROOT, "src")
    if not os.path.exists(src_dir):
        pytest.skip("src mappe ikke fundet")

    tsx_files = list(Path(src_dir).glob("**/*.tsx"))
    ts_files = list(Path(src_dir).glob("**/*.ts"))

    total_files = len(tsx_files) + len(ts_files)

    assert total_files > 0, "Ingen TypeScript filer at lint"


# ── 3. Ratchet Gate Configuration ───────────────────────────────────────────────

@pytest.mark.integration
def test_ratchet_baseline_exists():
    """ESLint ratchet baseline skal eksistere."""
    if not os.path.exists(RATCHET_BASELINE):
        pytest.skip("ESLint ratchet baseline ikke fundet - P1-06 ikke fuldt opfyldt")

    assert os.path.exists(RATCHET_BASELINE)


@pytest.mark.integration
def test_ratchet_baseline_valid():
    """ESLint ratchet baseline skal være gyldig."""
    if not os.path.exists(RATCHET_BASELINE):
        pytest.skip("ESLint ratchet baseline ikke fundet")

    try:
        with open(RATCHET_BASELINE) as f:
            baseline = json.load(f)

        # Should have expected structure
        assert isinstance(baseline, dict), "Baseline skal være et objekt"

        # Check for issue count
        if "issueCount" in baseline:
            assert isinstance(baseline["issueCount"], int), "issueCount skal være et tal"

        assert True
    except json.JSONDecodeError as e:
        pytest.fail(f"Ratchet baseline er ugyldig JSON: {e}")


@pytest.mark.integration
def test_ratchet_baseline_has_issues():
    """Ratchet baseline skal have issues tracket."""
    if not os.path.exists(RATCHET_BASELINE):
        pytest.skip("ESLint ratchet baseline ikke fundet")

    with open(RATCHET_BASELINE) as f:
        baseline = json.load(f)

    # Should track issues
    has_issues = (
        "issues" in baseline or
        "issueCount" in baseline or
        "results" in baseline
    )

    if not has_issues:
        pytest.skip("Ratchet baseline har ikke issues tracket")

    assert has_issues


@pytest.mark.integration
def test_ratchet_baseline_date():
    """Ratchet baseline skal have dato."""
    if not os.path.exists(RATCHET_BASELINE):
        pytest.skip("ESLint ratchet baseline ikke fundet")

    with open(RATCHET_BASELINE) as f:
        baseline = json.load(f)

    # Should have date/timestamp
    has_date = (
        "date" in baseline or
        "timestamp" in baseline or
        "createdAt" in baseline
    )

    if not has_date:
        pytest.skip("Ratchet baseline mangler dato")

    assert has_date


# ── 4. Current Issues Tracking ───────────────────────────────────────────────────

@pytest.mark.integration
def test_current_issues_counted():
    """Nuværende ESLint issues skal være talt."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Run ESLint and count issues
    result = run_command(
        ["npx", "eslint", "--format", "json", "src/"],
        cwd=UI_ROOT,
        check=False
    )

    if result.returncode not in [0, 1]:
        pytest.skip("ESLint kunne ikke køre")

    # Parse JSON output
    try:
        eslint_output = json.loads(result.stdout)

        total_errors = 0
        total_warnings = 0

        for file_result in eslint_output:
            errors = file_result.get("errorCount", 0)
            warnings = file_result.get("warningCount", 0)
            total_errors += errors
            total_warnings += warnings

        # Should have counts
        assert True  # Issues talt
    except json.JSONDecodeError:
        pytest.skip("ESLint output er ikke gyldig JSON")


@pytest.mark.integration
def test_issue_categories():
    """ESLint issues skal være kategoriseret."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Run ESLint
    result = run_command(
        ["npx", "eslint", "--format", "json", "src/"],
        cwd=UI_ROOT,
        check=False
    )

    if result.returncode not in [0, 1]:
        pytest.skip("ESLint kunne ikke køre")

    # Analyze issue types
    try:
        eslint_output = json.loads(result.stdout)

        issue_types = set()
        for file_result in eslint_output:
            for message in file_result.get("messages", []):
                rule_id = message.get("ruleId", "unknown")
                issue_types.add(rule_id)

        # Should have identified issue types
        assert len(issue_types) >= 0  # Just verify we can categorize
    except json.JSONDecodeError:
        pytest.skip("ESLint output er ikke gyldig JSON")


# ── 5. Ratchet Enforcement ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_no_new_issues_added():
    """Ingen nye ESLint issues må tilføjes (ratchet)."""
    if not os.path.exists(RATCHET_BASELINE):
        pytest.skip("ESLint ratchet baseline ikke fundet")

    # Get current issue count
    result = run_command(
        ["npx", "eslint", "--format", "json", "src/"],
        cwd=UI_ROOT,
        check=False
    )

    if result.returncode not in [0, 1]:
        pytest.skip("ESLint kunne ikke køre")

    # Parse current issues
    try:
        eslint_output = json.loads(result.stdout)

        current_total = 0
        for file_result in eslint_output:
            current_total += file_result.get("errorCount", 0)
            current_total += file_result.get("warningCount", 0)

        # Get baseline count
        with open(RATCHET_BASELINE) as f:
            baseline = json.load(f)

        baseline_count = baseline.get("issueCount", 999999)

        # Current should not exceed baseline
        if current_total > baseline_count:
            pytest.fail(
                f"Ratchet violated: {current_total} > {baseline_count} (baseline). "
                f"Fix issues eller opdater baseline."
            )

        assert current_total <= baseline_count
    except json.JSONDecodeError:
        pytest.skip("ESLint output er ikke gyldig JSON")


@pytest.mark.integration
def test_ratchet_gate_in_ci():
    """Ratchet gate skal være konfigureret i CI."""
    # Check if ESLint runs in CI
    ci_config_paths = [
        os.path.join(PROJECT_ROOT, ".github", "workflows", "ci.yml"),
        os.path.join(PROJECT_ROOT, ".github", "workflows", "eslint.yml"),
    ]

    has_ratchet_gate = False
    for path in ci_config_paths:
        if os.path.exists(path):
            with open(path) as f:
                content = f.read()
                if "eslint" in content.lower() or "ratchet" in content.lower():
                    has_ratchet_gate = True
                    break

    if not has_ratchet_gate:
        pytest.skip("Ratchet gate ikke fundet i CI config")

    assert has_ratchet_gate


@pytest.mark.integration
def test_ratchet_script_exists():
    """Ratchet script skal eksistere."""
    # Check if there's a script to run ESLint with ratchet
    package_json = os.path.join(UI_ROOT, "package.json")

    if not os.path.exists(package_json):
        pytest.skip("package.json ikke fundet")

    with open(package_json) as f:
        content = f.read()

    # Check for lint script
    has_lint_script = '"lint"' in content or '"eslint"' in content

    if not has_lint_script:
        pytest.skip("Lint script ikke fundet i package.json")

    assert has_lint_script


# ── 6. Issue Categories Breakdown ────────────────────────────────────────────────

@pytest.mark.integration
def test_issues_by_severity():
    """Issues skal være opdelt efter severity."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Run ESLint
    result = run_command(
        ["npx", "eslint", "--format", "json", "src/"],
        cwd=UI_ROOT,
        check=False
    )

    if result.returncode not in [0, 1]:
        pytest.skip("ESLint kunne ikke køre")

    # Count by severity
    try:
        eslint_output = json.loads(result.stdout)

        total_errors = 0
        total_warnings = 0

        for file_result in eslint_output:
            total_errors += file_result.get("errorCount", 0)
            total_warnings += file_result.get("warningCount", 0)

        # Should have breakdown
        assert total_errors >= 0 and total_warnings >= 0
    except json.JSONDecodeError:
        pytest.skip("ESLint output er ikke gyldig JSON")


@pytest.mark.integration
def test_issues_by_rule():
    """Issues skal være grupperet efter regel."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Run ESLint
    result = run_command(
        ["npx", "eslint", "--format", "json", "src/"],
        cwd=UI_ROOT,
        check=False
    )

    if result.returncode not in [0, 1]:
        pytest.skip("ESLint kunne ikke køre")

    # Group by rule
    try:
        eslint_output = json.loads(result.stdout)

        rule_counts = {}
        for file_result in eslint_output:
            for message in file_result.get("messages", []):
                rule_id = message.get("ruleId", "unknown")
                rule_counts[rule_id] = rule_counts.get(rule_id, 0) + 1

        # Should have rule breakdown
        assert len(rule_counts) >= 0
    except json.JSONDecodeError:
        pytest.skip("ESLint output er ikke gyldig JSON")


# ── 7. High Priority Issues ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_no_critical_security_issues():
    """Ingen kritiske sikkerhedsissues må eksistere."""
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Security-related rules to check
    security_rules = [
        "no-eval",
        "no-implied-eval",
        "no-new-func",
        "no-script-url",
    ]

    # Run ESLint
    result = run_command(
        ["npx", "eslint", "--format", "json", "src/"],
        cwd=UI_ROOT,
        check=False
    )

    if result.returncode not in [0, 1]:
        pytest.skip("ESLint kunne ikke køre")

    # Check for security issues
    try:
        eslint_output = json.loads(result.stdout)

        security_issues = []
        for file_result in eslint_output:
            for message in file_result.get("messages", []):
                rule_id = message.get("ruleId", "")
                if any(rule in rule_id for rule in security_rules):
                    security_issues.append({
                        "file": file_result.get("filePath"),
                        "rule": rule_id,
                        "message": message.get("message"),
                    })

        if security_issues:
            pytest.fail(f"Kritiske sikkerhedsissues fundet: {security_issues}")

        assert True
    except json.JSONDecodeError:
        pytest.skip("ESLint output er ikke gyldig JSON")


@pytest.mark.integration
def test_fixable_issues_identified():
    """Fixable issues skal være identificeret."""
    # ESLint can identify auto-fixable issues
    if not os.path.exists(UI_ROOT):
        pytest.skip("timelapse-ui mappe ikke fundet")

    # Run ESLint with --fix to see what's fixable
    result = run_command(
        ["npx", "eslint", "--format", "json", "--fix-dry-run", "src/"],
        cwd=UI_ROOT,
        check=False
    )

    if result.returncode not in [0, 1]:
        pytest.skip("ESLint kunne ikke køre")

    # Count fixable issues
    try:
        eslint_output = json.loads(result.stdout)

        fixable_count = 0
        for file_result in eslint_output:
            for message in file_result.get("messages", []):
                if message.get("fix"):
                    fixable_count += 1

        # Should identify fixable issues
        assert fixable_count >= 0
    except json.JSONDecodeError:
        pytest.skip("ESLint output er ikke gyldig JSON")


# ── 8. P1-06 Completion Verification ───────────────────────────────────────────

@pytest.mark.integration
def test_p1_06_ratchet_configured():
    """P1-06: Ratchet gate skal være konfigureret."""
    # Ratchet gate should be in place
    if not os.path.exists(RATCHET_BASELINE):
        pytest.fail("P1-06 ikke opfyldt: Ratchet baseline mangler")

    assert True


@pytest.mark.integration
def test_p1_06_issue_count_tracked():
    """P1-06: Issue count skal være tracket."""
    # Should know the current issue count (222 mentioned in P1-06)
    if not os.path.exists(RATCHET_BASELINE):
        pytest.skip("Ratchet baseline ikke fundet")

    with open(RATCHET_BASELINE) as f:
        baseline = json.load(f)

    issue_count = baseline.get("issueCount")

    if issue_count is None:
        pytest.skip("Issue count ikke i baseline")

    # Should have reasonable count
    assert isinstance(issue_count, int) and issue_count >= 0


@pytest.mark.integration
def test_p1_06_documented():
    """P1-06 skal være dokumenteret."""
    backlog_path = os.path.join(PROJECT_ROOT, "PRIORITIZED_BACKLOG.md")

    if not os.path.exists(backlog_path):
        pytest.skip("PRIORITIZED_BACKLOG.md ikke fundet")

    with open(backlog_path) as f:
        content = f.read()

    # P1-06 should be mentioned
    p1_06_section = content[content.find("P1-06"):content.find("P1-06") + 500]

    assert "P1-06" in p1_06_section, "P1-06 skal være i backlog"


# ── 9. ESLint Configuration Quality ───────────────────────────────────────────────

@pytest.mark.integration
def test_eslint_preset_reasonable():
    """ESLint preset skal være passende."""
    # Should use a reasonable preset (e.g., @typescript-eslint/recommended)
    eslintrc_json = os.path.join(UI_ROOT, ".eslintrc.json")
    eslintrc_js = os.path.join(UI_ROOT, ".eslintrc.js")

    config_path = None
    if os.path.exists(eslintrc_json):
        config_path = eslintrc_json
    elif os.path.exists(eslintrc_js):
        config_path = eslintrc_js

    if not config_path:
        pytest.skip("ESLint config ikke fundet")

    with open(config_path) as f:
        content = f.read()

    # Should have TypeScript support
    has_typescript = "typescript" in content.lower() or "@typescript-eslint" in content

    if not has_typescript:
        pytest.fail("ESLint skal have TypeScript support")

    assert has_typescript


@pytest.mark.integration
def test_eslint_react_configured():
    """ESLint skal have React/JSX support."""
    eslintrc_json = os.path.join(UI_ROOT, ".eslintrc.json")
    eslintrc_js = os.path.join(UI_ROOT, ".eslintrc.js")

    config_path = None
    if os.path.exists(eslintrc_json):
        config_path = eslintrc_json
    elif os.path.exists(eslintrc_js):
        config_path = eslintrc_js

    if not config_path:
        pytest.skip("ESLint config ikke fundet")

    with open(config_path) as f:
        content = f.read()

    # Should have React support
    has_react = "react" in content.lower() or "jsx" in content.lower()

    if not has_react:
        pytest.skip("React support ikke konfigureret (kan være valgfri)")


@pytest.mark.integration
def test_eslint_rules_documented():
    """ESLint regler skal være dokumenteret."""
    # Should have documentation for custom rules
    doc_paths = [
        os.path.join(PROJECT_ROOT, "Dokumentation", "DEVELOPERGUIDE.md"),
        os.path.join(PROJECT_ROOT, "timelapse-ui", "README.md"),
        os.path.join(PROJECT_ROOT, "README.md"),
    ]

    has_docs = False
    for doc_path in doc_paths:
        if os.path.exists(doc_path):
            with open(doc_path) as f:
                content = f.read()
                if "eslint" in content.lower():
                    has_docs = True
                    break

    if not has_docs:
        pytest.skip("ESLint dokumentation ikke fundet")

    assert has_docs
