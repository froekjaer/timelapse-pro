# Modem Wake-Up Coordinator — Design

**Version:** 1.0
**Dato:** 13. juli 2026
**Formål:** Koordinere alle API kald i én modem wake-up periode

---

## Problem

I dag har hver API kald sit eget interval:
- Config poll: 5 min
- Heartbeat: 60 min
- SIEM forward: 5 min
- Upload retry: varierende

Resultat: Modem tænder/slukker mange gange unødvendigt.

## Løsning: Modem Wake-Up Coordinator

En coordinator der:
1. Samler alle due API kald i én batch
2. Tænder modem én gang
3. Udfører alle kald
4. Slukker modem

## Implementation

```python
class ModemWakeUpCoordinator:
    """
    Koordinerer alle API kald for at minimere modem active tid.

    Strategi:
    - Saml alle due kald
    - Udfør dem i én batch
    - Returner til sleep
    """

    def __init__(self, agent):
        self._agent = agent
        self._last_coordination = datetime.min

    def should_coordinate(self, now: datetime) -> bool:
        """Tjek om nogen API kald er due."""
        return (
            self._config_poll_due(now) or
            self._heartbeat_due(now) or
            self._siem_forward_due(now) or
            self._uploads_due(now)
        )

    def coordinate_batch(self, now: datetime):
        """Udfør alle due API kald i én batch."""
        log.info("Modem wake-up: koordinerer API kald batch")

        # Tænd modem (implicit ved første kald)
        calls_made = []

        # Config poll
        if self._config_poll_due(now):
            self._agent._pull_config()
            self._agent._check_backup_request()
            self._agent._check_update()
            calls_made.append("config")

        # Heartbeat
        if self._heartbeat_due(now):
            self._agent._send_heartbeat()
            self._agent._sync_captures()
            calls_made.append("heartbeat")

        # SIEM forward
        if self._siem_forward_due(now):
            self._agent._forward_siem_logs()
            calls_made.append("siem")

        # Uploads
        if self._uploads_due(now):
            self._agent._retry_pending_uploads_if_slot()
            calls_made.append("upload")

        log.info("Modem wake-up: udførte %d kald: %s", len(calls_made), calls_made)
        self._last_coordination = now
```

## Integration i _tick

```python
def _tick(self, mode: str) -> None:
    now = datetime.now(timezone.utc)

    # Capture check (prioriteret - har sit eget wakeup)
    capture_due = self._should_capture(now, mode)
    if capture_due:
        # ... capture logic ...

    # Koordiner alle andre API kald
    if self._modem_coordinator.should_coordinate(now):
        self._modem_coordinator.coordinate_batch(now)

    # Sleep med smart wake-up
    sleep_s = self._seconds_until_next_event(now, mode)
    max_idle = self._cfg.get("system", {}).get("max_idle_sleep_s", 300)
    self._stop_event.wait(min(sleep_s, max_idle))
```

## Effekt

Før:
- Modem tænder 5-10 gange per time (config + SIEM + upload)
- Total modem active tid: ~5-10 minutter per time

Efter:
- Modem tænder 1-2 gange per time (koordineret batch)
- Total modem active tid: ~2-3 minutter per time

**Besparelse: 60-70% modem active tid**
