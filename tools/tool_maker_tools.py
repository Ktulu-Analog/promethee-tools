# ============================================================================
# Prométhée — Assistant IA desktop
# ============================================================================
# Auteur  : Pierre COUGET
# Licence : GNU Affero General Public License v3.0 (AGPL-3.0)
# ============================================================================

"""
tools/tool_maker_tools.py — Auto-développement d'outils
=======================================================

Outils exposés (1):
  - create_skill : Création/Mise à jour d'outils dynamiques

Prérequis :
    Dépendance interne : core.dynamic_tools (mode agentique de Prométhée)
"""

from core.tools_engine import tool, set_current_family
from core.dynamic_tools import get_dynamic_tools_manager

set_current_family("tool_maker", "Génie Logiciel", "🛠️")


@tool(
    name="create_skill",
    description=(
        "Crée, met à jour ou CORRIGE un outil Python dynamiquement. "
        "MÉCANISME D'AUTO-RÉPARATION : Si un outil que tu as créé renvoie une erreur lors de son exécution, "
        "tu DOIS utiliser `create_skill` pour le réécrire et le corriger. "
        "NE PROPOSE JAMAIS un correctif dans un bloc de code texte (Markdown), utilise toujours cet outil. "
        "Ne JAMAIS utiliser write_file pour un outil. "
        "Règles : Le nom de la fonction principale DOIT être identique à `tool_name`. "
        "Inclus des type hints et une docstring Google. "
        "Le code doit être robuste : intercepte tes propres exceptions (try/except) pour retourner un dict "
        "contenant {'error': '...'} au lieu de crasher."
    ),
    parameters={
        "type": "object",
        "properties": {
            "tool_name": {
                "type": "string",
                "description": "Nom unique de l'outil (minuscules, underscores).",
            },
            "python_code": {
                "type": "string",
                "description": "Code source Python complet et corrigé de l'outil.",
            },
        },
        "required": ["tool_name", "python_code"],
    },
)
def create_skill(tool_name: str, python_code: str) -> dict:
    """
    Portail vers le DynamicToolsManager pour l'auto-développement d'outils.
    """
    try:
        manager = get_dynamic_tools_manager()
        result = manager.create_skill(tool_name, python_code)

        # Interpréter le résultat
        if result.startswith("✓"):
            return {"status": "success", "tool_name": tool_name, "message": result}
        else:
            return {"status": "error", "tool_name": tool_name, "error": result}

    except Exception as e:
        return {
            "status": "error",
            "tool_name": tool_name,
            "error": f"Erreur lors de la création du skill : {str(e)}",
        }
