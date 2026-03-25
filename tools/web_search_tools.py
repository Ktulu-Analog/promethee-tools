# ============================================================================
# Prométhée — Assistant IA desktop
# ============================================================================
# Auteur  : Pierre COUGET
# Licence : GNU Affero General Public License v3.0 (AGPL-3.0)
# ============================================================================

"""
tools/web_search_tools.py — Recherche Web (DuckDuckGo + SearXNG)
==============================================================

Outils exposés (3):
  - web_search        : Recherche multi-moteurs (DDG ou SearXNG)
  - web_search_news   : Recherche d'actualités récentes
  - web_search_engine : Configuration du moteur actif

Configuration .env (optionnelle) :
    WEB_SEARCH_ENGINE=ddg                    # "ddg" (défaut) ou "searxng"
    WEB_SEARCH_SEARXNG_URL=http://localhost:8080   # URL instance SearXNG
    WEB_SEARCH_DEFAULT_LANG=fr-FR            # langue des résultats

Stratégie :
    - DuckDuckGo : aucune clé API, via POST HTML
    - SearXNG    : instance auto-hébergée, API JSON native
    - Résultats normalisés dans le même format
    - Snippets nettoyés du HTML résiduel

Prérequis :
    pip install requests beautifulsoup4 lxml
"""

import re
from typing import Optional
from urllib.parse import urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup

from core.config import Config
from core.tools_engine import tool, set_current_family, _TOOL_ICONS

set_current_family("web_search_tools", "Recherche Web", "🔍")

# ── Icônes UI ─────────────────────────────────────────────────────────────────
_TOOL_ICONS.update(
    {
        "web_search": "🔍",
        "web_search_news": "📰",
        "web_search_engine": "⚙️",
    }
)

# ── Constantes ────────────────────────────────────────────────────────────────
_DEFAULT_TIMEOUT = 15
_MAX_RESULTS = 25

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}


# ══════════════════════════════════════════════════════════════════════════════
# Helpers internes
# ══════════════════════════════════════════════════════════════════════════════


def _get_engine() -> str:
    """Retourne le moteur configuré : 'ddg' ou 'searxng'."""
    return getattr(Config, "WEB_SEARCH_ENGINE", "ddg").lower().strip()


def _get_searxng_url() -> str:
    """Retourne l'URL de l'instance SearXNG configurée."""
    return getattr(Config, "WEB_SEARCH_SEARXNG_URL", "http://localhost:8080").rstrip(
        "/"
    )


def _get_default_lang() -> str:
    return getattr(Config, "WEB_SEARCH_DEFAULT_LANG", "fr-FR")


def _clean_snippet(raw: str) -> str:
    """Nettoie le HTML résiduel dans un snippet."""
    soup = BeautifulSoup(raw, "lxml")
    text = soup.get_text(separator=" ", strip=True)
    # Supprimer les espaces multiples
    return re.sub(r"\s{2,}", " ", text).strip()


def _decode_ddg_url(href: str) -> str:
    """Décode l'URL DDG encapsulée dans /l/?uddg=..."""
    if "uddg=" in href:
        qs = parse_qs(urlparse(href).query)
        urls = qs.get("uddg", [])
        if urls:
            return unquote(urls[0])
    if href.startswith("/"):
        return "https://duckduckgo.com" + href
    return href


# ── Moteur DuckDuckGo ─────────────────────────────────────────────────────────


def _search_ddg(
    requete: str,
    limite: int = 10,
    region: str = "fr-fr",
    timeout: int = _DEFAULT_TIMEOUT,
    filtre_domaine: Optional[str] = None,
) -> list[dict]:
    """Recherche via DuckDuckGo HTML (sans API key)."""

    # Ajouter le filtre domaine directement dans la requête si demandé
    query = requete
    if filtre_domaine:
        query = f"site:{filtre_domaine} {query}"

    resp = requests.post(
        "https://html.duckduckgo.com/html/",
        data={"q": query, "kl": region},
        headers=_DEFAULT_HEADERS,
        timeout=timeout,
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    resultats = []

    for result in soup.select(".result"):
        title_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")
        url_el = result.select_one(".result__url")

        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        href = _decode_ddg_url(title_el.get("href", ""))

        if not href.startswith("http"):
            continue

        snippet = _clean_snippet(snippet_el.decode_contents()) if snippet_el else ""
        display_url = url_el.get_text(strip=True) if url_el else href

        resultats.append(
            {
                "titre": title,
                "url": href,
                "extrait": snippet,
                "domaine": display_url,
                "moteur": "DuckDuckGo",
            }
        )

        if len(resultats) >= limite:
            break

    return resultats


# ── Moteur SearXNG ────────────────────────────────────────────────────────────


def _search_searxng(
    requete: str,
    limite: int = 10,
    lang: str = "fr-FR",
    timeout: int = _DEFAULT_TIMEOUT,
    categories: str = "general",
    time_range: Optional[str] = None,
    filtre_domaine: Optional[str] = None,
) -> list[dict]:
    """Recherche via instance SearXNG locale (API JSON)."""

    base_url = _get_searxng_url()

    query = requete
    if filtre_domaine:
        query = f"site:{filtre_domaine} {query}"

    params: dict = {
        "q": query,
        "format": "json",
        "categories": categories,
        "language": lang,
    }
    if time_range:
        params["time_range"] = time_range  # "day", "week", "month", "year"

    resp = requests.get(
        f"{base_url}/search",
        params=params,
        headers=_DEFAULT_HEADERS,
        timeout=timeout,
    )
    resp.raise_for_status()

    data = resp.json()
    resultats = []

    for r in data.get("results", [])[:limite]:
        resultats.append(
            {
                "titre": r.get("title", ""),
                "url": r.get("url", ""),
                "extrait": _clean_snippet(r.get("content", "")),
                "domaine": urlparse(r.get("url", "")).netloc,
                "moteur": "SearXNG",
            }
        )

    return resultats


# ── Dispatcher ────────────────────────────────────────────────────────────────


def _search(
    requete: str,
    limite: int = 10,
    lang: str = "",
    timeout: int = _DEFAULT_TIMEOUT,
    filtre_domaine: Optional[str] = None,
    time_range: Optional[str] = None,
    categories: str = "general",
) -> list[dict]:
    """Dispatch vers le moteur configuré."""
    engine = _get_engine()
    lang = lang or _get_default_lang()

    if engine == "searxng":
        return _search_searxng(
            requete,
            limite=limite,
            lang=lang,
            timeout=timeout,
            categories=categories,
            time_range=time_range,
            filtre_domaine=filtre_domaine,
        )
    else:
        # DDG : convertir lang "fr-FR" → région "fr-fr"
        region = lang.lower().replace("_", "-")
        return _search_ddg(
            requete,
            limite=limite,
            region=region,
            timeout=timeout,
            filtre_domaine=filtre_domaine,
        )


# ══════════════════════════════════════════════════════════════════════════════
# OUTILS
# ══════════════════════════════════════════════════════════════════════════════


@tool(
    name="web_search",
    description=(
        "Effectue une recherche sur le web et retourne les résultats "
        "(titre, URL, extrait). Utilise DuckDuckGo ou une instance SearXNG "
        "selon la configuration. "
        "Pour lire le contenu complet d'un résultat, utiliser web_fetch avec l'URL. "
        "Exemples de requêtes : 'loi n° 2023-22 legifrance', "
        "'pandas read_csv documentation', 'actualité IA France 2024'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "requete": {
                "type": "string",
                "description": (
                    "Requête de recherche. Supports les opérateurs avancés : "
                    'site:example.com, filetype:pdf, "phrase exacte", -mot_exclu.'
                ),
            },
            "limite": {
                "type": "integer",
                "description": f"Nombre de résultats (défaut: 10, max: {_MAX_RESULTS}).",
            },
            "langue": {
                "type": "string",
                "description": (
                    "Langue/région des résultats : 'fr-FR' (défaut), 'en-US', 'de-DE', etc."
                ),
            },
            "filtre_domaine": {
                "type": "string",
                "description": (
                    "Restreindre les résultats à un domaine précis "
                    "(ex: 'legifrance.gouv.fr', 'wikipedia.org')."
                ),
            },
            "timeout": {
                "type": "integer",
                "description": f"Délai max en secondes (défaut: {_DEFAULT_TIMEOUT}).",
            },
        },
        "required": ["requete"],
    },
)
def web_search(
    requete: str,
    limite: int = 10,
    langue: str = "",
    filtre_domaine: Optional[str] = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict:
    limite = min(max(1, limite), _MAX_RESULTS)

    try:
        resultats = _search(
            requete,
            limite=limite,
            lang=langue,
            timeout=timeout,
            filtre_domaine=filtre_domaine,
        )

        if not resultats:
            return {
                "status": "success",
                "requete": requete,
                "nombre": 0,
                "resultats": [],
                "message": "Aucun résultat trouvé. Essayez avec d'autres termes.",
            }

        return {
            "status": "success",
            "requete": requete,
            "moteur": _get_engine(),
            "nombre": len(resultats),
            "resultats": resultats,
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "error": f"Timeout après {timeout}s."}
    except requests.exceptions.ConnectionError as e:
        return {"status": "error", "error": f"Connexion impossible : {e}"}
    except Exception as e:
        return {"status": "error", "error": f"Erreur de recherche : {e}"}


@tool(
    name="web_search_news",
    description=(
        "Recherche des actualités récentes sur le web. "
        "Filtre automatiquement les résultats sur une période récente "
        "(dernière journée, semaine ou mois). "
        "Idéal pour : suivi de l'actualité, veille réglementaire, "
        "nouvelles versions de logiciels, événements récents."
    ),
    parameters={
        "type": "object",
        "properties": {
            "requete": {
                "type": "string",
                "description": "Sujet à rechercher (ex: 'RGPD actualité 2024', 'Python 3.13 release').",
            },
            "periode": {
                "type": "string",
                "description": (
                    "Période de recherche : "
                    "'jour' (dernières 24h), "
                    "'semaine' (7 derniers jours, défaut), "
                    "'mois' (30 derniers jours), "
                    "'annee' (12 derniers mois)."
                ),
                "enum": ["jour", "semaine", "mois", "annee"],
            },
            "limite": {
                "type": "integer",
                "description": f"Nombre de résultats (défaut: 10, max: {_MAX_RESULTS}).",
            },
            "langue": {
                "type": "string",
                "description": "Langue des résultats (défaut: 'fr-FR').",
            },
            "timeout": {
                "type": "integer",
                "description": f"Délai max en secondes (défaut: {_DEFAULT_TIMEOUT}).",
            },
        },
        "required": ["requete"],
    },
)
def web_search_news(
    requete: str,
    periode: str = "semaine",
    limite: int = 10,
    langue: str = "",
    timeout: int = _DEFAULT_TIMEOUT,
) -> dict:
    limite = min(max(1, limite), _MAX_RESULTS)

    # Correspondance période → paramètre time_range SearXNG / suffixe DDG
    _periodes = {
        "jour": ("day", "après:"),
        "semaine": ("week", ""),
        "mois": ("month", ""),
        "annee": ("year", ""),
    }
    time_range, _ = _periodes.get(periode, ("week", ""))

    try:
        engine = _get_engine()

        if engine == "searxng":
            resultats = _search_searxng(
                requete,
                limite=limite,
                lang=langue or _get_default_lang(),
                timeout=timeout,
                categories="news,general",
                time_range=time_range,
            )
        else:
            # DDG n'expose pas de filtre date natif dans l'API HTML ;
            # on ajoute une indication temporelle dans la requête pour biaiser les résultats.
            _ddg_time = {"jour": " après 24h", "semaine": "", "mois": "", "annee": ""}
            requete_ddg = requete + _ddg_time.get(periode, "")
            region = (langue or _get_default_lang()).lower().replace("_", "-")
            resultats = _search_ddg(
                requete_ddg,
                limite=limite,
                region=region,
                timeout=timeout,
            )

        if not resultats:
            return {
                "status": "success",
                "requete": requete,
                "periode": periode,
                "nombre": 0,
                "resultats": [],
                "message": "Aucune actualité trouvée pour cette période.",
            }

        return {
            "status": "success",
            "requete": requete,
            "periode": periode,
            "moteur": engine,
            "nombre": len(resultats),
            "resultats": resultats,
        }

    except requests.exceptions.Timeout:
        return {"status": "error", "error": f"Timeout après {timeout}s."}
    except requests.exceptions.ConnectionError as e:
        return {"status": "error", "error": f"Connexion impossible : {e}"}
    except Exception as e:
        return {"status": "error", "error": f"Erreur recherche actualités : {e}"}


@tool(
    name="web_search_engine",
    description=(
        "Retourne la configuration du moteur de recherche actif "
        "(DuckDuckGo ou SearXNG) et ses paramètres. "
        "Utile pour savoir quel moteur est configuré avant d'effectuer une recherche."
    ),
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def web_search_engine() -> dict:
    engine = _get_engine()

    info: dict = {
        "status": "success",
        "moteur_actif": engine,
    }

    if engine == "searxng":
        searxng_url = _get_searxng_url()
        # Vérifier que l'instance répond
        try:
            resp = requests.get(
                f"{searxng_url}/config",
                headers=_DEFAULT_HEADERS,
                timeout=5,
            )
            if resp.status_code == 200:
                cfg = resp.json()
                info["searxng_url"] = searxng_url
                info["searxng_version"] = cfg.get("version", "inconnue")
                info["searxng_statut"] = "disponible"
            else:
                info["searxng_url"] = searxng_url
                info["searxng_statut"] = f"erreur HTTP {resp.status_code}"
        except Exception as e:
            info["searxng_url"] = searxng_url
            info["searxng_statut"] = f"inaccessible ({e})"
    else:
        info["description"] = (
            "DuckDuckGo HTML (sans clé API). "
            "Pour utiliser SearXNG, définissez WEB_SEARCH_ENGINE=searxng "
            "et WEB_SEARCH_SEARXNG_URL dans le fichier .env."
        )

    info["langue_defaut"] = _get_default_lang()
    return info
