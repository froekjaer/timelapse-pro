"""Versioned, allowlisted AI prompt templates stored in PostgreSQL."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy import text


TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}")


@dataclass(frozen=True)
class PromptDefinition:
    label: str
    variables: tuple[str, ...]
    template: str


DEFAULT_PROMPTS: dict[str, PromptDefinition] = {
    "vision_single": PromptDefinition(
        "Billedanalyse",
        ("context", "vocabulary"),
        """Analyze this outdoor time-lapse image. Respond only with valid JSON. No markdown.
{{context}}
Describe only what is actually visible. Do not assume this is a construction site.
Before answering, systematically inspect: (1) camera/lens quality, (2) weather and light,
(3) buildings, roofs, facades and structures, (4) vegetation, roads, terrain and surroundings,
(5) vehicles, machinery, materials, workers and unusual events.

Rules:
- Never tag absence and never copy the vocabulary as a checklist.
- Construction stages, interior work and machinery require direct visual evidence.
- Use 12-25 concrete searchable tags when justified; use fewer for a simple scene.
- Include visible weather and lighting such as overcast, sunlight, backlight, sun_in_lens,
  glare, lens_flare, blown_highlights, shadows, diffuse_light and time of day.
- quality.flag is the single strongest of clear_image, overexposed, underexposed,
  blown_highlights, glare, sun_in_lens, lens_flare, low_contrast, dirty_lens,
  condensation_on_lens, motion_blur, incorrect_focus, night_image_too_dark,
  obstruction_in_front_of_camera or camera_moved. Only use unusable_image for a blank,
  fully blocked or sensor-error frame with no discernible real content.
- Tags must be English lowercase underscore-separated. Unknown English tags go in new_tags,
  with a Danish translation at the same index in new_tags_da.
- Scene text is Danish and mentions anything unusual. Never identify people or read plates.

Approved vocabulary (inspiration, not a checklist):
{{vocabulary}}

Return exactly this JSON shape:
{"scene":"Billedet viser ...","tags":[],"new_tags":[],"new_tags_da":[],
"quality":{"flag":"clear_image","ok":true},
"gdpr":{"has_data":false,"detections":[]}}""",
    ),
    "vision_change": PromptDefinition(
        "Ændringsanalyse",
        ("vocabulary",),
        """Compare IMAGE 1 (reference) with IMAGE 2 (current). Return only valid JSON.
Describe only visible changes; do not infer construction progress from weather, viewpoint or
lighting differences. Tags are English lowercase underscore-separated; scene and change
summary are Danish. Unknown tags require parallel Danish translations in new_tags_da.
Never identify people or read license plates.

Approved vocabulary:
{{vocabulary}}

Return exactly:
{"scene":"...","tags":[],"new_tags":[],"new_tags_da":[],
"change":{"detected":true,"summary":"...","magnitude":"ingen|lille|moderat|stor",
"new_items":[],"removed_items":[]},"quality":{"flag":"clear_image","ok":true},
"gdpr":{"has_data":false,"detections":[]}}""",
    ),
    "aiops_assessment": PromptDefinition(
        "AI Ops vurdering",
        ("snapshot",),
        """Du er TimeLapse Pro AI Ops co-pilot. Analyser kun read-only data. Bed aldrig om
hemmeligheder og markér alle ændringsforslag som krævende menneskelig accept. Vurder CMDB,
SIEM, updates, key management, resilience og SAST med SABSA, IEC 62443, ISO 27000, NIS2 og CRA.
Returner kun JSON med mode, summary, risk_level, recommendations og next_checks.
SNAPSHOT:\n{{snapshot}}""",
    ),
    "aiops_query": PromptDefinition(
        "AI Ops spørgsmål",
        ("area", "question", "snapshot"),
        """Du er TimeLapse Pro GRC/AI Ops co-pilot. Svar praktisk på dansk og kun ud fra
read-only evidens. Returner kun JSON med mode, answer, risk_level, recommendations, evidence
og suggested_filters. Område: {{area}}\nSpørgsmål: {{question}}\nSNAPSHOT:\n{{snapshot}}""",
    ),
}


def render_template(template: str, allowed_variables: list[str] | tuple[str, ...], values: dict[str, object]) -> str:
    allowed = set(allowed_variables)
    referenced = set(TOKEN_RE.findall(template))
    unknown = referenced - allowed
    missing = referenced - values.keys()
    if unknown:
        raise ValueError(f"Ikke-tilladte promptvariable: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"Manglende promptvariable: {', '.join(sorted(missing))}")
    return TOKEN_RE.sub(lambda match: str(values[match.group(1)]), template)


def get_prompt(db, purpose: str) -> dict:
    definition = DEFAULT_PROMPTS.get(purpose)
    if not definition:
        raise KeyError(f"Ukendt promptformål: {purpose}")
    try:
        row = db.execute(text("""
            SELECT id, purpose, version, status, template, allowed_variables, notes,
                   created_by, created_at, activated_by, activated_at
            FROM ai_prompt_templates WHERE purpose = :purpose AND status = 'active'
            ORDER BY version DESC LIMIT 1
        """), {"purpose": purpose}).mappings().first()
    except Exception:
        db.rollback()
        row = None
    if row:
        result = dict(row)
        result["allowed_variables"] = list(result["allowed_variables"] or [])
        result["source"] = "database"
        result["label"] = definition.label
        return result
    return {
        "id": None, "purpose": purpose, "version": 0, "status": "fallback",
        "template": definition.template, "allowed_variables": list(definition.variables),
        "notes": "Indbygget, kontrolleret fallback", "source": "default", "label": definition.label,
    }


def render_prompt(db, purpose: str, **values: object) -> str:
    prompt = get_prompt(db, purpose)
    return render_template(prompt["template"], prompt["allowed_variables"], values)


def ensure_prompt_defaults(db) -> None:
    """Seed governed version 1 prompts once; never overwrite admin versions."""
    for purpose, definition in DEFAULT_PROMPTS.items():
        exists = db.execute(text(
            "SELECT 1 FROM ai_prompt_templates WHERE purpose = :purpose LIMIT 1"
        ), {"purpose": purpose}).first()
        if exists:
            continue
        db.execute(text("""
            INSERT INTO ai_prompt_templates
                (purpose, version, status, template, allowed_variables, notes,
                 created_by, activated_by, activated_at)
            VALUES (:purpose, 1, 'active', :template, CAST(:variables AS JSONB),
                    'Initial kontrolleret standardprompt', 'system', 'system', NOW())
            ON CONFLICT (purpose, version) DO NOTHING
        """), {"purpose": purpose, "template": definition.template,
                 "variables": json.dumps(definition.variables)})
    db.commit()


def list_prompts(db) -> list[dict]:
    ensure_prompt_defaults(db)
    result = []
    for purpose in DEFAULT_PROMPTS:
        active = get_prompt(db, purpose)
        rows = db.execute(text("""
            SELECT id, version, status, notes, created_by, created_at, activated_by, activated_at
            FROM ai_prompt_templates WHERE purpose = :purpose ORDER BY version DESC
        """), {"purpose": purpose}).mappings().all()
        active["history"] = [dict(row) for row in rows]
        result.append(active)
    return result


def create_draft(db, purpose: str, template: str, notes: str | None, username: str) -> dict:
    definition = DEFAULT_PROMPTS.get(purpose)
    if not definition:
        raise KeyError(purpose)
    render_template(template, definition.variables, {name: f"<{name}>" for name in definition.variables})
    row = db.execute(text("""
        INSERT INTO ai_prompt_templates
            (purpose, version, status, template, allowed_variables, notes, created_by)
        VALUES (:purpose,
            COALESCE((SELECT MAX(version) + 1 FROM ai_prompt_templates WHERE purpose = :purpose), 1),
            'draft', :template, CAST(:variables AS JSONB), :notes, :username)
        RETURNING id, version, status
    """), {"purpose": purpose, "template": template,
             "variables": json.dumps(definition.variables), "notes": notes, "username": username}).mappings().one()
    db.commit()
    return dict(row)


def activate_prompt(db, prompt_id: int, username: str) -> dict:
    target = db.execute(text("SELECT purpose, status FROM ai_prompt_templates WHERE id = :id"), {"id": prompt_id}).mappings().first()
    if not target:
        raise KeyError(prompt_id)
    if target["status"] not in {"draft", "active"}:
        raise ValueError("Kun en kladde kan aktiveres")
    db.execute(text("UPDATE ai_prompt_templates SET status = 'retired' WHERE purpose = :purpose AND status = 'active' AND id <> :id"), {"purpose": target["purpose"], "id": prompt_id})
    db.execute(text("UPDATE ai_prompt_templates SET status = 'active', activated_by = :username, activated_at = NOW() WHERE id = :id"), {"username": username, "id": prompt_id})
    db.commit()
    return {"id": prompt_id, "purpose": target["purpose"], "status": "active"}
