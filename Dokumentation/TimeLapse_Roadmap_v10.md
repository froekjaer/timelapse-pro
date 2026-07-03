# TimeLapse Pro — Udviklings-roadmap (v10, konsolideret)

**Version:** 10 (konsolideret)
**Dato:** 2026-07-02
**Konsoliderer:** `TimeLapse_Roadmap_v1.docx`…`_v4.docx` (arkiveret i `Gamle versioner/`). v4 (14. apr 2026) er backbone.

> **Udviklingsnote:** Roadmappen blev skrevet i Canon/RPi5-æraen. Aktuel status og fremadrettet plan føres nu i `KRAVREGISTER_og_STATUS_v10.md` (§4 tidslinje + Sprint H–N) og `GO_LIVE_CHECKLIST_v10.md`. Nedenstående bevarer den historiske sprint-plan.

## 1. Gennemførte milepæle (Fase 1–2 + Sprint A+B, marts–april 2026)

Bootstrap/provisioning (zero-touch, MAC-afledt device_id), Canon EOS-integration (gphoto2, relay-GPIO, shutter-tracking), store-and-forward SFTP-upload (SHA-256, retry, 50 GB circular buffer), Web UI (timeline-navigator, 16:9 thumbnails 320×180), LAB mode (preview uden lukker-forbrug, histogram, WiFi-konfig, camera-ready), kamera-diagnostik (batteri, shutter-tæller alarm >80%, config drift, NTP-offset), histogram/kvalitetsgrafer (RGB+luminans, blur/lysstyrke over tid), GitHub + CI/CD (17 tests, Pi5-poller, edge self-update ~33s), hierarkisk config (5-lag Global→Kunde→Site→Kamera→Runtime), EXIF+GPS, parameter-persistens, multi-kamera burst (GPIO 356/357), SHA-256 billedintegritet (pre-XMP), sidecar JSON, udev USB-symlinks, timelapse-video (FFmpeg: FPS, opløsning, codec, crop, fade, Ken Burns), dag/nat-filter (astronomisk solhøjde), blur+lysstyrke-filter (Laplacian variance), TimelapseVideoPage, ensure_utc + wifi_ssid fixes.

## 2. Sprint C — RBAC, autentificering, reverse SSH (4 uger)

5 roller, MFA, sikker remote-adgang via reverse SSH m. customer approval. Faser: (1) RBAC-fundament — DB-schema (users, sessions, mfa_secrets, audit_log, user_customers, ssh_approvals), JWT RS256, bcrypt, TOTP/MFA, magic link, OAuth2-stub, permission-matrix, FastAPI-middleware (require_auth/role/customer), audit-decorator, customer_id row-level filter, Fernet key-store, path-traversal fix, FFmpeg whitelist. (2) Frontend auth — LoginPage, MFASetupPage, UserManagementPage, AuthContext (JWT i memory, aldrig localStorage), ProtectedRoute, SessionTimeout. (3) Reverse SSH + RBAC-integration.

## 3. Sprint D — Production hardening (Q2 2026)

HTTPS, kryptering, monitoring, operations-dashboard, GDPR/compliance.

## 4. Sprint E — Compliance og certificering (Q3 2026)

## 5. Fase 4 — Avancerede features (2027+)

## 6. Support-tiers og 7. Kendte begrænsninger

Ført videre i `ADMINISTRATORMANUAL_v10.md` og `KRAVREGISTER_og_STATUS_v10.md`.
