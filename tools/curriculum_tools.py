# ============================================================================
# Prométhée — Assistant IA desktop
# ============================================================================
# Auteur  : Pierre COUGET
# Licence : GNU Affero General Public License v3.0 (AGPL-3.0)
# ============================================================================

"""
tools/curriculum_tools.py — Programmes Scolaires (Eduscol)
===========================================================

Outils exposés (1):
  - get_curriculum_guidelines : Recherche dans les programmes Eduscol

Prérequis :
    pip install pypdf                # obligatoire, pour lecture PDF locale

    Optionnels (pour RAG vectoriel):
        pip install qdrant-client     # base vectorielle
        pip install sentence-transformers  # embeddings

Configuration .env (optionnelle):
    RAG_ENABLED=false                 # désactive le RAG, lecture locale uniquement
    RAG_COLLECTION=curriculum_memory
    RAG_MODEL=all-MiniLM-L6-v2
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any

from core.config import Config
from core.tools_engine import tool, set_current_family, _TOOL_ICONS

set_current_family("curriculum_tools", "Programmes (Eduscol)", "🎒")

_TOOL_ICONS.update(
    {
        "get_curriculum_guidelines": "🎓",
    }
)

# Constantes
_LOCAL_DIR = Path("data/programmes_eduscol")
_MAX_RESULTS = 5

# Vérification des dépendances
try:
    import pypdf

    _PYPDF_AVAILABLE = True
except ImportError:
    _PYPDF_AVAILABLE = False

# Vérification du RAG (optionnel)
try:
    from core import rag_engine

    _RAG_AVAILABLE = rag_engine.is_available()
except (ImportError, AttributeError):
    _RAG_AVAILABLE = False


def _is_rag_enabled() -> bool:
    """Vérifie si le RAG est disponible et activé."""
    if not _RAG_AVAILABLE:
        return False
    return getattr(Config, "RAG_ENABLED", "false").lower() in ("true", "yes", "1")


def _sync_and_ingest_programs() -> None:
    """Synchronise et ingère les PDF dans le RAG (si activé)."""
    if not _is_rag_enabled():
        return

    _LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    # Récupérer les sources existantes
    try:
        existing_sources = {
            s["source"] for s in rag_engine.list_sources(conversation_id="global")
        }
    except Exception:
        existing_sources = set()

    for pdf_path in _LOCAL_DIR.glob("*.pdf"):
        if pdf_path.stat().st_size == 0:
            continue

        if pdf_path.name not in existing_sources:
            try:
                rag_engine.ingest_file(str(pdf_path), conversation_id="global")
            except Exception:
                # Ignorer les erreurs d'ingestion silencieusement
                pass


def _search_local_pdfs(query: str, limit: int = _MAX_RESULTS) -> list[dict]:
    """
    Recherche dans les PDF locaux via pypdf (sans RAG).
    Plus lent mais ne nécessite pas Qdrant.
    """
    if not _PYPDF_AVAILABLE:
        return [{"error": "pypdf non installé. Installer avec : pip install pypdf"}]

    results = []
    query_lower = query.lower()

    for pdf_path in _LOCAL_DIR.glob("*.pdf"):
        try:
            reader = pypdf.PdfReader(pdf_path)
            text = ""
            # Limiter aux 3 premières pages pour la recherche rapide
            for page in reader.pages[:3]:
                try:
                    text += page.extract_text() + "\n"
                except Exception:
                    continue

            # Recherche basique de mots-clés
            if query_lower in text.lower():
                results.append(
                    {
                        "source": pdf_path.name,
                        "path": str(pdf_path),
                        "score": 1.0,  # Score arbitraire (pas de similarité vectorielle)
                        "text": text[:500] + "..." if len(text) > 500 else text,
                    }
                )
        except Exception:
            continue

    return results[:limit]


@tool(
    name="get_curriculum_guidelines",
    description=(
        "Récupère les directives du programme officiel pour un niveau donné "
        "en Physique-Chimie (ex: 'Terminale Spécialité', 'PCSI', 'Seconde'). "
        "Recherche dans les programmes Eduscol. "
        "Si le RAG est activé, utilise une recherche vectorielle (rapide et précise). "
        "Sinon, effectue une recherche locale dans les PDF (plus lente). "
        "Prérequis : déposer les PDF des B.O. dans data/programmes_eduscol/."
    ),
    parameters={
        "type": "object",
        "properties": {
            "level": {
                "type": "string",
                "description": "Niveau visé (ex: 'Seconde', 'Première Spécialité', 'Terminale Spécialité', 'PCSI', 'MPSI').",
            },
            "domain": {
                "type": "string",
                "description": "Domaine spécifique (ex: 'Thermodynamique', 'Ondes', 'Cinétique').",
            },
        },
        "required": ["level"],
    },
)
def get_curriculum_guidelines(level: str, domain: str = "") -> dict:
    """
    Fournit un résumé des attentes du programme via RAG ou recherche locale.
    """
    # Vérifier que les PDF existent
    if not _LOCAL_DIR.exists() or len(list(_LOCAL_DIR.glob("*.pdf"))) == 0:
        return {
            "status": "error",
            "error": (
                f"Aucun PDF trouvé dans {_LOCAL_DIR}. "
                "Déposez les B.O. d'Eduscol dans ce dossier."
            ),
        }

    # Construction de la requête
    query = f"Programme officiel {level}"
    if domain:
        query += f" capacités exigibles : {domain}"

    # RAG activé ?
    if _is_rag_enabled():
        _sync_and_ingest_programs()
        try:
            hits = rag_engine.search(
                query, top_k=_MAX_RESULTS, conversation_id="global"
            )

            if not hits:
                return {
                    "status": "error",
                    "error": (
                        f"Aucun résultat pour '{query}'. "
                        "Vérifiez que les PDF des B.O. ont été déposés dans data/programmes_eduscol/."
                    ),
                    "note_stricte": (
                        "INTERDICTION ABSOLUE d'aborder des notions de niveau supérieur "
                        "(pas d'entropie au lycée, etc.)."
                    ),
                }

            return {
                "status": "success",
                "level": level,
                "domain": domain,
                "search_mode": "RAG (vectoriel)",
                "results": [
                    {
                        "source": h["source"],
                        "score": h["score"],
                        "text": h["text"][:500] + "..."
                        if len(h["text"]) > 500
                        else h["text"],
                    }
                    for h in hits
                ],
            }
        except Exception as e:
            return {
                "status": "error",
                "error": f"Erreur lors de la recherche RAG : {e}",
            }
    else:
        # Recherche locale (fallback)
        hits = _search_local_pdfs(query)

        if not hits or "error" in hits[0]:
            return {
                "status": "error",
                "error": f"Aucun résultat pour '{query}'. {hits[0].get('error', '')}",
            }

        return {
            "status": "success",
            "level": level,
            "domain": domain,
            "search_mode": "local (pypdf)",
            "results": hits,
        }
