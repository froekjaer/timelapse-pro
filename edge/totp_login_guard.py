"""Single-use TOTP verification and a persisted "last known good time" floor
for the Edge's local management login (edge/scripts/totp-service.py).

Added 2026-10-01 (Peter). Two problems on the local login:

1. pyotp.TOTP.verify(code, valid_window=N) accepts the same code again and
   again for its whole validity window (about +-90 s with N=3). A code seen
   over someone's shoulder could be replayed. Here every accepted code moves
   a persisted "last accepted time step" forward, and only strictly newer
   steps are accepted afterwards.

2. When the Edge clock is wrong (no Headend/NTP, no GPS fix yet), every code
   fails and the technician cannot get in to fix the clock. The login page may
   therefore set the clock from the technician's browser time -- but only if
   the code is valid *at that browser time*, the Edge clock is NOT already
   synchronised (enforced by the caller), and the browser time is not earlier
   than the persisted floor. The floor is the time of the last accepted login,
   so a code recorded earlier cannot be used to wind the clock back and replay
   it.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path

# Dependency-free on purpose: the Bluetooth technician service shares this
# guard (and its state file) and runs without pyotp.
from totp_verifier import matching_steps

DEFAULT_STATE_PATH = Path("/etc/timelapse/totp-login-state.json")
STEP_S = 30
# Browser-supplied times outside this range are rejected outright
# (2026-01-01 .. 2100-01-01 UTC).
MIN_PLAUSIBLE_EPOCH = 1767225600
MAX_PLAUSIBLE_EPOCH = 4102444800


class TotpLoginGuard:
    def __init__(self, state_path: Path = DEFAULT_STATE_PATH):
        self._path = Path(state_path)
        self._lock = threading.Lock()

    @contextmanager
    def _locked(self):
        """Thread + cross-process lock: the web login (totp-service) and the
        Bluetooth technician service consume codes from the same state."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, open(str(self._path) + ".lock", "a") as lock_fh:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)

    # -- persisted state ---------------------------------------------------
    def _load(self) -> dict:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return {
                "last_step": int(data.get("last_step", 0)),
                "clock_floor": float(data.get("clock_floor", 0.0)),
            }
        except (OSError, ValueError, TypeError):
            return {"last_step": 0, "clock_floor": 0.0}

    def _save(self, state: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), prefix=".totp-login-state.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(state, fh)
            os.chmod(tmp, 0o600)
            os.replace(tmp, self._path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def clock_floor(self) -> float:
        return self._load()["clock_floor"]

    # -- verification ------------------------------------------------------
    def verify_and_consume(self, secret: str, code: str, at_epoch: float, valid_window: int) -> int | None:
        """Return the accepted time step, or None.

        Accepts ``code`` only for a time step within +-valid_window of
        ``at_epoch`` that is strictly newer than every previously accepted
        step, then records it (and raises the clock floor) atomically.
        """
        code = (code or "").strip()
        with self._locked():
            state = self._load()
            for step in matching_steps(secret, code, now=at_epoch, window=max(0, int(valid_window))):
                if step <= state["last_step"]:
                    continue
                state["last_step"] = step
                state["clock_floor"] = max(state["clock_floor"], float(step * STEP_S))
                self._save(state)
                return step
        return None

    def browser_time_acceptable(self, epoch: float) -> tuple[bool, str]:
        if not (MIN_PLAUSIBLE_EPOCH <= epoch <= MAX_PLAUSIBLE_EPOCH):
            return False, "Enhedens tid er ikke plausibel"
        floor = self.clock_floor()
        if floor and epoch < floor - STEP_S:
            return False, "Enhedens tid er før Edgens sidst kendte korrekte tid"
        return True, ""
