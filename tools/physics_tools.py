# ============================================================================
# Prométhée — Assistant IA desktop
# ============================================================================
# Auteur  : Pierre COUGET
# Licence : GNU Affero General Public License v3.0 (AGPL-3.0)
# ============================================================================

"""
tools/physics_tools.py — Outils de Physique (CODATA/NIST)
=========================================================

Outils exposés (2):
  - get_physical_constant : Constantes fondamentales
  - convert_units : Conversion d'unités

Prérequis :
    pip install scipy
"""

from core.tools_engine import tool, set_current_family, _TOOL_ICONS

set_current_family("physics_tools", "Physique (CODATA/NIST)", "🧲")

_TOOL_ICONS.update(
    {
        "get_physical_constant": "📊",
        "convert_units": "🔄",
    }
)

try:
    import scipy.constants as const

    _SCIPY_AVAILABLE = True
except ImportError:
    _SCIPY_AVAILABLE = False


@tool(
    name="get_physical_constant",
    description=(
        "Récupère la valeur, l'unité et l'incertitude d'une constante physique fondamentale (CODATA / NIST). "
        "Recherche les constantes par mot-clé (ex: 'Planck', 'Avogadro', 'faraday', 'electron mass'). "
        "Privilégiez des mots-clés en anglais pour avoir plus de résultats (ex: 'speed of light', 'Boltzmann')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "Mot-clé ou nom partiel de la constante recherchée (ex: 'Planck', 'gravitation', 'Avogadro').",
            }
        },
        "required": ["keyword"],
    },
)
def get_physical_constant(keyword: str) -> dict:
    """
    Recherche une constante physique dans la base de données de scipy.constants
    (qui encapsule les valeurs recommandées par CODATA).
    """
    if not _SCIPY_AVAILABLE:
        return {
            "status": "error",
            "error": "scipy non installé. Installer avec : pip install scipy",
        }

    keyword_lower = keyword.lower()
    results = []

    # physical_constants est un dictionnaire : clé -> (valeur, unité, incertitude)
    for key, (value, unit, uncertainty) in const.physical_constants.items():
        if keyword_lower in key.lower():
            results.append(
                {"name": key, "value": value, "unit": unit, "uncertainty": uncertainty}
            )

    if not results:
        return {
            "status": "error",
            "error": (
                f"Aucune constante trouvée pour le mot-clé '{keyword}'. "
                "Essayez avec un terme anglais plus générique (ex: 'mass', 'charge', 'constant')."
            ),
        }

    # Limiter le nombre de résultats pour ne pas inonder le LLM
    if len(results) > 10:
        return {
            "status": "success",
            "message": f"Trop de résultats ({len(results)}). Voici les 10 premiers. Soyez plus précis.",
            "results": results[:10],
            "total_found": len(results),
        }

    return {
        "status": "success",
        "keyword": keyword,
        "results": results,
        "count": len(results),
    }


@tool(
    name="convert_units",
    description=(
        "Convertit une valeur d'une unité à une autre (si elles sont homogènes) ou fournit un facteur de conversion. "
        "Utile pour vérifier un changement d'unité dans un exercice ou vérifier la cohérence. "
        "Note : Cet outil utilise les facteurs de conversion de scipy.constants vers le système SI."
    ),
    parameters={
        "type": "object",
        "properties": {
            "value": {
                "type": "number",
                "description": "Chiffre à convertir (ex: 10.5).",
            },
            "from_unit": {
                "type": "string",
                "description": "Unité de départ (ex: 'eV', 'atm', 'calorie', 'angstrom').",
            },
            "to_unit": {
                "type": "string",
                "description": "Unité d'arrivée (ex: 'J', 'Pa', 'joule', 'm').",
            },
        },
        "required": ["value", "from_unit", "to_unit"],
    },
)
def convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    """
    Effectue une conversion basique d'unités via scipy.constants si l'unité de départ
    correspond à un facteur connu (qui convertit souvent vers l'unité SI).
    """
    if not _SCIPY_AVAILABLE:
        return {
            "status": "error",
            "error": "scipy non installé. Installer avec : pip install scipy",
        }

    # Nettoyage
    from_u = from_unit.strip()
    to_u = to_unit.strip()

    # scipy.constants possède des facteurs de conversion directs
    known_factors = {
        "eV": const.eV,
        "electron_volt": const.eV,
        "atm": const.atm,
        "calorie": const.calorie,
        "cal": const.calorie,
        "angstrom": const.angstrom,
        "light_year": const.light_year,
        "parsec": const.parsec,
        "au": const.au,  # Astronomical unit
        "c": const.c,  # Vitesse de la lumière
        "g": const.g,  # Gravité terrestre (pour de la force en kgf)
        "hp": const.hp,  # Horsepower
        "bar": const.bar,
        "mmHg": const.mmHg,
        "knot": const.knot,
        "nautical_mile": const.nautical_mile,
    }

    # C'est une fonction utilitaire très basique. Une approche plus robuste utiliserait `pint` ou `astropy.units`.

    # Si c'est une conversion de/vers le SI
    if from_u in known_factors and to_u in ["J", "Pa", "m", "kg", "s", "m/s", "W"]:
        # Suppose from_u is non-SI, to_u is SI
        result_value = value * known_factors[from_u]
        return {
            "status": "success",
            "value": result_value,
            "unit": to_u,
            "note": f"Conversion basée sur {from_u} dans le système SI",
            "from_unit": from_u,
            "to_unit": to_u,
        }

    if to_u in known_factors and from_u in ["J", "Pa", "m", "kg", "s", "m/s", "W"]:
        # Suppose from_u is SI, to_u is non-SI
        result_value = value / known_factors[to_u]
        return {
            "status": "success",
            "value": result_value,
            "unit": to_u,
            "note": f"Conversion calculée depuis le SI",
            "from_unit": from_u,
            "to_unit": to_u,
        }

    return {
        "status": "not_implemented",
        "message": "Conversion complexe/composée non prise en charge nativement par cet outil léger.",
        "suggestion": "Utilisez python_tools pour un calcul d'unités robuste, ou les valeurs CODATA.",
        "known_direct_factors_to_SI": list(known_factors.keys()),
        "from_unit": from_u,
        "to_unit": to_u,
    }
