"""Regression guard for the main.py modularization plan (2026-08-26/27):
when a name is extracted out of main.py into auth.py/tenant_scope.py/
dict_merge.py, every call site in main.py must actually import it — a
`from X import Y` at module scope creates a name binding, it does not
retroactively make main.py aware of names that are merely DEFINED in a
module main.py imports from *some* names of.

2026-08-27 incident (live production, caught by Peter, not by CI):
_resolve_session_policy moved to auth.py in the Phase 0 extraction, but
main.py calls it directly at 3 call sites (/api/auth/login,
/api/auth/session-policy, /api/auth/me) without ever importing it. This
is a NameError at runtime, not at import time — it only fires when that
specific code path actually executes, so `import main` succeeding and
even the full test suite passing does not catch it (no test happened to
call these three routes with a real session end-to-end). /api/auth/me is
what the frontend polls on every page load to validate the session
cookie — the 500 it returned was silently interpreted by the frontend as
"not authenticated", logging Peter out on every refresh.

This test performs the same AST sweep that found the bug: for each of
auth.py, tenant_scope.py, dict_merge.py, collect every top-level name
defined there, then check that every such name *used* (loaded) anywhere
in main.py is also present in main.py's `from <module> import (...)`
block. A name legitimately shadowed by main.py's own definition (e.g.
`log`) is excluded automatically, since we only flag names NOT already
bound some other way — checked by ensuring the name doesn't appear as a
top-level assignment/def in main.py itself either.
"""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADEND = ROOT / "headend"

# Every module in this set is a Phase 0/1/2 extraction target of the main.py
# modularization plan: main.py imports names FROM these, and must import
# every name it actually uses, not just some of them.
EXTRACTED_MODULES = ["auth", "tenant_scope", "dict_merge"]


def _top_level_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_main_imports_every_name_it_uses_from_each_extracted_module():
    main_path = HEADEND / "main.py"
    main_tree = ast.parse(main_path.read_text(encoding="utf-8"))

    # Names main.py defines itself (functions/classes/assignments at any
    # scope) — a name defined locally legitimately shadows an
    # identically-named export from an extracted module (e.g. `log`).
    locally_defined = set()
    for node in ast.walk(main_tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            locally_defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    locally_defined.add(t.id)

    used_names = {
        node.id
        for node in ast.walk(main_tree)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }

    problems = []
    for module_name in EXTRACTED_MODULES:
        module_path = HEADEND / f"{module_name}.py"
        defined_in_module = _top_level_names(module_path)

        imported = set()
        for node in ast.walk(main_tree):
            if isinstance(node, ast.ImportFrom) and node.module == module_name:
                for alias in node.names:
                    imported.add(alias.asname or alias.name)

        missing = (defined_in_module & used_names) - imported - locally_defined
        for name in sorted(missing):
            problems.append(f"{name!r} is defined in {module_name}.py, used in main.py, "
                             f"but not imported (and not locally defined/shadowed)")

    assert not problems, (
        "main.py references names from an extracted module without importing them — "
        "this is a NameError waiting to happen at runtime, on whatever code path first "
        "reaches the missing name:\n  " + "\n  ".join(problems)
    )
