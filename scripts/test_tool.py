#!/usr/bin/env python3
"""
scripts/test_tool.py — Test rapide d'un outil en ligne de commande

Usage :
    python scripts/test_tool.py --module <module> --outil <nom> --args '<json>'
    python scripts/test_tool.py --module <module> --outil <nom> --args '<json>' --setup "<outil> <arg1=val1> ..."

Exemples :
    python scripts/test_tool.py --module data_tools --outil datetime_now --args '{}'

    python scripts/test_tool.py \\
        --module data_file_tools \\
        --setup "df_read chemin=/tmp/employes.csv nom=rh" \\
        --outil df_info \\
        --args '{"nom": "rh"}'

    python scripts/test_tool.py \\
        --module web_tools \\
        --outil web_search \\
        --args '{"query": "open data emploi", "max_results": 2}'
"""

import argparse
import json
import sys
import time
import importlib
from pathlib import Path

# ── Détection automatique du répertoire Prométhée ────────────────────────────

def _find_promethee_root() -> Path:
    """Cherche le répertoire racine de Prométhée (contenant core/tools_engine.py)."""
    candidates = [
        Path.cwd(),
        Path.cwd().parent,
        Path(__file__).parent.parent,
        Path.home() / "promethee",
    ]
    for candidate in candidates:
        if (candidate / "core" / "tools_engine.py").exists():
            return candidate
    return None


def _setup_path():
    root = _find_promethee_root()
    if root:
        sys.path.insert(0, str(root))
        return root
    # Essai avec stub minimal
    stub_dir = Path(__file__).parent.parent
    if not (stub_dir / "core").exists():
        (stub_dir / "core").mkdir(exist_ok=True)
        stub_file = stub_dir / "core" / "tools_engine.py"
        if not stub_file.exists():
            stub_file.write_text(
                '# Stub minimal pour tests standalone\n'
                '_TOOLS = {}\n'
                '_TOOL_ICONS = {}\n'
                '_CURRENT_FAMILY = {}\n\n'
                'def set_current_family(module, label, emoji):\n'
                '    _CURRENT_FAMILY["module"] = module\n\n'
                'def tool(name, description, parameters):\n'
                '    def decorator(func):\n'
                '        _TOOLS[name] = {"func": func, "description": description}\n'
                '        return func\n'
                '    return decorator\n'
            )
    sys.path.insert(0, str(stub_dir))
    return stub_dir


# ── Parser des arguments de setup ─────────────────────────────────────────────

def _parse_setup_args(setup_str: str) -> tuple[str, dict]:
    """Parse 'outil_name cle1=val1 cle2=val2' → (nom, {cle: val})"""
    parts = setup_str.strip().split()
    if not parts:
        raise ValueError("--setup vide")
    tool_name = parts[0]
    kwargs = {}
    for part in parts[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            # Conversion automatique des types simples
            if v.isdigit():
                v = int(v)
            elif v.replace(".", "", 1).isdigit():
                v = float(v)
            elif v.lower() == "true":
                v = True
            elif v.lower() == "false":
                v = False
            kwargs[k] = v
        else:
            raise ValueError(f"Argument de setup invalide : '{part}' (format attendu: cle=valeur)")
    return tool_name, kwargs


# ── Affichage du résultat ─────────────────────────────────────────────────────

def _print_result(result: dict, duree_ms: float):
    status = result.get("status", "?")
    symbol = "✅" if status == "success" else "❌"

    print(f"\n{symbol} Status : {status}  ({duree_ms:.1f} ms)")
    print("─" * 60)

    if status == "error":
        print(f"Erreur : {result.get('error', '(pas de message)')}")
        return

    # Afficher les champs clés
    skip = {"status", "lignes", "resultats", "records"}
    for k, v in result.items():
        if k in skip:
            continue
        if isinstance(v, (list, dict)) and len(str(v)) > 120:
            print(f"  {k:25} : [{len(v)} éléments]" if isinstance(v, list) else f"  {k:25} : {{...}}")
        else:
            print(f"  {k:25} : {v}")

    # Afficher les données si présentes
    data_key = next((k for k in ("lignes", "resultats", "records") if k in result), None)
    if data_key and result[data_key]:
        lignes = result[data_key]
        print(f"\n  [{data_key}] — {len(lignes)} ligne(s) :")
        # En-têtes
        if lignes:
            cols = list(lignes[0].keys())
            col_widths = {c: max(len(str(c)), max(len(str(r.get(c, ""))) for r in lignes[:5])) for c in cols}
            col_widths = {c: min(w, 20) for c, w in col_widths.items()}
            header = "  " + " | ".join(str(c)[:col_widths[c]].ljust(col_widths[c]) for c in cols)
            print(header)
            print("  " + "-" * (len(header) - 2))
            for row in lignes[:10]:
                print("  " + " | ".join(str(row.get(c, ""))[:col_widths[c]].ljust(col_widths[c]) for c in cols))
            if len(lignes) > 10:
                print(f"  ... ({len(lignes) - 10} lignes supplémentaires)")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Test rapide d'un outil Prométhée")
    parser.add_argument("--module", required=True, help="Nom du module (ex: data_file_tools)")
    parser.add_argument("--outil",  required=True, help="Nom de l'outil (ex: df_info)")
    parser.add_argument("--args",   default="{}", help="Arguments JSON (ex: '{\"nom\": \"rh\"}')")
    parser.add_argument("--setup",  default=None, help="Outil de setup à exécuter avant (ex: 'df_read chemin=/tmp/x.csv nom=rh')")
    parser.add_argument("--json",   action="store_true", help="Sortie JSON brute")
    args = parser.parse_args()

    # Setup du path
    root = _setup_path()
    print(f"📁 Racine Prométhée : {root}")

    # Import du module
    try:
        module = importlib.import_module(f"tools.{args.module}")
    except ImportError as e:
        print(f"❌ Impossible d'importer 'tools.{args.module}' : {e}")
        sys.exit(1)

    print(f"✅ Module 'tools.{args.module}' chargé")

    # Récupérer l'outil via le registre
    try:
        from core.tools_engine import _TOOLS
    except ImportError:
        print("❌ Impossible d'importer core.tools_engine")
        sys.exit(1)

    # Étape de setup (optionnelle)
    if args.setup:
        setup_tool_name, setup_kwargs = _parse_setup_args(args.setup)
        if setup_tool_name not in _TOOLS:
            print(f"❌ Outil de setup '{setup_tool_name}' introuvable")
            sys.exit(1)
        print(f"\n⚙️  Setup : {setup_tool_name}({setup_kwargs})")
        setup_result = _TOOLS[setup_tool_name]["func"](**setup_kwargs)
        if setup_result.get("status") != "success":
            print(f"❌ Setup échoué : {setup_result.get('error')}")
            sys.exit(1)
        print(f"✅ Setup OK : {setup_result.get('message', '')}")

    # Appel de l'outil principal
    if args.outil not in _TOOLS:
        available = [n for n in _TOOLS if args.module.replace("_tools", "") in n or True]
        print(f"❌ Outil '{args.outil}' introuvable.")
        print(f"   Outils disponibles dans ce module :")
        module_prefix = args.module.replace("_tools", "")
        for name in sorted(_TOOLS.keys()):
            print(f"   - {name}")
        sys.exit(1)

    try:
        kwargs = json.loads(args.args)
    except json.JSONDecodeError as e:
        print(f"❌ --args JSON invalide : {e}")
        sys.exit(1)

    print(f"\n🔧 Appel : {args.outil}({kwargs})")

    t0 = time.perf_counter()
    try:
        result = _TOOLS[args.outil]["func"](**kwargs)
    except Exception as e:
        print(f"❌ Exception non catchée : {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    duree_ms = (time.perf_counter() - t0) * 1000

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        _print_result(result, duree_ms)


if __name__ == "__main__":
    main()
