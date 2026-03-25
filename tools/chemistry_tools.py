# ============================================================================
# Prométhée — Assistant IA desktop
# ============================================================================
# Auteur  : Pierre COUGET
# Licence : GNU Affero General Public License v3.0 (AGPL-3.0)
# ============================================================================

"""
tools/chemistry_tools.py — Outils de Chimie (PubChem)
=======================================================

Outils exposés (1):
  - search_chemical_compound : Recherche de molécules

Prérequis :
    pip install pubchempy
"""

from core.tools_engine import tool, set_current_family

set_current_family("chemistry_tools", "Chimie (PubChem)", "🧪")

try:
    import pubchempy as pcp

    _PUBCHEM_AVAILABLE = True
except ImportError:
    _PUBCHEM_AVAILABLE = False


@tool(
    name="search_chemical_compound",
    description=(
        "Recherche les propriétés de base (formule brute, masse molaire, nom IUPAC, "
        "synonymes, numéro CAS) d'une molécule sur PubChem. "
        "Idéal pour préparer les mémorandums de TP de chimie (masses molaires). "
        "Exemples : 'water', 'benzene', 'aspirin', 'hydrochloric acid'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "name_or_formula": {
                "type": "string",
                "description": "Nom de la molécule (ex: 'benzene', 'aspirin', 'hydrochloric acid') ou formule brute/SMILES.",
            }
        },
        "required": ["name_or_formula"],
    },
)
def search_chemical_compound(name_or_formula: str) -> dict:
    """
    Interroge l'API PubChem via pubchempy pour obtenir les propriétés du composé.
    """
    if not _PUBCHEM_AVAILABLE:
        return {
            "status": "error",
            "error": "pubchempy non installé. Installer avec : pip install pubchempy",
        }

    try:
        compounds = pcp.get_compounds(name_or_formula, "name")

        if not compounds:
            return {
                "status": "error",
                "error": (
                    f"Aucune molécule trouvée pour '{name_or_formula}'. "
                    "Essayez avec son équivalent en anglais (ex: 'water' au lieu de 'eau', "
                    "'hydrochloric acid') ou son code SMILES."
                ),
            }

        c = compounds[0]

        return {
            "status": "success",
            "name_or_formula": name_or_formula,
            "iupac_name": c.iupac_name,
            "molecular_formula": c.molecular_formula,
            "molecular_weight": float(c.molecular_weight)
            if c.molecular_weight
            else None,
            "isomeric_smiles": c.isomeric_smiles,
            "charge": c.charge,
            "complexity": c.complexity,
            "synonyms": c.synonyms[:5] if c.synonyms else [],
        }

    except Exception as e:
        return {
            "status": "error",
            "error": f"Erreur lors de l'accès à PubChem : {str(e)}",
        }
