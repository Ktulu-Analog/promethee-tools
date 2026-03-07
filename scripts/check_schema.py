#!/usr/bin/env python3
"""
scripts/check_schema.py — Vérifie la cohérence JSON Schema ↔ signature Python

Détecte :
- Paramètres dans JSON Schema absents de la signature Python (et vice-versa)
- Paramètres marqués required mais avec valeur par défaut (incohérence)
- Paramètres required avec Optional dans la signature
- Noms d'outils en doublon entre modules

Usage :
    python scripts/check_schema.py                    # vérifie tous les modules
    python scripts/check_schema.py --module data_file_tools
    python scripts/check_schema.py --doublons         # vérifie uniquement les doublons
"""

import argparse
import ast
import sys
import importlib
from pathlib import Path


def _find_promethee_root() -> Path:
    candidates = [Path.cwd(), Path.cwd().parent, Path(__file__).parent.parent]
    for c in candidates:
        if (c / "core" / "tools_engine.py").exists():
            return c
    return None


def _setup_path():
    root = _find_promethee_root()
    if root:
        sys.path.insert(0, str(root))
        return root
    # Stub
    stub_dir = Path(__file__).parent.parent
    if not (stub_dir / "core").exists():
        (stub_dir / "core").mkdir(exist_ok=True)
    stub_file = stub_dir / "core" / "tools_engine.py"
    if not stub_file.exists():
        stub_file.write_text(
            '_TOOLS = {}\n_TOOL_ICONS = {}\n_CURRENT_FAMILY = {}\n\n'
            'def set_current_family(m, l, e): pass\n\n'
            'def tool(name, description, parameters):\n'
            '    def decorator(func):\n'
            '        _TOOLS[name] = {"func": func, "parameters": parameters}\n'
            '        return func\n'
            '    return decorator\n'
        )
    sys.path.insert(0, str(stub_dir))
    return stub_dir


def _get_function_params(func) -> dict[str, bool]:
    """Retourne {param_name: has_default} pour une fonction."""
    import inspect
    sig = inspect.signature(func)
    result = {}
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        has_default = param.default is not inspect.Parameter.empty
        result[name] = has_default
    return result


def _get_optional_params(func) -> set[str]:
    """Retourne les noms de paramètres typés Optional[...]."""
    import inspect
    hints = {}
    try:
        hints = func.__annotations__
    except Exception:
        pass
    optional = set()
    for name, hint in hints.items():
        if name == "return":
            continue
        hint_str = str(hint)
        if "Optional" in hint_str or "NoneType" in hint_str:
            optional.add(name)
    return optional


def check_module(module_name: str, tools_registry: dict) -> list[str]:
    """Vérifie un module et retourne la liste des problèmes."""
    problems = []

    module_tools = {
        name: info for name, info in tools_registry.items()
        if True  # on checke tout
    }

    # Filtrer par module si demandé
    try:
        mod = importlib.import_module(f"tools.{module_name}")
    except ImportError as e:
        return [f"❌ Impossible d'importer tools.{module_name} : {e}"]

    # Récupérer les outils de ce module spécifique
    # (tous ceux enregistrés depuis ce fichier)
    tools_file = Path(f"tools/{module_name}.py")

    for name, info in tools_registry.items():
        func = info.get("func")
        if func is None:
            continue

        # Vérifier que la fonction vient de ce module
        func_module = getattr(func, "__module__", "")
        if module_name not in func_module and f"tools.{module_name}" not in func_module:
            # Essai par nom de fichier
            func_file = getattr(sys.modules.get(func_module, None), "__file__", "") or ""
            if module_name not in func_file:
                continue

        schema_params = set(info.get("parameters", {}).get("properties", {}).keys())
        required_params = set(info.get("parameters", {}).get("required", []))
        python_params = _get_function_params(func)
        optional_hints = _get_optional_params(func)

        # 1. Dans schema mais pas dans signature
        in_schema_not_python = schema_params - set(python_params.keys())
        for p in sorted(in_schema_not_python):
            problems.append(f"  ⚠️  {name}.{p} : dans JSON Schema mais absent de la signature Python")

        # 2. Dans signature mais pas dans schema (sauf 'self')
        in_python_not_schema = set(python_params.keys()) - schema_params
        for p in sorted(in_python_not_schema):
            problems.append(f"  ⚠️  {name}.{p} : dans signature Python mais absent du JSON Schema")

        # 3. Required mais avec valeur par défaut
        for p in sorted(required_params):
            if p in python_params and python_params[p]:  # has_default = True
                problems.append(f"  ⚠️  {name}.{p} : marqué 'required' dans le Schema mais a une valeur par défaut Python")

        # 4. Required mais Optional dans la signature
        for p in sorted(required_params):
            if p in optional_hints:
                problems.append(f"  ⚠️  {name}.{p} : marqué 'required' mais typé Optional dans la signature")

        # 5. Paramètre non-required sans valeur par défaut
        for p in sorted(schema_params - required_params):
            if p in python_params and not python_params[p]:  # has_default = False
                problems.append(f"  ⚠️  {name}.{p} : optionnel dans le Schema mais sans valeur par défaut Python")

    return problems


def check_duplicates(tools_registry: dict) -> list[str]:
    """Vérifie les noms en doublon (ne devrait pas arriver mais au cas où)."""
    # Les doublons sont impossibles dans un dict, mais on peut vérifier
    # si des fonctions Python ont le même nom dans des modules différents
    func_names: dict[str, list[str]] = {}
    for tool_name, info in tools_registry.items():
        func = info.get("func")
        if func:
            fname = func.__name__
            if fname not in func_names:
                func_names[fname] = []
            func_names[fname].append(tool_name)

    problems = []
    for fname, tool_names in func_names.items():
        if len(tool_names) > 1:
            problems.append(f"  ⚠️  Fonction Python '{fname}' utilisée par plusieurs outils : {tool_names}")

    return problems


def main():
    parser = argparse.ArgumentParser(description="Vérifie la cohérence JSON Schema ↔ signature des outils")
    parser.add_argument("--module",   default=None, help="Module à vérifier (ex: data_file_tools)")
    parser.add_argument("--doublons", action="store_true", help="Vérifier uniquement les doublons")
    args = parser.parse_args()

    root = _setup_path()
    print(f"📁 Racine : {root}")

    # Charger tous les modules
    tools_dir = root / "tools" if root else Path("tools")
    modules_to_check = []

    if args.module:
        modules_to_check = [args.module]
    else:
        modules_to_check = [
            f.stem for f in tools_dir.glob("*_tools.py")
            if not f.stem.startswith("__")
        ]

    from core.tools_engine import _TOOLS
    _TOOLS.clear()

    loaded = []
    for mod_name in sorted(modules_to_check):
        try:
            importlib.import_module(f"tools.{mod_name}")
            loaded.append(mod_name)
        except Exception as e:
            print(f"⚠️  Impossible de charger tools.{mod_name} : {e}")

    print(f"✅ {len(loaded)} modules chargés, {len(_TOOLS)} outils au total\n")

    all_problems = []

    if args.doublons:
        problems = check_duplicates(_TOOLS)
        if problems:
            print("── Doublons ──")
            for p in problems:
                print(p)
        else:
            print("✅ Aucun doublon détecté")
        return

    for mod_name in loaded:
        problems = check_module(mod_name, _TOOLS)
        if problems:
            print(f"── {mod_name} ({'⚠️ ' + str(len(problems)) + ' problème(s)'}) ──")
            for p in problems:
                print(p)
            all_problems.extend(problems)
        else:
            print(f"  ✅ {mod_name} — OK")

    print()
    if all_problems:
        print(f"{'─' * 50}")
        print(f"⚠️  {len(all_problems)} problème(s) détecté(s) au total")
        sys.exit(1)
    else:
        print("✅ Tous les modules sont cohérents.")


if __name__ == "__main__":
    main()
