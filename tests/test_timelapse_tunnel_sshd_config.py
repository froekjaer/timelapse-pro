"""Regression tests for the dedicated tunnel-sshd ingress artefacts.

Locks in three externally reviewed blocking defects (2026-09-17) so they
cannot silently regress:

1. authorized_keys entries must use
       restrict,port-forwarding,permitlisten="127.0.0.1:<port>"
   (`restrict` alone disables ALL forwarding; `permitlisten` alone re-enables
   NOTHING — `port-forwarding` is what re-enables it, then `permitlisten`
   narrows it). A bare `restrict,permitlisten=…` entry yields a key that can
   establish no forwards at all: a silent tunnel failure.

2. Every ssh invocation in the installer must place ALL options BEFORE the
   destination host (options after the destination are parsed as a remote
   command).

3. `--verify-only` must be provably read-only: its branch must exit before
   the first mutating command, and the verify section must contain no
   mutating commands at all.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "deploy/ssh/install_timelapse_tunnel_sshd.sh"
TEMPLATE = ROOT / "deploy/ssh/authorized_keys.timelapse_tunnel"
SSHD_CONF = ROOT / "deploy/ssh/timelapse-tunnel-sshd.conf"

INSTALLER_SRC = INSTALLER.read_text()
TEMPLATE_SRC = TEMPLATE.read_text()
CONF_SRC = SSHD_CONF.read_text()

# Mutating commands that must NEVER appear inside the verify-only section.
MUTATING_PATTERNS = [
    r"\bdscl\s+\.\s+-create",
    r"\bmkdir\b",
    r"\binstall\s+-m",
    r"\bchown\b",
    r"\bchmod\b",
    r"\bssh-keygen\b",
    r"\blaunchctl\s+bootstrap\b",
    r"\blaunchctl\s+kickstart\b",
    r"\blaunchctl\s+bootout\b",
    r"\brm\s+-",
]


# ── Defect 1: correct authorized_keys option syntax ────────────────────────

def test_template_documents_correct_entry_syntax() -> None:
    assert (
        'restrict,port-forwarding,permitlisten="127.0.0.1:2201"' in TEMPLATE_SRC
    ), "template must document the correct device entry for TL-C87FF9587CA0"
    assert (
        'restrict,port-forwarding,permitlisten="127.0.0.1:2204"' in TEMPLATE_SRC
    ), "template must document the correct device entry for TL-043EB9E72EFD"


def test_no_bare_restrict_permitlisten_anywhere() -> None:
    # Any `restrict,` immediately followed by `permitlisten` (without
    # port-forwarding in between) is the silent-failure defect.
    for name, src in (("template", TEMPLATE_SRC), ("installer", INSTALLER_SRC), ("sshd_conf", CONF_SRC)):
        bad = re.findall(r"restrict,permitlisten", src)
        assert not bad, f"{name} contains bare 'restrict,permitlisten' (missing port-forwarding): {bad}"


def test_no_false_claim_that_permitlisten_reenables_forwarding() -> None:
    # Documentation must not claim permitlisten itself re-enables forwarding.
    for name, src in (("template", TEMPLATE_SRC), ("installer", INSTALLER_SRC), ("sshd_conf", CONF_SRC)):
        for m in re.finditer(r"permitlisten", src, re.IGNORECASE):
            ctx = src[max(0, m.start() - 160) : m.end() + 160]
            flat = " ".join(ctx.split()).lower()
                # Portuguese/Danish/English phrasings of the false claim:
            for phrase in (
                "permitlisten re-enables",
                "permitlisten genaktiverer",
                "permitlisten reaktiverer",
                "permitlisten turns forwarding back on",
            ):
                assert phrase not in flat, f"{name} claims '{phrase}' — port-forwarding is the re-enabler, not permitlisten"


def test_installer_selftest_entry_uses_port_forwarding() -> None:
    m = re.search(
        r"printf\s+'restrict,port-forwarding,permitlisten=\"127\.0\.0\.1:%s\"", INSTALLER_SRC
    )
    assert m, "self-test authorized_keys entry must be restrict,port-forwarding,permitlisten=…"


# ── Defect 2: ssh options before destination ───────────────────────────────

SSH_INVOCATION = re.compile(r"^\s*ssh\s+(?P<args>.+)$", re.MULTILINE)


def test_all_ssh_options_precede_destination() -> None:
    offenders: list[str] = []
    for m in SSH_INVOCATION.finditer(INSTALLER_SRC):
        line = m.group("args")
        # Skip documentation/comment lines mentioning ssh usage.
        if line.lstrip().startswith("#"):
            continue
        dest = re.search(r'"\$\{USER_NAME\}@127\.0\.0\.1"', line)
        if not dest:
            continue  # no destination on this (continuation) line
        head = line[: dest.start()]
        tail = line[dest.end() :]
        if '"${SSHOPTS[@]}"' in tail:
            offenders.append("SSHOPTS after destination: ssh " + line.strip())
        # Any trailing -o / -p / -i flag after the destination is a defect.
        if re.search(r'(^|\s)(-[a-zA-Z]|--)', tail):
            offenders.append("options after destination: ssh " + line.strip())
    assert not offenders, "ssh option-order defects:\n" + "\n".join(offenders)


# ── Defect 3: --verify-only provably read-only ─────────────────────────────

def _line_no(needle: str) -> int:
    idx = INSTALLER_SRC.find(needle)
    assert idx >= 0, f"missing marker: {needle!r}"
    return INSTALLER_SRC[:idx].count("\n") + 1


def test_verify_branch_exits_before_first_mutation() -> None:
    verify_start = _line_no('if [[ "$MODE" == "verify" ]]; then')
    verify_exit = _line_no('verify-only complete — NOTHING was modified.')
    first_mutation = _line_no(
        "MUTATIONS BEGIN HERE"
    )
    assert verify_start < first_mutation, "verify branch must precede the mutation section"
    assert verify_exit < first_mutation, (
        f"verify-only must exit (line {verify_exit}) before mutations begin (line {first_mutation})"
    )


def test_verify_section_contains_no_mutating_commands() -> None:
    start = _line_no('if [[ "$MODE" == "verify" ]]; then')
    end = _line_no('verify-only complete — NOTHING was modified.')
    section = "\n".join(INSTALLER_SRC.splitlines()[start - 1 : end])
    for pat in MUTATING_PATTERNS:
        hits = re.findall(pat, section)
        assert not hits, f"verify-only section contains mutating command ({pat}): {hits}"


def test_verify_marker_appears_once_per_mode_branch() -> None:
    # The read-only exit marker must exist exactly once (single verify exit).
    assert INSTALLER_SRC.count("NOTHING was modified.") == 1


# ── Supporting artefact sanity ─────────────────────────────────────────────

def test_config_keeps_server_side_frames() -> None:
    for directive in (
        "AllowTcpForwarding remote",
        "PermitOpen none",
        "GatewayPorts no",
        "PermitListen any",
    ):
        assert directive in CONF_SRC, f"sshd_config lost required directive: {directive}"


def test_template_contains_no_real_key_material() -> None:
    body = "\n".join(
        line for line in TEMPLATE_SRC.splitlines() if not line.lstrip().startswith("#")
    )
    assert not re.search(r"(ssh-(rsa|ed25519)|ecdsa-[a-z0-9-]+) +AAAA[A-Za-z0-9+/]{40,}", body.replace("AAAA…placeholder…", "")), \
        "template must not contain real key material"
