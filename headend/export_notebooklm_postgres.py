#!/usr/bin/env python3
"""
TimeLapse Pro — NotebookLM export fra PostgreSQL headend

Bruger DATABASE_URL fra:
1. miljøvariabel DATABASE_URL
2. launchd plist: /Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist
3. fallback: postgresql://timelapse@localhost/timelapse_db

Output:
  <repo>/headend/exports/notebooklm_YYYYMMDD_HHMMSS/

Filer:
  - notebooklm_summary.md
  - notebooklm_export.jsonl
  - devices.csv
  - captures.csv
  - diagnostics.csv
  - events.csv
  - cameras.csv, customers.csv, sites.csv osv. hvis tabellerne findes
"""

from __future__ import annotations

import csv
import json
import os
import plistlib
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras


PLIST_PATH = Path("/Library/LaunchDaemons/dk.froekjaer.timelapse-headend.plist")
DEFAULT_DATABASE_URL = "postgresql://timelapse@localhost/timelapse_db"
EXPORT_ROOT = Path(os.getenv("TIMELAPSE_NOTEBOOKLM_EXPORT_ROOT", Path(__file__).resolve().parent / "exports"))


CORE_TABLES = [
    "devices",
    "captures",
    "diagnostics",
    "events",
]

OPTIONAL_TABLES = [
    "customers",
    "sites",
    "cameras",
    "users",
    "device_assignments",
    "ssh_tunnel_logs",
    "pending_updates",
    "settings",
    "config_defaults",
]


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def read_database_url() -> str:
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    if PLIST_PATH.exists():
        with PLIST_PATH.open("rb") as f:
            plist_data = plistlib.load(f)

        env = plist_data.get("EnvironmentVariables", {})
        if isinstance(env, dict) and env.get("DATABASE_URL"):
            return env["DATABASE_URL"]

    return DEFAULT_DATABASE_URL


def connect_pg(database_url: str):
    # SQLAlchemy-style URL fallback
    database_url = database_url.replace("postgresql+psycopg2://", "postgresql://")

    return psycopg2.connect(
        database_url,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )


def table_exists(conn, table: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = %s
            ) AS exists
            """,
            (table,),
        )
        return bool(cur.fetchone()["exists"])


def get_columns(conn, table: str) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table,),
        )
        return [r["column_name"] for r in cur.fetchall()]


def export_table_to_csv(conn, table: str, output_file: Path) -> int:
    if not table_exists(conn, table):
        output_file.write_text("", encoding="utf-8")
        return 0

    columns = get_columns(conn, table)
    if not columns:
        output_file.write_text("", encoding="utf-8")
        return 0

    # Vælg en fornuftig sortering hvis kendte tidskolonner findes
    order_col = None
    for candidate in ["captured_at", "recorded_at", "event_at", "last_seen", "created_at", "id"]:
        if candidate in columns:
            order_col = candidate
            break

    col_sql = ", ".join([f'"{c}"' for c in columns])
    query = f'SELECT {col_sql} FROM "{table}"'
    if order_col:
        direction = "DESC" if order_col != "id" else "ASC"
        query += f' ORDER BY "{order_col}" {direction}'

    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()

    if not rows:
        output_file.write_text(",".join(columns) + "\n", encoding="utf-8")
        return 0

    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    return len(rows)


def export_jsonl(conn, tables: list[str], output_file: Path) -> int:
    count = 0

    with output_file.open("w", encoding="utf-8") as f:
        for table in tables:
            if not table_exists(conn, table):
                continue

            columns = get_columns(conn, table)
            if not columns:
                continue

            col_sql = ", ".join([f'"{c}"' for c in columns])

            with conn.cursor() as cur:
                cur.execute(f'SELECT {col_sql} FROM "{table}"')
                rows = cur.fetchall()

            for row in rows:
                record = {
                    "source": "timelapse_headend_postgresql",
                    "table": table,
                    "exported_at": datetime.now(timezone.utc).isoformat(),
                    "data": row,
                }
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                count += 1

    return count


def fetch_all(conn, query: str):
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def safe_query(conn, query: str):
    try:
        return fetch_all(conn, query)
    except Exception:
        conn.rollback()
        return []


def minmax(conn, table: str, col: str):
    if not table_exists(conn, table):
        return None, None

    columns = get_columns(conn, table)
    if col not in columns:
        return None, None

    try:
        with conn.cursor() as cur:
            cur.execute(f'SELECT MIN("{col}") AS min_val, MAX("{col}") AS max_val FROM "{table}"')
            row = cur.fetchone()
        return row["min_val"], row["max_val"]
    except Exception:
        conn.rollback()
        return None, None


def count_table(conn, table: str) -> int:
    if not table_exists(conn, table):
        return 0

    try:
        with conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) AS c FROM "{table}"')
            return int(cur.fetchone()["c"])
    except Exception:
        conn.rollback()
        return 0


def write_summary(conn, out_dir: Path, exported_counts: dict[str, int], jsonl_count: int, database_url_safe: str) -> None:
    captures_min, captures_max = minmax(conn, "captures", "captured_at")
    diagnostics_min, diagnostics_max = minmax(conn, "diagnostics", "recorded_at")
    events_min, events_max = minmax(conn, "events", "event_at")

    device_rows = []
    if table_exists(conn, "devices"):
        cols = get_columns(conn, "devices")

        select_parts = []
        for col in [
            "device_id",
            "customer_name",
            "site_name",
            "camera_name",
            "status",
            "last_seen",
            "app_version",
            "ip_address",
            "config_version",
        ]:
            if col in cols:
                select_parts.append(f'"{col}"')
            else:
                select_parts.append(f"NULL AS {col}")

        device_rows = safe_query(conn, f"""
            SELECT {", ".join(select_parts)}
            FROM devices
            ORDER BY customer_name NULLS LAST, site_name NULLS LAST, camera_name NULLS LAST, device_id
        """)

    quality_rows = []
    if table_exists(conn, "captures"):
        cols = get_columns(conn, "captures")
        if "device_id" in cols:
            quality_pass_expr = (
                "SUM(CASE WHEN quality_passed = true THEN 1 ELSE 0 END) AS quality_passed"
                if "quality_passed" in cols
                else "NULL AS quality_passed"
            )
            avg_blur_expr = (
                "ROUND(AVG(blur_score)::numeric, 2) AS avg_blur_score"
                if "blur_score" in cols
                else "NULL AS avg_blur_score"
            )
            avg_brightness_expr = (
                "ROUND(AVG(brightness_mean)::numeric, 2) AS avg_brightness"
                if "brightness_mean" in cols
                else "NULL AS avg_brightness"
            )
            latest_expr = (
                "MAX(captured_at) AS latest_capture"
                if "captured_at" in cols
                else "NULL AS latest_capture"
            )

            quality_rows = safe_query(conn, f"""
                SELECT
                    device_id,
                    COUNT(*) AS captures_total,
                    {quality_pass_expr},
                    {avg_blur_expr},
                    {avg_brightness_expr},
                    {latest_expr}
                FROM captures
                GROUP BY device_id
                ORDER BY device_id
            """)

    diagnostics_rows = []
    if table_exists(conn, "diagnostics"):
        cols = get_columns(conn, "diagnostics")
        if "device_id" in cols:
            def avg_expr(col: str, alias: str, digits: int = 2):
                if col in cols:
                    return f"ROUND(AVG({col})::numeric, {digits}) AS {alias}"
                return f"NULL AS {alias}"

            def max_expr(col: str, alias: str, digits: int = 2):
                if col in cols:
                    return f"ROUND(MAX({col})::numeric, {digits}) AS {alias}"
                return f"NULL AS {alias}"

            latest_expr = "MAX(recorded_at) AS latest_diagnostic" if "recorded_at" in cols else "NULL AS latest_diagnostic"

            diagnostics_rows = safe_query(conn, f"""
                SELECT
                    device_id,
                    COUNT(*) AS diagnostics_total,
                    {avg_expr("cpu_temp_c", "avg_cpu_temp_c")},
                    {max_expr("cpu_temp_c", "max_cpu_temp_c")},
                    {avg_expr("cpu_load_pct", "avg_cpu_load_pct")},
                    {avg_expr("disk_used_gb", "avg_disk_used_gb")},
                    {avg_expr("ntp_offset_s", "avg_ntp_offset_s", 4)},
                    {avg_expr("upload_queue", "avg_upload_queue")},
                    {latest_expr}
                FROM diagnostics
                GROUP BY device_id
                ORDER BY device_id
            """)

    event_rows = []
    if table_exists(conn, "events"):
        cols = get_columns(conn, "events")
        if "level" in cols:
            event_rows = safe_query(conn, """
                SELECT
                    COALESCE(level, 'unknown') AS level,
                    COALESCE(category, 'unknown') AS category,
                    COUNT(*) AS count
                FROM events
                GROUP BY level, category
                ORDER BY count DESC, level, category
                LIMIT 25
            """)

    lines = []
    lines.append("# TimeLapse Pro — Headend PostgreSQL dataudtræk til NotebookLM")
    lines.append("")
    lines.append(f"**Eksporteret:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"**Database:** `{database_url_safe}`")
    lines.append("")
    lines.append("## 1. Formål")
    lines.append("")
    lines.append(
        "Dette udtræk samler driftsdata fra TimeLapse Pro headend-databasen, "
        "så data kan analyseres i NotebookLM. Fokus er devices, captures, diagnostics og events."
    )
    lines.append("")
    lines.append("## 2. Eksporterede filer")
    lines.append("")
    lines.append("| Fil | Rækker |")
    lines.append("|---|---:|")
    for filename, count in exported_counts.items():
        lines.append(f"| `{filename}` | {count} |")
    lines.append(f"| `notebooklm_export.jsonl` | {jsonl_count} |")
    lines.append("")
    lines.append("## 3. Dataperiode")
    lines.append("")
    lines.append(f"- Captures: `{captures_min}` til `{captures_max}`")
    lines.append(f"- Diagnostics: `{diagnostics_min}` til `{diagnostics_max}`")
    lines.append(f"- Events: `{events_min}` til `{events_max}`")
    lines.append("")
    lines.append("## 4. Databasetabeller")
    lines.append("")
    lines.append("| Tabel | Rækker |")
    lines.append("|---|---:|")
    for table in CORE_TABLES + OPTIONAL_TABLES:
        if table_exists(conn, table):
            lines.append(f"| `{table}` | {count_table(conn, table)} |")
    lines.append("")
    lines.append("## 5. Devices")
    lines.append("")
    if device_rows:
        lines.append("| Device | Kunde | Site | Kamera | Status | Sidst set | App version | Config version | IP |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in device_rows:
            lines.append(
                f"| `{r.get('device_id')}` | {r.get('customer_name') or ''} | {r.get('site_name') or ''} | "
                f"{r.get('camera_name') or ''} | {r.get('status') or ''} | {r.get('last_seen') or ''} | "
                f"{r.get('app_version') or ''} | {r.get('config_version') or ''} | {r.get('ip_address') or ''} |"
            )
    else:
        lines.append("_Ingen device-data fundet._")
    lines.append("")
    lines.append("## 6. Capture-kvalitet per device")
    lines.append("")
    if quality_rows:
        lines.append("| Device | Captures | Quality passed | Avg blur | Avg brightness | Seneste capture |")
        lines.append("|---|---:|---:|---:|---:|---|")
        for r in quality_rows:
            lines.append(
                f"| `{r.get('device_id')}` | {r.get('captures_total')} | {r.get('quality_passed')} | "
                f"{r.get('avg_blur_score')} | {r.get('avg_brightness')} | {r.get('latest_capture')} |"
            )
    else:
        lines.append("_Ingen capture-data fundet._")
    lines.append("")
    lines.append("## 7. Diagnostics per device")
    lines.append("")
    if diagnostics_rows:
        lines.append("| Device | Målinger | Avg temp | Max temp | Avg CPU load | Avg disk GB | Avg NTP offset | Avg upload queue | Seneste diagnostic |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
        for r in diagnostics_rows:
            lines.append(
                f"| `{r.get('device_id')}` | {r.get('diagnostics_total')} | {r.get('avg_cpu_temp_c')} | "
                f"{r.get('max_cpu_temp_c')} | {r.get('avg_cpu_load_pct')} | {r.get('avg_disk_used_gb')} | "
                f"{r.get('avg_ntp_offset_s')} | {r.get('avg_upload_queue')} | {r.get('latest_diagnostic')} |"
            )
    else:
        lines.append("_Ingen diagnostic-data fundet._")
    lines.append("")
    lines.append("## 8. Event-fordeling")
    lines.append("")
    if event_rows:
        lines.append("| Level | Category | Antal |")
        lines.append("|---|---|---:|")
        for r in event_rows:
            lines.append(f"| {r.get('level')} | {r.get('category')} | {r.get('count')} |")
    else:
        lines.append("_Ingen event-data fundet._")
    lines.append("")
    lines.append("## 9. Gode spørgsmål til NotebookLM")
    lines.append("")
    lines.append("- Hvilke devices har dårligst capture quality pass rate?")
    lines.append("- Hvilke kameraer har ikke leveret billeder for nylig?")
    lines.append("- Er der sammenhæng mellem CPU-temperatur og capture-fejl?")
    lines.append("- Hvilke devices har høj NTP-offset?")
    lines.append("- Er der devices med stigende diskforbrug eller upload-kø?")
    lines.append("- Hvilke events indikerer tilbagevendende driftsproblemer?")
    lines.append("- Hvilke sites/kameraer bør prioriteres til service?")
    lines.append("- Er der tegn på config drift mellem devices?")
    lines.append("")
    lines.append("## 10. Sikkerhed")
    lines.append("")
    lines.append(
        "Udtrækket bør behandles som internt/fortroligt. Det kan indeholde device IDs, "
        "IP-adresser, lokationsnavne, timestamps og driftsmetadata. Upload ikke plist-filer, "
        ".env-filer, JWT secrets eller krypteringsnøgler til NotebookLM."
    )
    lines.append("")

    (out_dir / "notebooklm_summary.md").write_text("\n".join(lines), encoding="utf-8")


def mask_database_url(url: str) -> str:
    # Din nuværende URL har ikke password, men denne beskytter hvis det ændrer sig senere.
    if "://" not in url or "@" not in url:
        return url

    scheme, rest = url.split("://", 1)
    auth, hostpart = rest.split("@", 1)

    if ":" in auth:
        user, _password = auth.split(":", 1)
        return f"{scheme}://{user}:********@{hostpart}"

    return url


def main() -> int:
    out_dir = EXPORT_ROOT / f"notebooklm_{now_stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    database_url = read_database_url()
    database_url_safe = mask_database_url(database_url)

    print(f"Forbinder til: {database_url_safe}")

    try:
        conn = connect_pg(database_url)
    except Exception as e:
        print("")
        print("FEJL: Kunne ikke forbinde til PostgreSQL.")
        print(f"Database URL: {database_url_safe}")
        print(f"Fejl: {e}")
        print("")
        print("Prøv evt.:")
        print("  psql postgresql://timelapse@localhost/timelapse_db")
        print("")
        return 1

    all_tables = []
    for table in CORE_TABLES + OPTIONAL_TABLES:
        if table_exists(conn, table):
            all_tables.append(table)

    exported_counts = {}

    for table in all_tables:
        filename = f"{table}.csv"
        print(f"Eksporterer {table} -> {filename}")
        try:
            exported_counts[filename] = export_table_to_csv(conn, table, out_dir / filename)
        except Exception as e:
            conn.rollback()
            print(f"  ADVARSEL: Kunne ikke eksportere {table}: {e}")
            exported_counts[filename] = 0

    jsonl_count = export_jsonl(conn, all_tables, out_dir / "notebooklm_export.jsonl")
    write_summary(conn, out_dir, exported_counts, jsonl_count, database_url_safe)

    conn.close()

    print("")
    print("NotebookLM export færdig")
    print(f"Mappe: {out_dir}")
    print("")
    print("Filer:")
    for f in sorted(out_dir.iterdir()):
        print(f" - {f.name}")
    print("")
    print("Upload til NotebookLM:")
    print(" - notebooklm_summary.md")
    print(" - devices.csv")
    print(" - captures.csv")
    print(" - diagnostics.csv")
    print(" - events.csv")
    print("")
    print("Alternativt upload:")
    print(" - notebooklm_summary.md")
    print(" - notebooklm_export.jsonl")
    print("")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
