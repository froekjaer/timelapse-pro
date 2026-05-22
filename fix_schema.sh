#!/bin/bash
# Fix: kør schema_v2.sql (base) FØR schema_v2_patch.sql
# Kør fra: ~/projects/timelapse-pro

DB="timelapse_db"
HEADEND="$HOME/projects/timelapse-pro/headend"

echo "▶ Kører base schema (schema_v2.sql)..."
psql $DB -f "$HEADEND/schema_v2.sql" 2>&1 | grep -v "already exists" | grep -v "^$" || true

echo ""
echo "▶ Kører patch (schema_v2_patch.sql)..."
psql $DB -f "$HEADEND/ai/schema_v2_patch.sql" 2>&1 | grep -v "already exists" | grep -v "^$" || true

echo ""
echo "✅ Verificerer tabeller:"
psql $DB -c "\dt ai_*" 2>/dev/null
psql $DB -c "\dt gdpr_*" 2>/dev/null
