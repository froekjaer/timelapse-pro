import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "headend"))

from ai.prompt_registry import DEFAULT_PROMPTS, render_template


def test_all_default_prompts_render_with_declared_variables():
    for definition in DEFAULT_PROMPTS.values():
        values = {name: f"value-for-{name}" for name in definition.variables}
        rendered = render_template(definition.template, definition.variables, values)
        assert "{{" not in rendered


def test_prompt_rejects_undeclared_variable():
    with pytest.raises(ValueError, match="Ikke-tilladte"):
        render_template("Hello {{secret}}", ("question",), {"secret": "x"})


def test_prompt_rejects_missing_value():
    with pytest.raises(ValueError, match="Manglende"):
        render_template("Hello {{question}}", ("question",), {})


def test_values_are_data_not_second_pass_templates():
    rendered = render_template("Question: {{question}}", ("question",), {"question": "{{secret}}"})
    assert rendered == "Question: {{secret}}"
