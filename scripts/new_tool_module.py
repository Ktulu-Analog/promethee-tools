#!/usr/bin/env python3
"""
scripts/new_tool_module.py — Génère un squelette de module d'outils

Usage :
    python scripts/new_tool_module.py --nom mon_module --famille "Ma famille" --emoji 🔧

Génère : tools/mon_module_tools.py
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime
from string import Template

# ── Template ──────────────────────────────────────────────────────────────────
# Utilise string.Template ($var) plutôt que str.format() pour éviter tout
# conflit avec les accolades Python présentes dans le code généré.

TEMPLATE = Template(r'''# ============================================================================
# Prométhée — Assistant IA desktop
# ============================================================================
# Auteur  : $auteur
# Licence : GNU Affero General Public License v3.0 (AGPL-3.0)
#           https://www.gnu.org/licenses/agpl-3.0.html
# Année   : $annee
# ----------------------------------------------------------------------------
# Ce fichier fait partie du projet Prométhée.
# Vous pouvez le redistribuer et/ou le modifier selon les termes de la
# licence AGPL-3.0 publiée par la Free Software Foundation.
# ============================================================================

"""
tools/${nom}_tools.py — $famille
$separateur

Outils exposés (1) :

  - ${nom}_exemple   : exemple — décrire ce que fait cet outil

Prérequis :
    # pip install ma-dependance
"""

from typing import Optional
from core.tools_engine import tool, set_current_family, _TOOL_ICONS

set_current_family("${nom}_tools", "$famille", "$emoji")

# ── Icônes ────────────────────────────────────────────────────────────────────
_TOOL_ICONS.update({
    "${nom}_exemple": "$emoji",
})

# ── Constantes ────────────────────────────────────────────────────────────────
# _MA_CONSTANTE = "valeur"

# ── État de session (si nécessaire) ─────────────────────────────────────────
# _ETAT: dict = {}

# ── Helpers privés ──────────────────────────────────────────────────────────
# def _mon_helper(x):
#     ...


# ══════════════════════════════════════════════════════════════════════════════
# OUTILS
# ══════════════════════════════════════════════════════════════════════════════

@tool(
    name="${nom}_exemple",
    description=(
        "Description de ce que fait l'outil. "
        "Quand l'utiliser. "
        "Paramètres importants. "
        "Exemples : 'valeur_exemple', 'autre_exemple'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "param_requis": {
                "type": "string",
                "description": "Description du paramètre requis.",
            },
            "param_optionnel": {
                "type": "integer",
                "description": "Description du paramètre optionnel (défaut: 10).",
            },
        },
        "required": ["param_requis"],
    },
)
def ${nom}_exemple(
    param_requis: str,
    param_optionnel: int = 10,
) -> dict:
    # Valider les entrées
    if not param_requis.strip():
        return {"status": "error", "error": "param_requis ne peut pas être vide."}

    try:
        # TODO : implémenter la logique
        resultat = f"Traitement de {param_requis!r} avec limite={param_optionnel}"

        return {
            "status":   "success",
            "resultat": resultat,
            "message":  f"{param_requis!r} traité avec succès.",
        }

    except Exception as e:
        return {"status": "error", "error": f"Erreur ${nom}_exemple : {e}"}
''')


def main():
    parser = argparse.ArgumentParser(description="Génère un squelette de module d'outils Prométhée")
    parser.add_argument("--nom",     required=True, help="Nom du module (ex: mon_module → tools/mon_module_tools.py)")
    parser.add_argument("--famille", nargs="+",     help="Nom de la famille affiché dans l'UI (ex: 'Ma famille')")
    parser.add_argument("--emoji",   default="🔧",   help="Icône emoji (défaut: 🔧)")
    parser.add_argument("--auteur",  default="Pierre COUGET", help="Auteur")
    parser.add_argument("--output",  default=None,   help="Répertoire de sortie (défaut: tools/)")
    args = parser.parse_args()

    # Nettoyer le nom
    nom = args.nom.lower().replace("-", "_").replace(" ", "_")
    if nom.endswith("_tools"):
        nom = nom[:-6]

    # Famille : accepte --famille Office 365 (plusieurs mots sans guillemets)
    famille = " ".join(args.famille) if args.famille else nom.replace("_", " ").title()

    # Répertoire de sortie
    if args.output:
        output_dir = Path(args.output)
    else:
        candidates = [Path.cwd() / "tools", Path(__file__).parent.parent / "tools"]
        output_dir = next((c for c in candidates if c.exists()), Path.cwd() / "tools")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{nom}_tools.py"

    if output_file.exists():
        print(f"⚠️  Le fichier {output_file} existe déjà.")
        answer = input("Écraser ? (o/N) ").strip().lower()
        if answer != "o":
            print("Annulé.")
            sys.exit(0)

    # Ligne de séparation proportionnelle au titre du docstring
    titre = f"tools/{nom}_tools.py — {famille}"
    separateur = "=" * len(titre)

    contenu = TEMPLATE.substitute(
        nom=nom,
        famille=famille,
        emoji=args.emoji,
        auteur=args.auteur,
        annee=datetime.now().year,
        separateur=separateur,
    )

    output_file.write_text(contenu, encoding="utf-8")

    print(f"✅ Fichier généré : {output_file}")
    print()
    print("Prochaines étapes :")
    print(f"  1. Éditer {output_file}")
    print(f"  2. Renommer {nom}_exemple et implémenter la logique")
    print(f"  3. Ajouter dans tools/__init__.py → register_all() :")
    print(f"       from tools import {nom}_tools")
    print(f"  4. Tester avec :")
    print(f'       python scripts/test_tool.py --module {nom}_tools --outil {nom}_exemple --args \'{{"param_requis": "test"}}\'')


if __name__ == "__main__":
    main()
