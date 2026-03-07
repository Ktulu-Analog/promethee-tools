"""
Configuration pytest partagée.
Gère l'injection du chemin Prométhée ou la génération du stub minimal.
"""
import sys
import os
from pathlib import Path

# ── Résolution du chemin Prométhée ──────────────────────────────────────────
_CANDIDATES = [
    Path(__file__).parent.parent.parent / "promethee",
    Path.home() / "promethee",
    Path.cwd(),
    Path.cwd().parent,
]

_ROOT = next((c for c in _CANDIDATES if (c / "core" / "tools_engine.py").exists()), None)

if _ROOT:
    sys.path.insert(0, str(_ROOT))
else:
    # Stub minimal pour CI / tests standalone
    _STUB_DIR = Path(__file__).parent.parent
    (_STUB_DIR / "core").mkdir(exist_ok=True)
    _STUB = _STUB_DIR / "core" / "tools_engine.py"
    if not _STUB.exists():
        _STUB.write_text(
            "_TOOLS = {}\n_TOOL_ICONS = {}\n_CURRENT_FAMILY = {}\n\n"
            "def set_current_family(m, l, e):\n    _CURRENT_FAMILY['module'] = m\n\n"
            "def tool(name, description, parameters):\n"
            "    def decorator(func):\n"
            "        _TOOLS[name] = {'fn': func, 'schema': {}, 'parameters': parameters}\n"
            "        return func\n"
            "    return decorator\n"
        )
    sys.path.insert(0, str(_STUB_DIR))

os.environ.setdefault("MAX_CONTEXT_TOKENS", "128000")
