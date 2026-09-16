#!/usr/bin/env python3
"""
Check/refresh the local cache of Mission Framework's canonical OP-001
(Mission Operational Preamble) against the authoritative upstream source.

Architecture (Peter, 2026-09-16): "C - canonical Mission Framework source
with controlled local cache/fallback". froekjaer/mission-framework is the
sole authoritative source for OP-001. This script is the explicit, human-
or-agent-triggered refresh mechanism; it is never run silently/automatically
as part of routine repo operations, and it never overwrites the cache
without recording what it did in OP-001.provenance.json.

Two independent questions, checked separately:

  LOCAL INTEGRITY - does the cached file's content actually match what its
  own provenance record says it should be? This is a purely local digest
  comparison over the file's raw bytes, needs no network, and is checked on
  every invocation before anything else. A mismatch means the file was
  modified, corrupted, or a previous refresh was interrupted partway - never
  silently trusted, and never allowed to crash the checker (tampering that
  happens to break UTF-8 decoding is exactly the kind of thing this check
  exists to catch, not something it should choke on).

  REMOTE FRESHNESS - does canonical's current HEAD match the cached
  revision? Needs network; absence of network is not evidence of staleness
  and is never reported as such.

last_check_result values:
  VERIFIED  - local integrity confirmed AND (canonical unreachable-but-
              previously-verified, or canonical reachable and HEAD matches
              the cached revision).
  STALE     - local integrity confirmed, canonical reachable, and its HEAD
              differs from the cached revision. Evidence-based, never a
              guess.
  UNKNOWN   - freshness/integrity cannot currently be established (network
              unreachable, or provenance lacks a content digest to check
              against). The cache remains usable at its last known state;
              this is not itself an error.
  CORRUPTED - local integrity check found the cached file's actual bytes do
              not match the digest recorded for them. Never silently
              rewritten. If a previous known-good backup exists and is
              itself internally consistent, it is restored automatically
              and used; otherwise the cache is not usable with confidence
              and --bootstrap is required.

Trust model, stated plainly: the content digest binds the cached bytes to
the provenance record this script itself wrote after a previous successful
fetch from canonical. It proves "these bytes are the ones this repository
previously fetched and recorded" - i.e. it detects LOCAL tampering/corruption
after the fact. It does NOT independently authenticate GitHub, and does NOT
create a cryptographic trust anchor beyond ordinary HTTPS to
api.github.com/raw.githubusercontent.com: the digest and the content it
describes both originate from the same remote trust domain at fetch time, so
a compromise of that domain at fetch time is not detected by this mechanism.
Four distinct things this script does and does not do:
  - canonical revision discovery: yes (via the GitHub API, HTTPS).
  - remote content consistency: yes, between the SHA check and the content
    fetch in the same run (immutable-SHA-pinned, no mutable-ref window).
  - local content integrity: yes, after the fact, against this script's own
    previously recorded digest (this is what stops silent local tampering).
  - source authenticity: NOT independently established - this script trusts
    GitHub's TLS certificate and API response at fetch time, same as any
    HTTPS client would; it adds no separate signature or trust anchor.

Refresh is a single logical transaction (new content + new provenance).
Before applying it, the current valid active pair (if internally consistent)
is backed up to *.prev sibling files. New content and provenance are written
to temp files in the same directory, fsync'd, then applied via os.replace().
Two separate os.replace() calls are not atomic as a pair - if a failure
happens between them, the *.prev backup and the local-integrity check above
are what prevent a mixed pair from ever being read back as VERIFIED, and
allow automatic recovery to the last known-good state on the next check.

Usage:
  python3 refresh_op001_cache.py            # check only, do not modify the cache
  python3 refresh_op001_cache.py --refresh  # if STALE, fetch and apply the new content
  python3 refresh_op001_cache.py --bootstrap  # (re)create from scratch from canonical HEAD
  python3 refresh_op001_cache.py --json     # machine-readable output on stdout
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CANONICAL_REPOSITORY = "froekjaer/mission-framework"
CANONICAL_PATH = "docs/operational/OP-001-Mission-Operational-Preamble.md"
CANONICAL_BRANCH = "main"

HERE = Path(__file__).resolve().parent
CACHED_FILE = HERE / "OP-001-Mission-Operational-Preamble.md"
PROVENANCE_FILE = HERE / "OP-001.provenance.json"
CACHED_FILE_PREV = HERE / "OP-001-Mission-Operational-Preamble.md.prev"
PROVENANCE_FILE_PREV = HERE / "OP-001.provenance.json.prev"

# Only ever read from api.github.com/raw.githubusercontent.com over HTTPS.
# The commit SHA used to build the raw-content URL always comes from this
# script's own GitHub API call in the same run, never from user input or
# from a previously cached value being blindly re-trusted as "current" -
# see _fetch_canonical_head_sha().
API_REF_URL = f"https://api.github.com/repos/{CANONICAL_REPOSITORY}/git/refs/heads/{CANONICAL_BRANCH}"
RAW_URL_TEMPLATE = f"https://raw.githubusercontent.com/{CANONICAL_REPOSITORY}/{{sha}}/{CANONICAL_PATH}"
HTTP_USER_AGENT = "TimeLapsePro-OP001-Cache/1.1"
REQUEST_TIMEOUT_S = 10

EXPECTED_CONTENT_MARKER = "# OP-001 — Mission Operational Preamble (MOP)".encode("utf-8")
MIN_EXPECTED_LENGTH = 2000  # sanity floor; the real document is ~9-12 KB

# Exceptions treated as expected operational failures (network, filesystem):
# reported cleanly with a message and a non-zero exit, never as a raw
# traceback. Anything else (e.g. a real bug) is allowed to propagate.
_EXPECTED_FAILURE_TYPES = (urllib.error.URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError)


class CacheError(Exception):
    """An expected, operator-facing failure (network, filesystem, integrity)."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_hex_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _write_provenance(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def _pair_is_internally_consistent(content_path: Path, provenance_path: Path) -> tuple[bool, dict | None, str]:
    """Returns (consistent, provenance_or_None, reason). Never raises for an
    ordinary inconsistency, including content that is corrupted badly enough
    to not even be valid UTF-8 - that is itself reported as an inconsistency
    (via the byte-level digest mismatch), not allowed to crash the checker."""
    if not content_path.is_file() or not provenance_path.is_file():
        return False, None, "one or both files missing"
    try:
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, None, f"provenance unreadable/not valid JSON: {exc}"
    digest = provenance.get("content_sha256")
    if digest is None:
        return False, provenance, "provenance has no content_sha256 recorded"
    if not _is_hex_digest(digest):
        return False, provenance, "provenance content_sha256 is malformed"
    try:
        actual_bytes = content_path.read_bytes()
    except OSError as exc:
        return False, provenance, f"content unreadable: {exc}"
    actual = _sha256_hex(actual_bytes)
    if actual != digest:
        return False, provenance, f"content digest mismatch (expected {digest}, actual {actual})"
    return True, provenance, "ok"


def _fetch_canonical_head_sha() -> str:
    """Returns the current immutable commit SHA of canonical OP-001's branch.

    Raises CacheError on any failure - callers must treat this as "cannot
    currently verify" (UNKNOWN), never as evidence of staleness.
    """
    req = urllib.request.Request(API_REF_URL, headers={"User-Agent": HTTP_USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except _EXPECTED_FAILURE_TYPES as exc:
        raise CacheError(f"could not reach canonical ref API: {exc}") from exc
    sha = payload.get("object", {}).get("sha")
    if not isinstance(sha, str) or len(sha) != 40 or not all(c in "0123456789abcdef" for c in sha):
        raise CacheError(f"unexpected ref response, refusing to trust it as a commit SHA: {payload!r}")
    return sha


def _fetch_canonical_content(sha: str) -> bytes:
    """Fetch OP-001's raw bytes pinned to an exact, already-verified commit SHA
    (never a branch name), so the content cannot change between the SHA check
    and the content fetch (no mutable-ref TOCTOU window). Returns bytes, not
    str, so the digest bound to this content describes exactly what is
    written to disk - no decode/encode round-trip in between."""
    url = RAW_URL_TEMPLATE.format(sha=sha)
    req = urllib.request.Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            content = resp.read()
    except _EXPECTED_FAILURE_TYPES as exc:
        raise CacheError(f"could not fetch canonical content: {exc}") from exc
    if EXPECTED_CONTENT_MARKER not in content or len(content) < MIN_EXPECTED_LENGTH:
        raise CacheError(
            "Fetched content failed a basic integrity sanity check (missing expected "
            "heading or implausibly short) - refusing to apply it to the cache."
        )
    return content


def _write_new_state_transactionally(new_content: bytes, new_provenance: dict) -> None:
    """Applies (new_content, new_provenance) as one logical transaction.

    Backs up the current active pair to *.prev first (only if it is itself
    internally consistent - never backs up known-bad state over a good one).
    Writes both new files to temp files in the same directory and fsyncs
    them before either is made active via os.replace(). A failure between
    the two os.replace() calls leaves a detectable mismatch (caught by
    _pair_is_internally_consistent on the next check()), not a silent
    false VERIFIED - the *.prev backup made here is what the recovery path
    falls back to.
    """
    consistent, _, _ = _pair_is_internally_consistent(CACHED_FILE, PROVENANCE_FILE)
    if consistent:
        try:
            shutil.copy2(CACHED_FILE, CACHED_FILE_PREV)
            shutil.copy2(PROVENANCE_FILE, PROVENANCE_FILE_PREV)
        except OSError as exc:
            raise CacheError(f"could not back up current valid cache before refresh: {exc}") from exc

    content_tmp_name: str | None = None
    provenance_tmp_name: str | None = None
    try:
        content_fd, content_tmp_name = tempfile.mkstemp(dir=HERE, prefix=".op001-content-", suffix=".tmp")
        with open(content_fd, "wb") as f:
            f.write(new_content)
            f.flush()
            os.fsync(f.fileno())

        provenance_fd, provenance_tmp_name = tempfile.mkstemp(dir=HERE, prefix=".op001-provenance-", suffix=".tmp")
        with open(provenance_fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(new_provenance, indent=2, sort_keys=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

        os.replace(content_tmp_name, CACHED_FILE)
        os.replace(provenance_tmp_name, PROVENANCE_FILE)
    except OSError as exc:
        for tmp_name in (content_tmp_name, provenance_tmp_name):
            if tmp_name is not None:
                Path(tmp_name).unlink(missing_ok=True)
        raise CacheError(
            f"write failure while committing refreshed cache: {exc}. If the active cache is now "
            "inconsistent, the next check will detect it and recover from the *.prev backup if one "
            "exists, or report CORRUPTED if not."
        ) from exc


def _try_recover_from_backup() -> tuple[bool, dict | None, str]:
    """If *.prev is itself internally consistent, restore it as active.
    Returns (recovered, provenance_or_None, reason)."""
    consistent, provenance, reason = _pair_is_internally_consistent(CACHED_FILE_PREV, PROVENANCE_FILE_PREV)
    if not consistent:
        return False, None, f"no usable backup ({reason})"
    try:
        shutil.copy2(CACHED_FILE_PREV, CACHED_FILE)
        shutil.copy2(PROVENANCE_FILE_PREV, PROVENANCE_FILE)
    except OSError as exc:
        return False, None, f"backup found but could not be restored: {exc}"
    return True, provenance, "restored from *.prev backup"


def bootstrap() -> dict:
    """Create the cache and provenance file from scratch (first-time setup, or
    recovery after the cache/provenance file was lost/corrupted). Always fetches
    canonical content fresh - never trusts a pre-existing, possibly-tampered
    cache file as a starting point. Does not consult or preserve *.prev."""
    checked_at = _now_iso()
    head_sha = _fetch_canonical_head_sha()
    content = _fetch_canonical_content(head_sha)
    digest = _sha256_hex(content)
    provenance = {
        "canonical_repository": CANONICAL_REPOSITORY,
        "canonical_path": CANONICAL_PATH,
        "cached_revision": head_sha,
        "content_sha256": digest,
        "cached_at": checked_at,
        "last_check_at": checked_at,
        "last_check_result": "VERIFIED",
        "last_check_note": "bootstrapped from canonical HEAD",
    }
    try:
        CACHED_FILE.write_bytes(content)
        _write_provenance(PROVENANCE_FILE, provenance)
    except OSError as exc:
        raise CacheError(f"could not write bootstrapped cache: {exc}") from exc
    return {"bootstrapped": True, "cached_revision": head_sha, "content_sha256": digest, "checked_at": checked_at}


def check(apply_refresh: bool) -> dict:
    result: dict = {"checked_at": _now_iso()}

    if not any(p.exists() for p in (CACHED_FILE, PROVENANCE_FILE, CACHED_FILE_PREV, PROVENANCE_FILE_PREV)):
        # Nothing has ever been created here - this is a setup gap, not
        # tampering/corruption of something that existed. Say so plainly
        # rather than reporting a fabricated CORRUPTED verdict.
        raise CacheError(
            "No cache found (neither active nor backup files exist). This directory has not been "
            "bootstrapped yet. Run this script with --bootstrap to create it from canonical."
        )

    # --- Local integrity check first. Purely local, needs no network,
    # always available offline. A mismatch is investigated (and, where
    # possible, recovered from *.prev) before any network call is made. ---
    consistent, provenance, reason = _pair_is_internally_consistent(CACHED_FILE, PROVENANCE_FILE)
    if not consistent:
        if provenance is not None and provenance.get("content_sha256") is None:
            # We simply lack the means to check (e.g. pre-digest provenance
            # format) - not positive evidence of tampering. Do not touch
            # anything or attempt recovery for a problem we haven't observed.
            result.update(
                last_check_result="UNKNOWN",
                reason=f"cannot verify local integrity: {reason}",
                cache_usable=CACHED_FILE.is_file(),
                cached_revision=provenance.get("cached_revision"),
            )
            return result

        # Positive evidence of a problem (digest present but doesn't match,
        # malformed digest, or files missing/unreadable). Attempt recovery
        # from a known-good backup; never silently rewrite the bad state.
        recovered, recovered_provenance, recover_reason = _try_recover_from_backup()
        if recovered:
            result.update(
                last_check_result=recovered_provenance.get("last_check_result", "VERIFIED"),
                cached_revision=recovered_provenance.get("cached_revision"),
                content_sha256=recovered_provenance.get("content_sha256"),
                recovered_from_backup=True,
                recovery_reason=reason,
                cache_usable=True,
            )
            return result

        result.update(
            last_check_result="CORRUPTED",
            reason=reason,
            recovered_from_backup=False,
            recovery_reason=recover_reason,
            cached_revision=provenance.get("cached_revision") if provenance else None,
            cache_usable=False,
        )
        return result

    # --- Local integrity confirmed. Proceed to remote freshness check. ---
    cached_revision = provenance.get("cached_revision")
    result["cached_revision"] = cached_revision
    result["content_sha256"] = provenance.get("content_sha256")
    result["previous_last_check_result"] = provenance.get("last_check_result")
    result["previous_last_check_at"] = provenance.get("last_check_at")

    try:
        head_sha = _fetch_canonical_head_sha()
    except CacheError as exc:
        provenance["last_check_at"] = result["checked_at"]
        provenance["last_check_result"] = "UNKNOWN"
        provenance["last_check_note"] = f"canonical unreachable: {exc}"
        _write_provenance(PROVENANCE_FILE, provenance)
        result.update(last_check_result="UNKNOWN", reason=str(exc), cache_usable=True)
        return result

    result["canonical_head_sha"] = head_sha

    if head_sha == cached_revision:
        provenance["last_check_at"] = result["checked_at"]
        provenance["last_check_result"] = "VERIFIED"
        provenance.pop("last_check_note", None)
        _write_provenance(PROVENANCE_FILE, provenance)
        result.update(last_check_result="VERIFIED", cache_usable=True)
        return result

    # Genuinely stale: canonical was reachable and its HEAD differs from cache.
    result.update(last_check_result="STALE", cache_usable=True)

    if apply_refresh:
        try:
            new_content = _fetch_canonical_content(head_sha)
        except CacheError as exc:
            provenance["last_check_at"] = result["checked_at"]
            provenance["last_check_result"] = "STALE"
            provenance["last_check_note"] = f"canonical HEAD {head_sha} differs from cache; refresh content fetch failed: {exc}"
            _write_provenance(PROVENANCE_FILE, provenance)
            result.update(refreshed=False, refresh_error=str(exc))
            return result

        new_digest = _sha256_hex(new_content)
        new_provenance = {
            "canonical_repository": provenance.get("canonical_repository", CANONICAL_REPOSITORY),
            "canonical_path": provenance.get("canonical_path", CANONICAL_PATH),
            "cached_revision": head_sha,
            "content_sha256": new_digest,
            "cached_at": result["checked_at"],
            "last_check_at": result["checked_at"],
            "last_check_result": "VERIFIED",
            "last_check_note": "refreshed to canonical HEAD in this run",
        }
        try:
            _write_new_state_transactionally(new_content, new_provenance)
        except CacheError as exc:
            result.update(refreshed=False, refresh_error=str(exc))
            return result

        result.update(refreshed=True, new_cached_revision=head_sha, new_content_sha256=new_digest)
        return result

    # STALE, not refreshed: record the observation without touching content.
    provenance["last_check_at"] = result["checked_at"]
    provenance["last_check_result"] = "STALE"
    provenance["last_check_note"] = f"canonical HEAD {head_sha} differs from cached_revision {cached_revision}"
    _write_provenance(PROVENANCE_FILE, provenance)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="If STALE, fetch and apply the new canonical content (rewrites the cached body; commit the result yourself).")
    parser.add_argument("--bootstrap", action="store_true", help="Create the cache and provenance file from scratch from canonical HEAD (first-time setup or recovery). Requires canonical to be reachable.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a human-readable summary.")
    args = parser.parse_args()

    try:
        if args.bootstrap:
            result = bootstrap()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Bootstrapped cache at canonical revision {result['cached_revision']} (content_sha256 {result['content_sha256'][:12]}...).")
            return 0

        result = check(apply_refresh=args.refresh)
    except CacheError as exc:
        # Expected operational failure - clean message, non-zero exit, no traceback.
        if args.json:
            print(json.dumps({"error": str(exc)}, indent=2))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
        return 0 if result.get("last_check_result") != "CORRUPTED" else 1

    state = result["last_check_result"]
    if state == "VERIFIED":
        if result.get("recovered_from_backup"):
            print(
                f"VERIFIED (recovered) - active cache was inconsistent ({result.get('recovery_reason')}); "
                f"restored from *.prev backup at revision {result.get('cached_revision')}. "
                "Investigate what interrupted the previous refresh."
            )
        else:
            print(f"VERIFIED - cached OP-001 matches canonical HEAD ({result['cached_revision']}).")
    elif state == "STALE":
        if result.get("refreshed"):
            print(f"STALE -> REFRESHED - cache updated to canonical HEAD {result['new_cached_revision']}. Review and commit the change.")
        elif "refresh_error" in result:
            print(f"STALE - refresh was attempted but failed: {result['refresh_error']}. Previous valid cache is unchanged and still usable.")
        else:
            print(
                f"STALE - canonical HEAD is {result.get('canonical_head_sha')}, cache is pinned to "
                f"{result['cached_revision']}. Re-run with --refresh to update, or record this as an "
                "explicit propagation gap if you cannot refresh now."
            )
    elif state == "CORRUPTED":
        print(
            f"CORRUPTED - local cache content does not match its recorded digest ({result.get('reason')}), "
            f"and no usable backup was found ({result.get('recovery_reason')}). The cache is NOT usable with "
            "confidence. Nothing has been overwritten - inspect it, then run --bootstrap to recreate it from "
            "canonical once you have preserved whatever forensic evidence you need.",
            file=sys.stderr,
        )
        return 1
    else:
        print(
            "UNKNOWN - could not establish freshness/integrity "
            f"({result.get('reason')}). The cached OP-001 remains usable as-is; its last confirmed state was "
            f"{result.get('previous_last_check_result')!r} as of {result.get('previous_last_check_at')!r} "
            f"against cached_revision {result.get('cached_revision')!r}. This session's governance work may "
            "proceed offline, but this gap should be visible in any consequential Visible Preamble Record."
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
