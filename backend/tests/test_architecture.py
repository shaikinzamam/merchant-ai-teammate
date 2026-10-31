"""Enforces module boundaries: only the composition root may import concrete integrations."""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def imports_of(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
        elif isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
    return out


def test_only_container_imports_integrations():
    offenders = []
    for f in APP.rglob("*.py"):
        rel = f.relative_to(APP).as_posix()
        if rel.startswith("integrations/") or rel == "container.py":
            continue
        if any(m.startswith("app.integrations") for m in imports_of(f)):
            offenders.append(rel)
    assert offenders == []


def test_orchestrator_and_planner_never_touch_tool_handlers():
    for pkg in ("modules/orchestrator", "modules/planner", "modules/growth"):
        for f in (APP / pkg).rglob("*.py"):
            bad = {m for m in imports_of(f) if m in {"app.modules.tools.base"}}
            assert not bad, f"{f} imports tool internals: {bad}"


def test_mock_and_real_integrations_are_separate_packages():
    assert (APP / "integrations/mock_paytm").is_dir() and (APP / "integrations/paytm_real").is_dir()
