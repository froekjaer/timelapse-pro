-- ═══════════════════════════════════════════════════════════════════════
-- Migration v7: Netværkskonfiguration per kamera-lokation
-- Gemmer foretrukket netværkstype (Ethernet/WiFi/USB modem) og
-- WiFi-legitimationsoplysninger direkte på Camera-entiteten, så
-- edge-provisioning automatisk præudfylder konfigurationen.
-- ═══════════════════════════════════════════════════════════════════════

ALTER TABLE cameras
    ADD COLUMN IF NOT EXISTS network_type   VARCHAR(20) DEFAULT 'ethernet';
    -- 'ethernet' | 'wifi' | 'usb_modem'

ALTER TABLE cameras
    ADD COLUMN IF NOT EXISTS wifi_ssid      VARCHAR(200) DEFAULT NULL;

ALTER TABLE cameras
    ADD COLUMN IF NOT EXISTS wifi_password  VARCHAR(200) DEFAULT NULL;
    -- Gemt i klartekst internt — adgang kræver admin-rolle.
    -- Til produktion: overvej kryptering med TIMELAPSE_GPG_KEY.

ALTER TABLE cameras
    ADD COLUMN IF NOT EXISTS wifi_country   VARCHAR(2) DEFAULT 'DK';
