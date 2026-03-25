# ============================================================================
# Prométhée — Assistant IA desktop
# ============================================================================
# Auteur  : Pierre COUGET
# Licence : GNU Affero General Public License v3.0 (AGPL-3.0)
# ============================================================================

"""
tools/lms_tools.py — Export LMS (Moodle)
=========================================

Outils exposés (1):
  - export_moodle_xml : Export QCM Moodle XML

Prérequis :
    Aucun (utilise uniquement la bibliothèque standard)
"""

from pathlib import Path

from core.tools_engine import tool, set_current_family

set_current_family("lms_tools", "Export LMS (Moodle)", "🎓")


def _resolve_output(output_path: str, default_name: str) -> Path:
    """
    Résout le chemin de sortie en utilisant Path.expanduser().
    Fallback vers le répertoire courant si output_path non fourni.
    """
    if output_path:
        p = Path(output_path).expanduser()
        if p.suffix and p.name != output_path.split("/")[-1]:
            # output_path contient un nom de fichier
            pass
        elif not p.suffix:
            # C'est un répertoire
            p = p / default_name
    else:
        p = Path.cwd() / default_name

    # Créer le répertoire parent si nécessaire
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@tool(
    name="export_moodle_xml",
    description=(
        "Génère un fichier Moodle XML (.xml) contenant une banque de questions (QCM). "
        "Ce format est standard et peut être importé directement dans Pronote, Moodle ou tout ENT de lycée. "
        "Très utile pour créer des quiz Rapides d'évaluation en Physique-Chimie."
    ),
    parameters={
        "type": "object",
        "properties": {
            "category_name": {
                "type": "string",
                "description": "Nom de la catégorie pour ranger ces questions dans la banque (ex: 'Séquence 1 - Cinétique').",
            },
            "questions": {
                "type": "array",
                "description": "Liste des questions QCM.",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Titre court de la question",
                        },
                        "text": {
                            "type": "string",
                            "description": "L'énoncé de la question",
                        },
                        "answers": {
                            "type": "array",
                            "description": "Liste des choix de réponse",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "text": {
                                        "type": "string",
                                        "description": "Le texte du choix",
                                    },
                                    "fraction": {
                                        "type": "integer",
                                        "description": "100 si bonne réponse, 0 si mauvaise réponse. (Pénalité possible: -33, -50)",
                                    },
                                    "feedback": {
                                        "type": "string",
                                        "description": "Feedback optionnel spécifique à cette réponse",
                                    },
                                },
                                "required": ["text", "fraction"],
                            },
                        },
                    },
                    "required": ["name", "text", "answers"],
                },
            },
            "output_path": {
                "type": "string",
                "description": "Chemin de destination (ex: ~/Documents/qcm_cinetique.xml). Optionnel.",
            },
            "filename": {
                "type": "string",
                "description": "Nom du fichier si output_path est omis (ex: qcm_cinetique.xml).",
            },
        },
        "required": ["category_name", "questions"],
    },
)
def export_moodle_xml(
    category_name: str, questions: list[dict], output_path: str = "", filename: str = ""
) -> dict:
    """
    Génère un fichier lisible par Moodle XML Import.
    """
    try:
        name = filename or "export_moodle.xml"
        if not name.endswith(".xml"):
            name += ".xml"
        p = _resolve_output(output_path, name)

        # En-tête Moodle XML
        xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>"]

        # Catégorie
        xml.append('  <question type="category">')
        xml.append("    <category>")
        xml.append(f"      <text><![CDATA[$course$ / {category_name}]]></text>")
        xml.append("    </category>")
        xml.append("  </question>")

        # Questions
        for q in questions:
            xml.append('  <question type="multichoice">')
            xml.append(
                f"    <name><text><![CDATA[{q.get('name', 'Question')}]]></text></name>"
            )
            xml.append(
                f'    <questiontext format="html"><text><![CDATA[{q.get("text", "")}]]></text></questiontext>'
            )
            xml.append("    <single>true</single>")  # Support QCU par défaut
            xml.append("    <shuffleanswers>true</shuffleanswers>")
            xml.append("    <answernumbering>abc</answernumbering>")

            for a in q.get("answers", []):
                fraction = a.get("fraction", 0)
                xml.append(f'    <answer fraction="{fraction}">')
                xml.append(f"      <text><![CDATA[{a.get('text', '')}]]></text>")
                if a.get("feedback"):
                    xml.append(
                        f"      <feedback><text><![CDATA[{a.get('feedback')}]]></text></feedback>"
                    )
                xml.append("    </answer>")

            xml.append("  </question>")

        xml.append("</quiz>")

        p.write_text("\n".join(xml), encoding="utf-8")

        return {
            "status": "success",
            "path": str(p),
            "size_bytes": p.stat().st_size,
            "category_name": category_name,
            "questions_exported": len(questions),
        }

    except Exception as e:
        return {"status": "error", "error": f"export_moodle_xml : {e}"}
