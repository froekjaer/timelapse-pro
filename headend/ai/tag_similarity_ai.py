"""
TimeLapse Pro — AI-drevet Tag Lighed via Gemini (Vertex AI)
============================================================
Sender alle brugte tags til Gemini og beder den gruppere semantisk
lignende tags og foreslå fælles canonical tag-navne.
Data forbliver i EU (europe-west1/west4).
"""
from __future__ import annotations
import json, logging, os, re
log = logging.getLogger(__name__)

SIMILARITY_PROMPT = """Du er ekspert i dansk tagklassificering for byggeplads-dokumentation.

Her er ALLE tags fra vores system (format: id:tag_navn ×antal_gange_brugt):

{tag_list}

Find grupper af tags der BETYDER DET SAMME eller næsten det samme.

Eksempler der BØR grupperes:
- overskyet_vejr + skyet_vejr + overskyet → én gruppe
- worker + arbejder → én gruppe
- byggeplads_på_afstand + byggeplads_i_baggrunden → én gruppe

Eksempler der IKKE må grupperes:
- råhus vs råhus_opførelse (forskellig detaljegrad)
- arbejder vs arbejder_aktiv (forskellig tilstand)
- kran vs tårnkran (forskellig type)

For canonical tag: vælg det mest præcise danske tag.

Returner KUN dette JSON:
{{
  "groups": [
    {{
      "canonical": "bedste_tag_navn",
      "ids": [1, 2, 3],
      "reason": "Kort forklaring på dansk"
    }}
  ]
}}

Kun grupper med mindst 2 tags. KUN JSON."""


def get_ai_similar_tags(db, limit: int = 50) -> list[dict]:
    """Send alle brugte tags til Gemini og få semantiske grupper tilbage."""
    from sqlalchemy import text

    rows = db.execute(text("""
        SELECT id, tag, category, count, approved, rejected
        FROM ai_tag_vocabulary
        WHERE rejected = FALSE AND count > 0
        ORDER BY count DESC, tag
        LIMIT 400
    """)).mappings().all()

    tags = [dict(r) for r in rows]
    if not tags:
        return []

    tag_map = {t["id"]: t for t in tags}
    tag_list = "\n".join(
        f'{t["id"]}:{t["tag"]} ×{t.get("count", 0)}'
        for t in tags
    )

    prompt = SIMILARITY_PROMPT.format(tag_list=tag_list)

    # Hent Gemini-konfiguration fra DB
    try:
        from ai.settings_helper import get_setting
        sa_path    = get_setting(db, "gcp_service_account_path", "")
        project_id = get_setting(db, "gcp_project_id", "")
        location   = get_setting(db, "gcp_location", "europe-west1")
    except Exception:
        from settings_helper import get_setting
        sa_path    = get_setting(db, "gcp_service_account_path", "")
        project_id = get_setting(db, "gcp_project_id", "")
        location   = get_setting(db, "gcp_location", "europe-west1")

    from google import genai
    from google.genai import types

    # Tag-analyse: brug AI Studio nøgle (ingen persondata i tags)
    try:
        from ai.settings_helper import get_setting as _gs
    except Exception:
        from settings_helper import get_setting as _gs
    api_key = _gs(db, "gemini_api_key", "")

    if api_key:
        client = genai.Client(api_key=api_key)
    elif sa_path and os.path.exists(sa_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = sa_path
        client = genai.Client(vertexai=True, project=project_id, location=location)
    else:
        raise ValueError("Ingen Gemini API-nøgle eller service account konfigureret")

    log.info("Sender %d tags til Gemini for lighed-analyse...", len(tags))
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=4000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )

    parsed = _parse_json(response.text)
    groups = []

    for grp in parsed.get("groups", []):
        ids = [int(x) for x in grp.get("ids", []) if x]
        members = [tag_map[i] for i in ids if i in tag_map]
        if len(members) < 2:
            continue

        canonical = grp.get("canonical", "")
        if not canonical:
            canonical = max(members,
                key=lambda t: (bool(t.get("approved")), t.get("count") or 0, -len(t["tag"]))
            )["tag"]

        groups.append({
            "canonical_tag":  canonical,
            "score":          1.0,
            "reason":         grp.get("reason", ""),
            "tags":           members,
            "total_count":    sum(t.get("count") or 0 for t in members),
        })

    return sorted(groups, key=lambda g: -g["total_count"])[:limit]


def _parse_json(text: str) -> dict:
    clean = re.sub(r"```(?:json)?\s*", "", text).strip()
    clean = re.sub(r"```\s*$", "", clean).strip()
    clean = re.sub(r",\s*([}\]])", r"\1", clean)
    try:
        return json.loads(clean)
    except Exception:
        m = re.search(r"(\{.*\})", clean, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
    return {}
