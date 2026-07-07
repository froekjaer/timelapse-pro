-- Migration v16: wb_cast_strength på captures
-- Dato: 2026-07-07
-- Formål: Gør hvidbalance-signalet (cast_strength) til en søgbar, indekseret
-- kolonne på samme måde som blur_score/brightness_mean allerede er — så en
-- drift-detektor kan lave en hurtig SQL-forespørgsel over historikken for et
-- kamera i stedet for at skulle parse ai_result-JSON'en for hver række.
--
-- Additiv/nullable: kolonnen udfyldes KUN når den autonome optimizer på Edge
-- rent faktisk kørte og rapporterede en white_balance-feature (afhænger af
-- quality.edge_ai.run_optimizer-politikken). Mange historiske og fremtidige
-- rækker vil derfor have NULL her — det er forventet og OK, drift-analysen
-- skal håndtere sparse data.
--
-- Se headend/main.py _extract_wb_cast_strength() for hvor værdien udtrækkes
-- fra edge_ai_result ved ingest (receive_capture), og
-- headend/ai/drift_detection.py for hvordan den bruges.

ALTER TABLE captures
    ADD COLUMN IF NOT EXISTS wb_cast_strength DOUBLE PRECISION;

CREATE INDEX IF NOT EXISTS idx_captures_camera_captured_at
    ON captures(camera_id, captured_at)
    WHERE camera_id IS NOT NULL;
