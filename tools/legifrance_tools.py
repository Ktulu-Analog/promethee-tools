# ============================================================================
# Prométhée — Assistant IA desktop
# ============================================================================
# Auteur  : Pierre COUGET
# Licence : GNU Affero General Public License v3.0 (AGPL-3.0)
#           https://www.gnu.org/licenses/agpl-3.0.html
# Année   : 2026
# ----------------------------------------------------------------------------
# Ce fichier fait partie du projet Prométhée.
# Vous pouvez le redistribuer et/ou le modifier selon les termes de la
# licence AGPL-3.0 publiée par la Free Software Foundation.
# ============================================================================

"""
tools/legifrance_tools.py — Outils Légifrance pour Prométhée
=====================================================================

Intègre les 57 outils Légifrance dans le moteur d'outils de Prométhée.
Suit le même pattern que math_tools, system_tools et data_tools.

Usage dans main.py ou app.py :
    import tools.legifrance_tools  # noqa — enregistre les outils au démarrage

Ou via register_all() dans tools/__init__.py :
    from tools import register_all
    register_all()

Les outils sont ensuite automatiquement disponibles dans agent_loop()
via get_tool_schemas() et call_tool().

Prérequis dans .env :
    LEGIFRANCE_CLIENT_ID=votre_client_id
    LEGIFRANCE_CLIENT_SECRET=votre_client_secret

Outils disponibles (57 au total) :
  Recherche (4)   : legifrance_rechercher, legifrance_version_canonique_article,
                    legifrance_version_canonique, legifrance_version_proche
  Consultation codes/lois (11) :
                    legifrance_consulter_code, legifrance_code_complet,
                    legifrance_code_par_ancien_id,
                    legifrance_obtenir_article, legifrance_article_par_numero,
                    legifrance_article_par_eli, legifrance_versions_article,
                    legifrance_articles_meme_numero,
                    legifrance_loi_decret, legifrance_legi_part,
                    legifrance_tables_annuelles
  Liens d'articles (4) :
                    legifrance_liens_concordance, legifrance_liens_relatifs,
                    legifrance_liens_service_public, legifrance_a_liens_service_public
  Consultation JORF (6) :
                    legifrance_jorf, legifrance_jorf_part,
                    legifrance_jo_par_nor, legifrance_eli_alias_texte,
                    legifrance_derniers_jo, legifrance_sommaire_jorf
  Consultation KALI (5) :
                    legifrance_convention_par_idcc, legifrance_convention_cont,
                    legifrance_convention_texte, legifrance_convention_article,
                    legifrance_convention_section
  Consultation jurisprudence (3) :
                    legifrance_jurisprudence, legifrance_jurisprudence_plan_classement,
                    legifrance_jurisprudence_ancien_id
  Consultation divers (7) :
                    legifrance_cnil, legifrance_cnil_ancien_id,
                    legifrance_acco, legifrance_circulaire,
                    legifrance_debat, legifrance_dossier_legislatif,
                    legifrance_section_par_cid
  Consultation BOCC (1) :
                    legifrance_bocc_pdf_metadata
  Chrono (3)      : legifrance_historique_texte, legifrance_versions_element,
                    legifrance_a_des_versions
  List (12)       : legifrance_lister_codes, legifrance_conventions,
                    legifrance_lister_loda, legifrance_lister_legislatures,
                    legifrance_lister_dossiers_legislatifs,
                    legifrance_lister_debats_parlementaires,
                    legifrance_lister_questions_parlementaires,
                    legifrance_lister_bocc, legifrance_lister_bocc_textes,
                    legifrance_lister_boccs_et_textes, legifrance_lister_docs_admins,
                    legifrance_lister_bodmr
  Suggest (3)     : legifrance_suggerer, legifrance_suggerer_acco,
                    legifrance_suggerer_pdc
  Misc (3)        : legifrance_dates_sans_jo, legifrance_annees_sans_table,
                    legifrance_commit_id
"""

import logging
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from core.tools_engine import set_current_family, tool

set_current_family("legifrance_tools", "Légifrance", "⚖️")

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Icônes pour l'UI Prométhée Desktop (ajoutées au registre _TOOL_ICONS)
# ---------------------------------------------------------------------------
try:
    from core.tools_engine import _TOOL_ICONS
    _TOOL_ICONS.update({
        # Recherche
        "legifrance_rechercher":                       "⚖️",
        "legifrance_version_canonique_article":        "🔍",
        "legifrance_version_canonique":                "📌",
        "legifrance_version_proche":                   "📍",
        # Consultation codes / lois
        "legifrance_consulter_code":                   "📖",
        "legifrance_obtenir_article":                  "📄",
        "legifrance_article_par_numero":               "🔢",
        "legifrance_versions_article":                 "🕐",
        "legifrance_loi_decret":                       "📜",
        "legifrance_jorf":                             "🗞️",
        "legifrance_jo_par_nor":                       "🗞️",
        "legifrance_derniers_jo":                      "📰",
        "legifrance_sommaire_jorf":                    "📑",
        # Conventions collectives (KALI)
        "legifrance_convention_par_idcc":              "🤝",
        "legifrance_convention_texte":                 "🤝",
        "legifrance_convention_article":               "🤝",
        "legifrance_convention_section":               "🤝",
        # Jurisprudence
        "legifrance_jurisprudence":                    "🏛️",
        "legifrance_jurisprudence_plan_classement":    "🗂️",
        # Consultation divers
        "legifrance_cnil":                             "🔒",
        "legifrance_acco":                             "🏢",
        "legifrance_circulaire":                       "📬",
        "legifrance_debat":                            "🎙️",
        "legifrance_dossier_legislatif":               "🗃️",
        "legifrance_section_par_cid":                  "📂",
        # Chrono
        "legifrance_historique_texte":                 "⏳",
        "legifrance_versions_element":                 "🕰️",
        "legifrance_a_des_versions":                   "✅",
        # List
        "legifrance_lister_codes":                     "📋",
        "legifrance_conventions":                      "🤝",
        "legifrance_lister_loda":                      "📜",
        "legifrance_lister_legislatures":              "🏛️",
        "legifrance_lister_dossiers_legislatifs":      "🗃️",
        "legifrance_lister_debats_parlementaires":     "🎙️",
        "legifrance_lister_questions_parlementaires":  "❓",
        "legifrance_lister_bocc":                      "📋",
        "legifrance_lister_bocc_textes":               "📄",
        "legifrance_lister_boccs_et_textes":           "📑",
        "legifrance_lister_docs_admins":               "🗂️",
        # Suggest
        "legifrance_suggerer":                         "💡",
        "legifrance_suggerer_acco":                    "🏢",
        "legifrance_suggerer_pdc":                     "🗂️",
        # Misc
        "legifrance_dates_sans_jo":                    "📅",
        "legifrance_annees_sans_table":                "📆",
        "legifrance_commit_id":                        "🔖",
        # List
        "legifrance_lister_bodmr":                     "🎖️",
        # Consult — codes
        "legifrance_code_complet":                     "📖",
        "legifrance_code_par_ancien_id":               "🔄",
        "legifrance_article_par_eli":                  "🔗",
        "legifrance_articles_meme_numero":             "🔢",
        # Consult — liens d'articles
        "legifrance_liens_concordance":                "🔀",
        "legifrance_liens_relatifs":                   "🔗",
        "legifrance_liens_service_public":             "🏛️",
        "legifrance_a_liens_service_public":           "✅",
        # Consult — JORF
        "legifrance_jorf_part":                        "🗞️",
        "legifrance_eli_alias_texte":                  "🔗",
        # Consult — KALI
        "legifrance_convention_cont":                  "🤝",
        # Consult — JURI
        "legifrance_jurisprudence_ancien_id":          "🏛️",
        # Consult — CNIL
        "legifrance_cnil_ancien_id":                   "🔒",
        # Consult — LEGI
        "legifrance_legi_part":                        "📜",
        # Consult — tables
        "legifrance_tables_annuelles":                 "📅",
        # Consult — BOCC
        "legifrance_bocc_pdf_metadata":                "📄",
    })
except Exception:
    pass


# ---------------------------------------------------------------------------
# Client Légifrance (autonome, lit le .env de l'applcaton)
# ---------------------------------------------------------------------------

class _LegifranceClient:
    """
    Client OAuth2 PISTE — singleton, partagé par tous les outils.
    Lit LEGIFRANCE_CLIENT_ID et LEGIFRANCE_CLIENT_SECRET depuis
    l'environnement (déjà chargé par config.py via python-dotenv).
    """

    PRODUCTION_BASE_URL = "https://api.piste.gouv.fr/dila/legifrance/lf-engine-app"
    OAUTH_URL           = "https://oauth.piste.gouv.fr/api/oauth/token"

    # Noms de codes → ID Légifrance
    CODE_IDS: Dict[str, str] = {
        "civil":                    "LEGITEXT000006070721",
        "penal":                    "LEGITEXT000006070719",
        "travail":                  "LEGITEXT000006072050",
        "commerce":                 "LEGITEXT000005634379",
        "consommation":             "LEGITEXT000006069565",
        "procedure_civile":         "LEGITEXT000006070716",
        "procedure_penale":         "LEGITEXT000006071154",
        "sante_publique":           "LEGITEXT000006072665",
        "education":                "LEGITEXT000006071191",
        "environnement":            "LEGITEXT000006074220",
        "securite_sociale":         "LEGITEXT000006073189",
        "general_collectivites":    "LEGITEXT000006070633",
        "urbanisme":                "LEGITEXT000006074075",
        "propriete_intellectuelle": "LEGITEXT000006069414",
        "assurances":               "LEGITEXT000006073984",
        "monetaire_financier":      "LEGITEXT000006072026",
    }

    def __init__(self):
        # NE PAS lire os.getenv() ici : le .env peut ne pas encore être chargé
        # au moment de l'import du module. On lit en live à chaque appel.
        self._token: Optional[str] = None
        self._token_expiry: float  = 0
        self._http = httpx.Client(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
        )

    @property
    def client_id(self) -> Optional[str]:
        return os.getenv("LEGIFRANCE_CLIENT_ID")

    @property
    def client_secret(self) -> Optional[str]:
        return os.getenv("LEGIFRANCE_CLIENT_SECRET")

    def _check_credentials(self):
        # Relecture en live : capte les valeurs chargées par config.py
        # même si legifrance_tools a été importé avant le load_dotenv()
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "Identifiants Légifrance manquants.\n"
                "Ajoutez dans votre .env :\n"
                "  LEGIFRANCE_CLIENT_ID=...\n"
                "  LEGIFRANCE_CLIENT_SECRET=..."
            )

    def _get_token(self) -> str:
        self._check_credentials()
        if self._token and time.time() < (self._token_expiry - 60):
            return self._token
        r = self._http.post(
            self.OAUTH_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     self.client_id,
                "client_secret": self.client_secret,
                "scope":         "openid",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        d = r.json()
        self._token        = d["access_token"]
        self._token_expiry = time.time() + d.get("expires_in", 3600)
        return self._token

    def _req(self, path: str, method: str = "POST", body: Optional[Dict] = None) -> Dict:
        url = f"{self.PRODUCTION_BASE_URL}{path}"
        for attempt in range(3):
            try:
                resp = self._http.request(
                    method=method.upper(),
                    url=url,
                    headers={
                        "Authorization":  f"Bearer {self._get_token()}",
                        "Accept":         "application/json",
                        "Content-Type":   "application/json",
                    },
                    json=body,
                )
                if resp.status_code == 401 and attempt == 0:
                    self._token = None
                    continue
                if resp.status_code == 429:
                    raise RuntimeError("Limite de débit API Légifrance atteinte (429)")
                resp.raise_for_status()
                ct = resp.headers.get("Content-Type", "")
                if "application/json" in ct:
                    return resp.json()
                return {"content": resp.text}
            except httpx.HTTPStatusError as e:
                if attempt == 2 or e.response.status_code < 500:
                    raise RuntimeError(f"Erreur HTTP {e.response.status_code} sur {path}")
                time.sleep(2 ** attempt)
            except httpx.RequestError as e:
                if attempt == 2:
                    raise RuntimeError(f"Erreur réseau : {e}")
                time.sleep(2 ** attempt)
        raise RuntimeError(f"Échec après 3 tentatives sur {path}")

    def resolve_code(self, code: str) -> str:
        """Résout un nom de code en ID Légifrance."""
        if code.startswith("LEGITEXT"):
            return code
        key = code.lower().replace(" ", "_").replace("-", "_")
        rid = self.CODE_IDS.get(key)
        if not rid:
            known = ", ".join(self.CODE_IDS.keys())
            raise ValueError(
                f"Code non reconnu : '{code}'.\n"
                f"Noms valides : {known}\n"
                f"Ou utilisez directement un ID LEGITEXT..."
            )
        return rid


# Singleton partagé
_client: Optional[_LegifranceClient] = None

def _get_client() -> _LegifranceClient:
    global _client
    if _client is None:
        _client = _LegifranceClient()
    return _client


# ---------------------------------------------------------------------------
# Formatage Markdown des résultats
# ---------------------------------------------------------------------------

def _strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"<p[^>]*>", "\n", text)
    text = re.sub(r"</p>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _fmt_search(data: Dict, query: str) -> str:
    results = data.get("results", [])
    total   = data.get("totalResultNumber", 0)
    if not results:
        return f"Aucun résultat pour : « {query} »"
    lines = [f"**{total} résultat(s) pour « {query} »** — {len(results)} affichés\n"]
    for i, r in enumerate(results, 1):
        t_list  = r.get("titles", [{}])
        title   = t_list[0].get("title",           r.get("title", "Sans titre"))
        nature  = t_list[0].get("nature",           r.get("nature", ""))
        rid     = t_list[0].get("id",               r.get("id", ""))
        date_p  = t_list[0].get("datePubliTexte",   "")
        lines.append(f"{i}. **{title}**")
        if nature: lines.append(f"   Nature : {nature}")
        if rid:    lines.append(f"   ID : `{rid}`")
        if date_p: lines.append(f"   Date : {date_p}")
        lines.append("")
    return "\n".join(lines)


def _fmt_article(data: Dict) -> str:
    a      = data.get("article", data)
    num    = a.get("num",    a.get("numero", ""))
    texte  = _strip_html(a.get("texte", a.get("content", a.get("texteHtml", ""))))
    rid    = a.get("id", "")
    etat   = a.get("etat", "")
    debut  = a.get("dateDebut", "")
    lines  = []
    if num:   lines.append(f"**Article {num}**")
    if rid:   lines.append(f"ID : `{rid}`")
    if etat:  lines.append(f"État : {etat}")
    if debut: lines.append(f"En vigueur depuis : {debut}")
    lines.append(f"\n{texte}" if texte else "\n*(texte non disponible)*")
    return "\n".join(lines)


def _fmt_toc(data: Dict, code: str) -> str:
    titre  = data.get("titre", data.get("title", code))
    lines  = [f"# {titre}\n"]

    def walk(items, depth=0):
        indent = "  " * depth
        for item in items:
            t   = item.get("titre", item.get("title", item.get("num", "")))
            rid = item.get("id", "")
            if t:
                if depth == 0:
                    lines.append(f"\n## {t}")
                else:
                    lines.append(f"{indent}- {t}" + (f" (`{rid}`)" if rid else ""))
            children = item.get("sections", item.get("articles", item.get("children", [])))
            if children and depth < 3:
                walk(children, depth + 1)

    walk(data.get("sections", data.get("articles", [])))
    return "\n".join(lines) if len(lines) > 1 else f"Structure vide pour {code}."


# ---------------------------------------------------------------------------
# Définition des outils Légifrance
# Préfixe "legifrance_" pour les distinguer des outils existants de Prométhée
# ---------------------------------------------------------------------------

@tool(
    name="legifrance_rechercher",
    description=(
        "Recherche de textes juridiques français dans Légifrance : codes, lois, décrets, "
        "arrêtés, circulaires, jurisprudence, conventions collectives, Journal Officiel. "
        "Retourne une liste avec titres, natures et identifiants."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Mots-clés (ex: 'responsabilité civile', 'licenciement abusif', 'RGPD')",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 10,
                "description": "Nombre de résultats (1–20, défaut: 10)",
            },
            "fond": {
                "type": "string",
                "enum": ["ALL", "JORF", "LODA", "CODE_DATE", "JURI", "KALI", "CNIL"],
                "default": "ALL",
                "description": "Fonds à interroger (ALL=tous, JURI=jurisprudence, KALI=conventions collectives…)",
            },
        },
        "required": ["query"],
    },
)
def legifrance_rechercher(query: str, nb_resultats: int = 10, fond: str = "ALL") -> str:
    c = _get_client()
    data = c._req("/search", body={
        "fond": fond,
        "recherche": {
            "champs": [{
                "typeChamp": "ALL",
                "criteres": [{"typeRecherche": "UN_DES_MOTS", "valeur": query, "operateur": "ET"}],
                "operateur": "ET",
            }],
            "operateur":      "ET",
            "pageSize":       min(max(1, nb_resultats), 20),
            "pageNumber":     1,
            "sort":           "PERTINENCE",
            "typePagination": "DEFAUT",
        },
    })
    return _fmt_search(data, query)


@tool(
    name="legifrance_consulter_code",
    description=(
        "Consulte la table des matières structurée d'un code juridique français "
        "(Code civil, pénal, du travail, de commerce, etc.). "
        "Retourne la hiérarchie des parties, livres, titres et articles avec leurs identifiants. "
        "Utilisez legifrance_obtenir_article ou legifrance_article_par_numero pour lire un article précis."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Nom du code (civil, penal, travail, commerce, consommation, "
                    "procedure_civile, procedure_penale, sante_publique, education, "
                    "environnement, securite_sociale, urbanisme, assurances, "
                    "monetaire_financier, propriete_intellectuelle) "
                    "ou directement un ID Légifrance (LEGITEXT...)."
                ),
            },
            "date": {
                "type": "string",
                "description": "Date de consultation YYYY-MM-DD (défaut: aujourd'hui)",
            },
        },
        "required": ["code"],
    },
)
def legifrance_consulter_code(code: str, date: Optional[str] = None) -> str:
    c      = _get_client()
    try:
        tid = c.resolve_code(code)
    except ValueError as e:
        return str(e)
    data = c._req("/consult/legi/tableMatieres", body={
        "textId": tid,
        "date":   date or globals()["date"].today().isoformat(),
    })
    return _fmt_toc(data, code)


@tool(
    name="legifrance_obtenir_article",
    description=(
        "Récupère le texte complet d'un article juridique par son identifiant Légifrance "
        "(format LEGIARTI000XXXXXXXXX). L'ID s'obtient via legifrance_rechercher ou legifrance_consulter_code."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_id": {
                "type": "string",
                "description": "Identifiant Légifrance de l'article (ex: LEGIARTI000006419283)",
            },
        },
        "required": ["article_id"],
    },
)
def legifrance_obtenir_article(article_id: str) -> str:
    c    = _get_client()
    data = c._req("/consult/getArticle", body={"id": article_id})
    return _fmt_article(data)


@tool(
    name="legifrance_article_par_numero",
    description=(
        "Récupère un article d'un code ou d'un texte par son numéro (ex: '1382', 'L1234-5', 'R123-1'). "
        "Plus pratique que legifrance_obtenir_article quand on connaît le numéro mais pas l'ID."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Nom du code (civil, travail…) ou ID Légifrance (LEGITEXT...)",
            },
            "numero": {
                "type": "string",
                "description": "Numéro de l'article (ex: '1382', 'L1234-5', 'R10')",
            },
        },
        "required": ["code", "numero"],
    },
)
def legifrance_article_par_numero(code: str, numero: str) -> str:
    c = _get_client()
    try:
        tid = c.resolve_code(code)
    except ValueError as e:
        return str(e)
    data = c._req("/consult/getArticleWithIdAndNum", body={"id": tid, "num": numero})
    return _fmt_article(data)


@tool(
    name="legifrance_versions_article",
    description=(
        "Récupère l'historique complet des versions d'un article pour suivre "
        "ses modifications législatives au fil du temps. Utilise le CID de l'article."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_cid": {
                "type": "string",
                "description": "CID (identifiant canonique) de l'article",
            },
        },
        "required": ["article_cid"],
    },
)
def legifrance_versions_article(article_cid: str) -> str:
    c        = _get_client()
    data     = c._req("/consult/getArticleByCid", body={"cid": article_cid})
    versions = data.get("versions", data.get("articles", []))
    if not versions:
        return f"Aucune version trouvée pour le CID `{article_cid}`."
    lines = [f"**{len(versions)} version(s) de l'article `{article_cid}`**\n"]
    for v in versions:
        lines.append(_fmt_article(v))
        lines.append("\n---\n")
    return "\n".join(lines)


@tool(
    name="legifrance_loi_decret",
    description=(
        "Consulte le contenu complet d'une loi, d'un décret, d'une ordonnance ou d'un arrêté "
        "(fonds LODA). Retourne les articles structurés du texte."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_id": {
                "type": "string",
                "description": "Identifiant Légifrance du texte (ex: LEGITEXT000006353440)",
            },
            "date": {
                "type": "string",
                "description": "Date de consultation YYYY-MM-DD (défaut: aujourd'hui)",
            },
        },
        "required": ["text_id"],
    },
)
def legifrance_loi_decret(text_id: str, date: Optional[str] = None) -> str:
    c    = _get_client()
    data = c._req("/consult/lawDecree", body={
        "textId": text_id,
        "date":   date or globals()["date"].today().isoformat(),
    })
    titre    = data.get("titre", data.get("title", text_id))
    nature   = data.get("nature", "")
    nor      = data.get("nor", "")
    date_pub = data.get("datePubliTexte", "")
    lines    = [f"# {titre}\n"]
    if nature:   lines.append(f"**Nature** : {nature}")
    if nor:      lines.append(f"**NOR** : {nor}")
    if date_pub: lines.append(f"**Publication** : {date_pub}")
    articles = data.get("articles", data.get("sections", []))
    if articles:
        lines.append(f"\n**{len(articles)} article(s)**\n")
        for a in articles[:50]:
            lines.append(_fmt_article(a))
            lines.append("")
        if len(articles) > 50:
            lines.append(f"*… {len(articles)-50} article(s) supplémentaires non affichés*")
    return "\n".join(lines)


@tool(
    name="legifrance_jorf",
    description=(
        "Consulte un texte publié au Journal Officiel de la République Française (JORF). "
        "Retourne le contenu et les métadonnées de publication."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_cid": {
                "type": "string",
                "description": "CID du texte JORF (ex: JORFTEXT000000000001)",
            },
        },
        "required": ["text_cid"],
    },
)
def legifrance_jorf(text_cid: str) -> str:
    c      = _get_client()
    data   = c._req("/consult/jorf", body={"textCid": text_cid})
    titre  = data.get("titre", data.get("title", text_cid))
    lines  = [f"# {titre}\n"]
    date_p = data.get("datePubliTexte", "")
    if date_p: lines.append(f"**Publication JO** : {date_p}")
    texte  = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:4000]}")
        if len(texte) > 4000:
            lines.append("\n*[Texte tronqué — consultez Légifrance pour le texte intégral]*")
    return "\n".join(lines)


@tool(
    name="legifrance_jurisprudence",
    description=(
        "Consulte une décision de justice française (jurisprudence). "
        "Retourne le texte complet de la décision avec la juridiction et la date."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_id": {
                "type": "string",
                "description": "Identifiant de la décision (ex: JURITEXT000007587512)",
            },
        },
        "required": ["text_id"],
    },
)
def legifrance_jurisprudence(text_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/juri", body={"textId": text_id})
    titre = data.get("titre", data.get("title", text_id))
    lines = [f"# {titre}\n"]
    juri  = data.get("juridiction", "")
    dt    = data.get("dateDecision", data.get("date", ""))
    if juri: lines.append(f"**Juridiction** : {juri}")
    if dt:   lines.append(f"**Date** : {dt}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:5000]}")
        if len(texte) > 5000:
            lines.append("\n*[Texte tronqué]*")
    return "\n".join(lines)


@tool(
    name="legifrance_lister_codes",
    description=(
        "Liste tous les codes juridiques disponibles dans Légifrance avec leurs identifiants. "
        "Utile pour trouver l'ID d'un code avant de le consulter."
    ),
    parameters={
        "type": "object",
        "properties": {
            "filtre": {
                "type": "string",
                "description": "Filtre par nom (optionnel, ex: 'code de la route', 'environnement')",
            },
            "en_vigueur_seulement": {
                "type": "boolean",
                "default": True,
                "description": "Retourner uniquement les codes en vigueur (défaut: true)",
            },
        },
    },
)
def legifrance_lister_codes(filtre: Optional[str] = None, en_vigueur_seulement: bool = True) -> str:
    c     = _get_client()
    body  = {"pageNumber": 1, "pageSize": 100}
    if filtre:               body["codeName"] = filtre
    if en_vigueur_seulement: body["states"]   = ["VIGUEUR"]
    data  = c._req("/list/code", body=body)
    codes = data.get("results", data.get("codes", []))
    if not codes:
        return "Aucun code trouvé."
    lines = [f"**{len(codes)} code(s)**\n"]
    for code in codes:
        t   = code.get("titre", code.get("title", ""))
        rid = code.get("id",    code.get("cid", ""))
        lines.append(f"- **{t}**" + (f" — `{rid}`" if rid else ""))
    return "\n".join(lines)


@tool(
    name="legifrance_conventions",
    description=(
        "Liste et recherche les conventions collectives disponibles dans Légifrance (fonds KALI). "
        "Filtrable par titre ou numéro IDCC."
    ),
    parameters={
        "type": "object",
        "properties": {
            "titre": {
                "type": "string",
                "description": "Recherche par titre (ex: 'métallurgie', 'bâtiment', 'commerce de détail')",
            },
            "idcc": {
                "type": "string",
                "description": "Numéro IDCC exact (ex: '0016', '1486')",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_conventions(
    titre: Optional[str] = None,
    idcc:  Optional[str] = None,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body = {"pageNumber": 1, "pageSize": nb_resultats}
    if titre: body["titre"] = titre
    if idcc:  body["idcc"]  = idcc
    data  = c._req("/list/conventions", body=body)
    items = data.get("results", data.get("conventions", []))
    if not items:
        return "Aucune convention collective trouvée."
    lines = [f"**{len(items)} convention(s)**\n"]
    for cv in items:
        t    = cv.get("titre", cv.get("title", ""))
        idcc = cv.get("idcc", "")
        rid  = cv.get("id", "")
        lines.append(
            f"- **{t}**"
            + (f" (IDCC {idcc})" if idcc else "")
            + (f" — `{rid}`"     if rid  else "")
        )
    return "\n".join(lines)


@tool(
    name="legifrance_suggerer",
    description=(
        "Suggestions et autocomplétion pour identifier un texte juridique dont on connaît "
        "le début du nom. Utile avant une recherche ou consultation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "texte": {
                "type": "string",
                "description": "Début du nom à compléter (ex: 'code de la consom', 'loi du 17 juil')",
            },
        },
        "required": ["texte"],
    },
)
def legifrance_suggerer(texte: str) -> str:
    c    = _get_client()
    data = c._req("/suggest", body={"searchText": texte})
    suggestions = data.get("suggestions", data.get("results", []))
    if not suggestions:
        return f"Aucune suggestion pour : « {texte} »"
    lines = [f"**Suggestions pour « {texte} »**\n"]
    for s in suggestions[:15]:
        t   = s.get("title", s.get("titre", s.get("text", str(s))))
        rid = s.get("id", "")
        lines.append(f"- {t}" + (f" (`{rid}`)" if rid else ""))
    return "\n".join(lines)


# ===========================================================================
# OUTILS SEARCH — versions canoniques
# ===========================================================================

@tool(
    name="legifrance_version_canonique_article",
    description=(
        "Récupère les informations de version canonique d'un article à partir de son identifiant. "
        "Utile pour résoudre l'identifiant stable (CID) d'un article dont on connaît l'ID versionnée."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_id": {
                "type": "string",
                "description": "Identifiant de l'article (ex: LEGIARTI000006436298)",
            },
        },
        "required": ["article_id"],
    },
)
def legifrance_version_canonique_article(article_id: str) -> str:
    c    = _get_client()
    data = c._req("/search/canonicalArticleVersion", body={"id": article_id})
    lines = [f"**Version canonique de l'article `{article_id}`**\n"]
    for k, v in data.items():
        if v:
            lines.append(f"- **{k}** : {v}")
    return "\n".join(lines) if len(lines) > 1 else f"Aucune information pour `{article_id}`."


@tool(
    name="legifrance_version_canonique",
    description=(
        "Récupère les informations de version canonique d'un texte à une date donnée. "
        "Permet de déterminer quelle version d'un texte était en vigueur à une date précise."
    ),
    parameters={
        "type": "object",
        "properties": {
            "cid_text": {
                "type": "string",
                "description": "CID du texte (ex: LEGITEXT000006070721)",
            },
            "date": {
                "type": "string",
                "description": "Date de référence au format YYYY-MM-DD",
            },
            "cid_section": {
                "type": "string",
                "description": "CID de la section (optionnel)",
            },
        },
        "required": ["cid_text", "date"],
    },
)
def legifrance_version_canonique(cid_text: str, date: str, cid_section: Optional[str] = None) -> str:
    c    = _get_client()
    body = {"cidText": cid_text, "date": date}
    if cid_section:
        body["cidSection"] = cid_section
    data  = c._req("/search/canonicalVersion", body=body)
    lines = [f"**Version canonique de `{cid_text}` au {date}**\n"]
    for k, v in data.items():
        if v:
            lines.append(f"- **{k}** : {v}")
    return "\n".join(lines) if len(lines) > 1 else "Aucune information de version canonique trouvée."


@tool(
    name="legifrance_version_proche",
    description=(
        "Récupère la version d'un texte la plus proche d'une date donnée. "
        "Utile quand la date exacte n'a pas de version et qu'on veut la version voisine."
    ),
    parameters={
        "type": "object",
        "properties": {
            "cid_text": {
                "type": "string",
                "description": "CID du texte (ex: LEGITEXT000006070721)",
            },
            "date": {
                "type": "string",
                "description": "Date de référence au format YYYY-MM-DD",
            },
            "cid_section": {
                "type": "string",
                "description": "CID de la section (optionnel)",
            },
        },
        "required": ["cid_text", "date"],
    },
)
def legifrance_version_proche(cid_text: str, date: str, cid_section: Optional[str] = None) -> str:
    c    = _get_client()
    body = {"cidText": cid_text, "date": date}
    if cid_section:
        body["cidSection"] = cid_section
    data  = c._req("/search/nearestVersion", body=body)
    lines = [f"**Version la plus proche de `{cid_text}` autour du {date}**\n"]
    for k, v in data.items():
        if v:
            lines.append(f"- **{k}** : {v}")
    return "\n".join(lines) if len(lines) > 1 else "Aucune version proche trouvée."


# ===========================================================================
# OUTILS CONSULT — Journal Officiel (JORF) complémentaires
# ===========================================================================

@tool(
    name="legifrance_jo_par_nor",
    description=(
        "Consulte un texte du Journal Officiel par son numéro NOR "
        "(Numéro d'Ordre du Registre, ex: PRMD2117108D). "
        "Retourne le contenu complet du texte publié au JO."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nor": {
                "type": "string",
                "description": "Numéro NOR du texte (ex: PRMD2117108D, JUSB2123813A)",
            },
        },
        "required": ["nor"],
    },
)
def legifrance_jo_par_nor(nor: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/getJoWithNor", body={"nor": nor})
    titre = data.get("titre", data.get("title", nor))
    lines = [f"# {titre}\n"]
    lines.append(f"**NOR** : {nor}")
    date_p = data.get("datePubliTexte", "")
    if date_p:
        lines.append(f"**Publication JO** : {date_p}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:4000]}")
        if len(texte) > 4000:
            lines.append("\n*[Texte tronqué — consultez Légifrance pour le texte intégral]*")
    return "\n".join(lines)


@tool(
    name="legifrance_derniers_jo",
    description=(
        "Récupère les dernières parutions du Journal Officiel. "
        "Retourne la liste des N derniers numéros publiés avec leurs dates et identifiants."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nb": {
                "type": "integer",
                "default": 10,
                "description": "Nombre de JO à récupérer (défaut: 10)",
            },
        },
    },
)
def legifrance_derniers_jo(nb: int = 10) -> str:
    c     = _get_client()
    data  = c._req("/consult/lastNJo", body={"nbElement": nb})
    items = data.get("results", data.get("jos", data.get("journaux", [])))
    if not items:
        return "Aucun Journal Officiel trouvé."
    lines = [f"**{len(items)} dernier(s) Journal(aux) Officiel(s)**\n"]
    for jo in items:
        date_p = jo.get("dateParution", jo.get("date", ""))
        num    = jo.get("numero", jo.get("num", ""))
        rid    = jo.get("id", "")
        label  = f"JO du {date_p}" if date_p else "JO"
        if num:
            label += f" n°{num}"
        lines.append(f"- **{label}**" + (f" — `{rid}`" if rid else ""))
    return "\n".join(lines)


@tool(
    name="legifrance_sommaire_jorf",
    description=(
        "Consulte le sommaire d'un numéro du Journal Officiel (JORF). "
        "Permet de lister les textes publiés dans un JO donné, filtrable par date ou numéro."
    ),
    parameters={
        "type": "object",
        "properties": {
            "date": {
                "type": "string",
                "description": "Date de parution du JO au format YYYY-MM-DD (ex: '2024-01-15')",
            },
            "jorf_id": {
                "type": "string",
                "description": "Identifiant du conteneur JORF (optionnel, ex: JORFCONT000049456397)",
            },
            "recherche": {
                "type": "string",
                "description": "Texte à rechercher dans le sommaire (optionnel)",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_sommaire_jorf(
    date: Optional[str] = None,
    jorf_id: Optional[str] = None,
    recherche: Optional[str] = None,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"pageNumber": 1, "pageSize": nb_resultats}
    if jorf_id:
        body["id"] = jorf_id
    if date:
        body["date"] = date
    if recherche:
        body["searchText"] = recherche
    data  = c._req("/consult/jorfCont", body=body)
    items = data.get("results", data.get("textes", []))
    label = date or jorf_id or "JO"
    if not items:
        return f"Aucun texte trouvé dans le sommaire du {label}."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} texte(s) au JO du {label}** — {len(items)} affiché(s)\n"]
    for t in items:
        titre  = t.get("titre", t.get("title", "Sans titre"))
        nature = t.get("nature", "")
        rid    = t.get("id", t.get("cid", ""))
        lines.append(f"- **{titre}**" + (f" ({nature})" if nature else "") + (f" — `{rid}`" if rid else ""))
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Conventions collectives (KALI)
# ===========================================================================

@tool(
    name="legifrance_convention_par_idcc",
    description=(
        "Consulte le conteneur (structure principale) d'une convention collective "
        "par son numéro IDCC. Retourne la structure et les métadonnées de la convention."
    ),
    parameters={
        "type": "object",
        "properties": {
            "idcc": {
                "type": "string",
                "description": "Numéro IDCC de la convention collective (ex: '0016', '1486', '3248')",
            },
        },
        "required": ["idcc"],
    },
)
def legifrance_convention_par_idcc(idcc: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/kaliContIdcc", body={"id": idcc})
    titre = data.get("titre", data.get("title", f"Convention IDCC {idcc}"))
    lines = [f"# {titre}\n", f"**IDCC** : {idcc}"]
    rid   = data.get("id", "")
    if rid:
        lines.append(f"**ID** : `{rid}`")
    etat  = data.get("etat", data.get("state", ""))
    if etat:
        lines.append(f"**État** : {etat}")
    date_debut = data.get("dateDebut", "")
    if date_debut:
        lines.append(f"**En vigueur depuis** : {date_debut}")
    sections = data.get("sections", data.get("articles", []))
    if sections:
        lines.append(f"\n**{len(sections)} section(s)/article(s)**")
        for s in sections[:20]:
            t = s.get("titre", s.get("title", s.get("num", "")))
            if t:
                lines.append(f"  - {t}")
        if len(sections) > 20:
            lines.append(f"  *… {len(sections)-20} élément(s) supplémentaires*")
    return "\n".join(lines)


@tool(
    name="legifrance_convention_texte",
    description=(
        "Consulte le texte complet d'une convention collective par son identifiant KALI "
        "(format KALITEXTXXXXXXXXX). Retourne le contenu structuré de la convention."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_id": {
                "type": "string",
                "description": "Identifiant KALI du texte (ex: KALITEXT000005635374)",
            },
        },
        "required": ["text_id"],
    },
)
def legifrance_convention_texte(text_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/kaliText", body={"id": text_id})
    titre = data.get("titre", data.get("title", text_id))
    lines = [f"# {titre}\n"]
    idcc  = data.get("idcc", "")
    if idcc:
        lines.append(f"**IDCC** : {idcc}")
    etat = data.get("etat", "")
    if etat:
        lines.append(f"**État** : {etat}")
    articles = data.get("articles", data.get("sections", []))
    if articles:
        lines.append(f"\n**{len(articles)} article(s)/section(s)**\n")
        for a in articles[:30]:
            lines.append(_fmt_article(a))
            lines.append("")
        if len(articles) > 30:
            lines.append(f"*… {len(articles)-30} élément(s) supplémentaire(s) non affiché(s)*")
    return "\n".join(lines)


@tool(
    name="legifrance_convention_article",
    description=(
        "Consulte un article spécifique d'une convention collective par son identifiant "
        "(format KALIARTXXXXXXXXX). Retourne le texte complet de l'article."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_id": {
                "type": "string",
                "description": "Identifiant de l'article KALI (ex: KALIARTI000005635375)",
            },
        },
        "required": ["article_id"],
    },
)
def legifrance_convention_article(article_id: str) -> str:
    c    = _get_client()
    data = c._req("/consult/kaliArticle", body={"id": article_id})
    return _fmt_article(data)


@tool(
    name="legifrance_convention_section",
    description=(
        "Consulte une section d'une convention collective par son identifiant "
        "(format KALISECTXXXXXXXXX). Retourne le contenu de la section."
    ),
    parameters={
        "type": "object",
        "properties": {
            "section_id": {
                "type": "string",
                "description": "Identifiant de la section KALI (ex: KALISECT000005635376)",
            },
        },
        "required": ["section_id"],
    },
)
def legifrance_convention_section(section_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/kaliSection", body={"id": section_id})
    titre = data.get("titre", data.get("title", section_id))
    lines = [f"**Section : {titre}**\n"]
    articles = data.get("articles", [])
    if articles:
        lines.append(f"**{len(articles)} article(s)**\n")
        for a in articles:
            lines.append(_fmt_article(a))
            lines.append("")
    else:
        texte = _strip_html(data.get("texte", data.get("content", "")))
        if texte:
            lines.append(texte)
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Jurisprudence complémentaire
# ===========================================================================

@tool(
    name="legifrance_jurisprudence_plan_classement",
    description=(
        "Consulte le plan de classement de la jurisprudence (arborescence thématique). "
        "Permet de naviguer dans les catégories de jurisprudence par thème ou matière."
    ),
    parameters={
        "type": "object",
        "properties": {
            "libelle": {
                "type": "string",
                "description": "Libellé à rechercher dans le plan de classement (ex: 'contrat', 'responsabilité')",
            },
            "fond": {
                "type": "string",
                "description": "Fond juridictionnel (optionnel, ex: 'juri', 'CASS', 'CE')",
            },
            "niveau": {
                "type": "integer",
                "description": "Niveau hiérarchique (optionnel, 1=racine)",
            },
        },
    },
)
def legifrance_jurisprudence_plan_classement(
    libelle: Optional[str] = None,
    fond: Optional[str] = None,
    niveau: Optional[int] = None,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {}
    if libelle:
        body["libelle"] = libelle
    if fond:
        body["fond"] = fond
    if niveau is not None:
        body["niveau"] = niveau
    data  = c._req("/consult/getJuriPlanClassement", body=body)
    items = data.get("results", data.get("items", []))
    if not items:
        return "Aucune entrée de plan de classement trouvée."
    lines = [f"**Plan de classement jurisprudence**\n"]
    for item in items[:30]:
        libelle_item = item.get("libelle", item.get("title", ""))
        rid          = item.get("id", "")
        nb           = item.get("nbDocuments", "")
        line         = f"- **{libelle_item}**"
        if nb:
            line += f" ({nb} décision(s))"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    if len(items) > 30:
        lines.append(f"\n*… {len(items)-30} entrée(s) supplémentaire(s)*")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Divers (CNIL, accords, circulaires, débats, dossiers)
# ===========================================================================

@tool(
    name="legifrance_cnil",
    description=(
        "Consulte une délibération ou une décision de la CNIL (Commission Nationale de l'Informatique "
        "et des Libertés) par son identifiant. Retourne le texte complet de la décision."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_id": {
                "type": "string",
                "description": "Identifiant du texte CNIL (ex: CNILTEXT000017651305)",
            },
        },
        "required": ["text_id"],
    },
)
def legifrance_cnil(text_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/cnil", body={"textId": text_id})
    titre = data.get("titre", data.get("title", text_id))
    lines = [f"# {titre}\n"]
    date_d = data.get("dateDecision", data.get("date", ""))
    if date_d:
        lines.append(f"**Date** : {date_d}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:5000]}")
        if len(texte) > 5000:
            lines.append("\n*[Texte tronqué]*")
    return "\n".join(lines)


@tool(
    name="legifrance_acco",
    description=(
        "Consulte un accord d'entreprise (fonds ACCO) par son identifiant. "
        "Les accords d'entreprise sont des conventions signées entre employeurs et représentants du personnel."
    ),
    parameters={
        "type": "object",
        "properties": {
            "acco_id": {
                "type": "string",
                "description": "Identifiant de l'accord d'entreprise",
            },
        },
        "required": ["acco_id"],
    },
)
def legifrance_acco(acco_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/acco", body={"id": acco_id})
    titre = data.get("titre", data.get("title", acco_id))
    lines = [f"# {titre}\n"]
    siret = data.get("siret", "")
    rs    = data.get("raisonSociale", data.get("entreprise", ""))
    if siret:
        lines.append(f"**SIRET** : {siret}")
    if rs:
        lines.append(f"**Entreprise** : {rs}")
    date_d = data.get("dateDepot", data.get("date", ""))
    if date_d:
        lines.append(f"**Date de dépôt** : {date_d}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:4000]}")
        if len(texte) > 4000:
            lines.append("\n*[Texte tronqué]*")
    return "\n".join(lines)


@tool(
    name="legifrance_circulaire",
    description=(
        "Consulte une circulaire administrative (fonds CIRC) par son identifiant. "
        "Retourne le contenu de la circulaire avec ses métadonnées."
    ),
    parameters={
        "type": "object",
        "properties": {
            "circulaire_id": {
                "type": "string",
                "description": "Identifiant de la circulaire",
            },
        },
        "required": ["circulaire_id"],
    },
)
def legifrance_circulaire(circulaire_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/circulaire", body={"id": circulaire_id})
    titre = data.get("titre", data.get("title", circulaire_id))
    lines = [f"# {titre}\n"]
    nor   = data.get("nor", "")
    if nor:
        lines.append(f"**NOR** : {nor}")
    date_p = data.get("datePubliTexte", data.get("date", ""))
    if date_p:
        lines.append(f"**Publication** : {date_p}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:4000]}")
        if len(texte) > 4000:
            lines.append("\n*[Texte tronqué]*")
    return "\n".join(lines)


@tool(
    name="legifrance_debat",
    description=(
        "Consulte le compte-rendu d'un débat parlementaire par son identifiant. "
        "Couvre les séances de l'Assemblée Nationale et du Sénat."
    ),
    parameters={
        "type": "object",
        "properties": {
            "debat_id": {
                "type": "string",
                "description": "Identifiant du débat parlementaire",
            },
        },
        "required": ["debat_id"],
    },
)
def legifrance_debat(debat_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/debat", body={"id": debat_id})
    titre = data.get("titre", data.get("title", debat_id))
    lines = [f"# {titre}\n"]
    jorf  = data.get("dateSeance", data.get("date", ""))
    if jorf:
        lines.append(f"**Séance du** : {jorf}")
    parlement = data.get("typeParlement", data.get("parlement", ""))
    if parlement:
        lines.append(f"**Chambre** : {parlement}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:5000]}")
        if len(texte) > 5000:
            lines.append("\n*[Texte tronqué — consultez Légifrance pour le texte intégral]*")
    return "\n".join(lines)


@tool(
    name="legifrance_dossier_legislatif",
    description=(
        "Consulte un dossier législatif complet par son identifiant. "
        "Un dossier législatif regroupe tous les documents liés à l'élaboration d'une loi : "
        "projets, amendements, rapports, textes adoptés."
    ),
    parameters={
        "type": "object",
        "properties": {
            "dossier_id": {
                "type": "string",
                "description": "Identifiant du dossier législatif",
            },
        },
        "required": ["dossier_id"],
    },
)
def legifrance_dossier_legislatif(dossier_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/dossierLegislatif", body={"id": dossier_id})
    titre = data.get("titre", data.get("title", dossier_id))
    lines = [f"# {titre}\n"]
    etat  = data.get("etat", data.get("statut", ""))
    if etat:
        lines.append(f"**État** : {etat}")
    legislature = data.get("legislature", "")
    if legislature:
        lines.append(f"**Législature** : {legislature}")
    etapes = data.get("etapes", data.get("phases", []))
    if etapes:
        lines.append(f"\n**{len(etapes)} étape(s) législative(s)**")
        for e in etapes[:10]:
            label = e.get("libelle", e.get("titre", e.get("type", "")))
            date_e = e.get("date", "")
            if label:
                lines.append(f"  - {label}" + (f" ({date_e})" if date_e else ""))
    return "\n".join(lines)


@tool(
    name="legifrance_section_par_cid",
    description=(
        "Récupère le contenu d'une section de code ou de texte par son CID canonique "
        "(format LEGISCTA...). Utile pour naviguer dans la structure d'un code."
    ),
    parameters={
        "type": "object",
        "properties": {
            "cid": {
                "type": "string",
                "description": "CID de la section (ex: LEGISCTA000006150321)",
            },
        },
        "required": ["cid"],
    },
)
def legifrance_section_par_cid(cid: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/getSectionByCid", body={"cid": cid})
    titre = data.get("titre", data.get("title", cid))
    lines = [f"**Section : {titre}**\n"]
    articles = data.get("articles", data.get("sections", []))
    if articles:
        lines.append(f"**{len(articles)} article(s)**\n")
        for a in articles[:20]:
            lines.append(_fmt_article(a))
            lines.append("")
        if len(articles) > 20:
            lines.append(f"*… {len(articles)-20} article(s) supplémentaire(s)*")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CHRONO — Historique des versions de textes
# ===========================================================================

@tool(
    name="legifrance_historique_texte",
    description=(
        "Récupère l'historique complet des versions d'un texte juridique sur une période donnée. "
        "Permet de suivre l'évolution législative d'un code ou d'une loi dans le temps."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_cid": {
                "type": "string",
                "description": "CID chronologique du texte (ex: LEGITEXT000006070721 pour le Code civil)",
            },
            "annee_debut": {
                "type": "integer",
                "description": "Année de début de la période détaillée (ex: 2015)",
            },
            "annee_fin": {
                "type": "integer",
                "description": "Année de fin de la période détaillée (ex: 2024)",
            },
            "date_consult": {
                "type": "string",
                "description": "Date de référence au format YYYY-MM-DD (défaut: aujourd'hui)",
            },
        },
        "required": ["text_cid", "annee_debut", "annee_fin"],
    },
)
def legifrance_historique_texte(
    text_cid: str,
    annee_debut: int,
    annee_fin: int,
    date_consult: Optional[str] = None,
) -> str:
    c = _get_client()
    if date_consult is None:
        date_consult = globals()["date"].today().isoformat()
    data     = c._req("/chrono/textCid", body={
        "textCid":     text_cid,
        "dateConsult": date_consult,
        "startYear":   annee_debut,
        "endYear":     annee_fin,
    })
    versions = data.get("versions", data.get("chronolegi", []))
    if not versions:
        return f"Aucune version trouvée pour `{text_cid}` entre {annee_debut} et {annee_fin}."
    lines = [f"**{len(versions)} version(s) de `{text_cid}` ({annee_debut}–{annee_fin})**\n"]
    for v in versions:
        debut = v.get("dateDebut", v.get("startDate", ""))
        fin   = v.get("dateFin",   v.get("endDate", "en cours"))
        rid   = v.get("id",        "")
        etat  = v.get("etat",      "")
        line  = f"- **{debut}** → {fin}"
        if etat:
            line += f" ({etat})"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_versions_element",
    description=(
        "Récupère toutes les versions chronologiques d'un article ou d'une section "
        "au sein d'un texte donné. Permet de voir toutes les modifications d'un article."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_cid": {
                "type": "string",
                "description": "CID du texte contenant l'élément (ex: LEGITEXT000006070721)",
            },
            "element_cid": {
                "type": "string",
                "description": "CID de l'article ou de la section (ex: LEGIARTI000006436298)",
            },
        },
        "required": ["text_cid", "element_cid"],
    },
)
def legifrance_versions_element(text_cid: str, element_cid: str) -> str:
    c        = _get_client()
    data     = c._req("/chrono/textCidAndElementCid", body={
        "textCid":    text_cid,
        "elementCid": element_cid,
    })
    versions = data.get("versions", data.get("chronolegi", []))
    if not versions:
        return f"Aucune version trouvée pour l'élément `{element_cid}`."
    lines = [f"**{len(versions)} version(s) de l'élément `{element_cid}`**\n"]
    for v in versions:
        debut = v.get("dateDebut", v.get("startDate", ""))
        fin   = v.get("dateFin",   v.get("endDate", "en cours"))
        rid   = v.get("id", "")
        etat  = v.get("etat", "")
        line  = f"- **{debut}** → {fin}"
        if etat:
            line += f" ({etat})"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_a_des_versions",
    description=(
        "Vérifie rapidement si un texte juridique possède des versions historiques "
        "sans charger toutes les données. Utile avant d'appeler legifrance_historique_texte."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_cid": {
                "type": "string",
                "description": "CID du texte (ex: LEGITEXT000006070721)",
            },
        },
        "required": ["text_cid"],
    },
)
def legifrance_a_des_versions(text_cid: str) -> str:
    c    = _get_client()
    data = c._req(f"/chrono/textCid/{text_cid}", method="GET")
    has  = data.get("hasChronolegi", data.get("hasVersions", False))
    if has:
        return f"✅ Le texte `{text_cid}` **possède** un historique de versions. Utilisez `legifrance_historique_texte` pour les récupérer."
    return f"ℹ️ Le texte `{text_cid}` **ne possède pas** de versions historiques enregistrées."


# ===========================================================================
# OUTILS LIST — Listages complémentaires
# ===========================================================================

@tool(
    name="legifrance_lister_loda",
    description=(
        "Liste les lois, ordonnances et décrets autonomes disponibles dans Légifrance (fonds LODA). "
        "Filtrable par nature (LOI, ORDONNANCE, DECRET…) et état juridique."
    ),
    parameters={
        "type": "object",
        "properties": {
            "natures": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Natures à filtrer (ex: ['LOI', 'ORDONNANCE', 'DECRET', 'ARRETE'])",
            },
            "en_vigueur_seulement": {
                "type": "boolean",
                "default": True,
                "description": "Retourner uniquement les textes en vigueur (défaut: true)",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_lister_loda(
    natures: Optional[List[str]] = None,
    en_vigueur_seulement: bool = True,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"pageNumber": 1, "pageSize": nb_resultats}
    if natures:
        body["natures"] = natures
    if en_vigueur_seulement:
        body["legalStatus"] = ["VIGUEUR"]
    data  = c._req("/list/loda", body=body)
    items = data.get("results", data.get("textes", []))
    if not items:
        return "Aucun texte LODA trouvé."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} texte(s) LODA** — {len(items)} affiché(s)\n"]
    for t in items:
        titre  = t.get("titre", t.get("title", ""))
        nature = t.get("nature", "")
        rid    = t.get("id", t.get("cid", ""))
        date_p = t.get("datePubliTexte", "")
        line   = f"- **{titre}**"
        if nature:
            line += f" ({nature})"
        if date_p:
            line += f" — {date_p}"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_lister_legislatures",
    description=(
        "Liste toutes les législatures disponibles dans Légifrance. "
        "Retourne les identifiants nécessaires pour lister les dossiers législatifs."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def legifrance_lister_legislatures() -> str:
    c     = _get_client()
    data  = c._req("/list/legislatures", body={})
    items = data.get("results", data.get("legislatures", []))
    if not items:
        return "Aucune législature trouvée."
    lines = [f"**{len(items)} législature(s)**\n"]
    for leg in items:
        num   = leg.get("numero", leg.get("num", leg.get("id", "")))
        debut = leg.get("dateDebut", leg.get("startDate", ""))
        fin   = leg.get("dateFin",   leg.get("endDate", "en cours"))
        rid   = leg.get("id", "")
        line  = f"- **Législature {num}**"
        if debut:
            line += f" : {debut} → {fin}"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_lister_dossiers_legislatifs",
    description=(
        "Liste les dossiers législatifs d'une législature donnée. "
        "Utilisez legifrance_lister_legislatures pour obtenir l'ID de législature."
    ),
    parameters={
        "type": "object",
        "properties": {
            "legislature_id": {
                "type": "integer",
                "description": "Numéro/identifiant de la législature (ex: 16 pour la XVIe législature)",
            },
            "type_dossier": {
                "type": "string",
                "description": "Type de dossier (ex: 'LOI_PUBLIEE', 'EN_COURS', 'LOI_ORDINAIRE')",
                "default": "LOI_PUBLIEE",
            },
        },
        "required": ["legislature_id"],
    },
)
def legifrance_lister_dossiers_legislatifs(
    legislature_id: int,
    type_dossier: str = "LOI_PUBLIEE",
) -> str:
    c     = _get_client()
    data  = c._req("/list/dossiersLegislatifs", body={
        "legislatureId": legislature_id,
        "type":          type_dossier,
    })
    items = data.get("results", data.get("dossiers", []))
    if not items:
        return f"Aucun dossier législatif trouvé pour la législature {legislature_id} (type: {type_dossier})."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} dossier(s)** — législature {legislature_id} / {type_dossier} — {len(items)} affiché(s)\n"]
    for d in items:
        titre = d.get("titre", d.get("title", "Sans titre"))
        rid   = d.get("id", "")
        etat  = d.get("etat", "")
        line  = f"- **{titre}**"
        if etat:
            line += f" ({etat})"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_lister_debats_parlementaires",
    description=(
        "Liste les débats parlementaires disponibles dans Légifrance. "
        "Couvre les comptes-rendus de l'Assemblée Nationale (AN) et du Sénat."
    ),
    parameters={
        "type": "object",
        "properties": {
            "types_publication": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Types de publication (ex: ['AN'] pour Assemblée Nationale, ['SENAT'] pour Sénat)",
            },
            "date_parution": {
                "type": "string",
                "description": "Date de parution au format YYYY-MM-DD (optionnel)",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_lister_debats_parlementaires(
    types_publication: Optional[List[str]] = None,
    date_parution: Optional[str] = None,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"pageNumber": 1, "pageSize": nb_resultats}
    if types_publication:
        body["typesPublication"] = types_publication
    if date_parution:
        body["dateParution"] = date_parution
    data  = c._req("/list/debatsParlementaires", body=body)
    items = data.get("results", data.get("debats", []))
    if not items:
        return "Aucun débat parlementaire trouvé."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} débat(s)** — {len(items)} affiché(s)\n"]
    for d in items:
        titre = d.get("titre", d.get("title", "Sans titre"))
        date_s = d.get("dateSeance", d.get("dateParution", d.get("date", "")))
        chambre = d.get("typeParlement", d.get("parlement", ""))
        rid    = d.get("id", "")
        line   = f"- **{titre}**"
        if chambre:
            line += f" ({chambre})"
        if date_s:
            line += f" — {date_s}"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_lister_questions_parlementaires",
    description=(
        "Liste les questions écrites parlementaires (questions de députés ou sénateurs "
        "aux ministres) disponibles dans Légifrance."
    ),
    parameters={
        "type": "object",
        "properties": {
            "parlement_types": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Types de parlement (ex: ['AN'] pour Assemblée Nationale, ['SENAT'])",
            },
            "periode_publication": {
                "type": "string",
                "description": "Période de publication (optionnel, ex: '01/01/2024 > 31/12/2024')",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_lister_questions_parlementaires(
    parlement_types: Optional[List[str]] = None,
    periode_publication: Optional[str] = None,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"pageNumber": 1, "pageSize": nb_resultats}
    if parlement_types:
        body["parlementTypes"] = parlement_types
    if periode_publication:
        body["periodePublication"] = periode_publication
    data  = c._req("/list/questionsEcritesParlementaires", body=body)
    items = data.get("results", data.get("questions", []))
    if not items:
        return "Aucune question parlementaire trouvée."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} question(s) parlementaire(s)** — {len(items)} affiché(e)(s)\n"]
    for q in items:
        titre   = q.get("titre", q.get("title", "Sans titre"))
        auteur  = q.get("auteur", q.get("depute", q.get("senateur", "")))
        date_p  = q.get("datePubliTexte", q.get("date", ""))
        chambre = q.get("typeParlement", "")
        rid     = q.get("id", "")
        line    = f"- **{titre}**"
        if auteur:
            line += f" — par {auteur}"
        if chambre:
            line += f" ({chambre})"
        if date_p:
            line += f" — {date_p}"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_lister_bocc",
    description=(
        "Liste les Bulletins Officiels des Conventions Collectives (BOCC). "
        "Le BOCC publie les textes des accords collectifs et avenants."
    ),
    parameters={
        "type": "object",
        "properties": {
            "interval_publication": {
                "type": "string",
                "description": "Intervalle de publication (ex: '01/01/2024 > 31/03/2024')",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_lister_bocc(
    interval_publication: Optional[str] = None,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"pageNumber": 1, "pageSize": nb_resultats}
    if interval_publication:
        body["intervalPublication"] = interval_publication
    data  = c._req("/list/bocc", body=body)
    items = data.get("results", data.get("boccs", []))
    if not items:
        return "Aucun BOCC trouvé."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} BOCC** — {len(items)} affiché(s)\n"]
    for b in items:
        num   = b.get("numero", b.get("num", ""))
        date_p = b.get("datePublication", b.get("date", ""))
        rid   = b.get("id", "")
        line  = f"- **BOCC {num}**"
        if date_p:
            line += f" — {date_p}"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_lister_bocc_textes",
    description=(
        "Liste les textes d'un numéro de BOCC donné. "
        "Filtrable par IDCC pour voir les accords d'une convention collective spécifique."
    ),
    parameters={
        "type": "object",
        "properties": {
            "bocc_id": {
                "type": "string",
                "description": "Identifiant du BOCC principal",
            },
            "idccs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Liste d'IDCC pour filtrer (ex: ['0016', '1486'])",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_lister_bocc_textes(
    bocc_id: Optional[str] = None,
    idccs: Optional[List[str]] = None,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"pageNumber": 1, "pageSize": nb_resultats}
    if bocc_id:
        body["idMainBocc"] = bocc_id
    if idccs:
        body["idccs"] = idccs
    data  = c._req("/list/boccTexts", body=body)
    items = data.get("results", data.get("textes", []))
    if not items:
        return "Aucun texte BOCC trouvé."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} texte(s) BOCC** — {len(items)} affiché(s)\n"]
    for t in items:
        titre = t.get("titre", t.get("title", "Sans titre"))
        idcc  = t.get("idcc", "")
        rid   = t.get("id", "")
        line  = f"- **{titre}**"
        if idcc:
            line += f" (IDCC {idcc})"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_lister_boccs_et_textes",
    description=(
        "Recherche combinée dans les BOCCs et leurs textes associés. "
        "Filtrable par titre de convention ou par numéro IDCC."
    ),
    parameters={
        "type": "object",
        "properties": {
            "idcc": {
                "type": "string",
                "description": "Numéro IDCC (ex: '0016')",
            },
            "titre": {
                "type": "string",
                "description": "Texte à rechercher dans les titres",
            },
            "interval_publication": {
                "type": "string",
                "description": "Intervalle de publication (ex: '01/01/2024 > 31/12/2024')",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_lister_boccs_et_textes(
    idcc: Optional[str] = None,
    titre: Optional[str] = None,
    interval_publication: Optional[str] = None,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"pageNumber": 1, "pageSize": nb_resultats}
    if idcc:
        body["idcc"] = idcc
    if titre:
        body["titre"] = titre
    if interval_publication:
        body["intervalPublication"] = interval_publication
    data  = c._req("/list/boccsAndTexts", body=body)
    items = data.get("results", data.get("textes", []))
    if not items:
        return "Aucun résultat BOCC/texte trouvé."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} résultat(s)** — {len(items)} affiché(s)\n"]
    for t in items:
        titre_item = t.get("titre", t.get("title", "Sans titre"))
        idcc_item  = t.get("idcc", "")
        date_p     = t.get("datePublication", t.get("date", ""))
        rid        = t.get("id", "")
        line       = f"- **{titre_item}**"
        if idcc_item:
            line += f" (IDCC {idcc_item})"
        if date_p:
            line += f" — {date_p}"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_lister_docs_admins",
    description=(
        "Liste les documents administratifs disponibles dans Légifrance pour une ou plusieurs années. "
        "Retourne les bulletins officiels et documents administratifs publiés."
    ),
    parameters={
        "type": "object",
        "properties": {
            "annees": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Liste d'années à rechercher (ex: [2023, 2024])",
            },
        },
    },
)
def legifrance_lister_docs_admins(annees: Optional[List[int]] = None) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {}
    if annees:
        body["years"] = annees
    data  = c._req("/list/docsAdmins", body=body)
    items = data.get("results", data.get("documents", []))
    if not items:
        return "Aucun document administratif trouvé."
    lines = [f"**{len(items)} document(s) administratif(s)**\n"]
    for d in items:
        titre = d.get("titre", d.get("title", "Sans titre"))
        annee = d.get("annee", d.get("year", ""))
        rid   = d.get("id", "")
        line  = f"- **{titre}**"
        if annee:
            line += f" ({annee})"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


# ===========================================================================
# OUTILS SUGGEST — Suggestions complémentaires
# ===========================================================================

@tool(
    name="legifrance_suggerer_acco",
    description=(
        "Suggestions de SIRET et raisons sociales pour les accords d'entreprise. "
        "Utile pour identifier une entreprise avant de rechercher ses accords."
    ),
    parameters={
        "type": "object",
        "properties": {
            "texte": {
                "type": "string",
                "description": "Début de la raison sociale ou numéro SIRET (ex: 'Renault', 'Airbus', '351')",
            },
        },
        "required": ["texte"],
    },
)
def legifrance_suggerer_acco(texte: str) -> str:
    c    = _get_client()
    data = c._req("/suggest/acco", body={"searchText": texte})
    suggestions = data.get("suggestions", data.get("results", []))
    if not suggestions:
        return f"Aucune suggestion entreprise pour : « {texte} »"
    lines = [f"**Entreprises suggérées pour « {texte} »**\n"]
    for s in suggestions[:15]:
        rs    = s.get("raisonSociale", s.get("title", s.get("text", str(s))))
        siret = s.get("siret", "")
        lines.append(f"- **{rs}**" + (f" (SIRET : {siret})" if siret else ""))
    return "\n".join(lines)


@tool(
    name="legifrance_suggerer_pdc",
    description=(
        "Suggestions de libellés pour le plan de classement (PDC) de Légifrance. "
        "Utile pour naviguer dans l'arborescence thématique avant une recherche avancée."
    ),
    parameters={
        "type": "object",
        "properties": {
            "texte": {
                "type": "string",
                "description": "Terme à compléter dans le plan de classement (ex: 'contrat de travail', 'bail')",
            },
            "fond": {
                "type": "string",
                "description": "Fond à interroger (optionnel, ex: 'JURI', 'LODA')",
            },
        },
        "required": ["texte"],
    },
)
def legifrance_suggerer_pdc(texte: str, fond: Optional[str] = None) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"searchText": texte}
    if fond:
        body["fond"] = fond
    data = c._req("/suggest/pdc", body=body)
    suggestions = data.get("suggestions", data.get("results", []))
    if not suggestions:
        return f"Aucune suggestion de plan de classement pour : « {texte} »"
    lines = [f"**Plan de classement — suggestions pour « {texte} »**\n"]
    for s in suggestions[:15]:
        libelle = s.get("libelle", s.get("title", s.get("text", str(s))))
        rid     = s.get("id", "")
        lines.append(f"- {libelle}" + (f" (`{rid}`)" if rid else ""))
    return "\n".join(lines)


# ===========================================================================
# OUTILS MISC — Services utilitaires
# ===========================================================================

@tool(
    name="legifrance_dates_sans_jo",
    description=(
        "Retourne la liste des dates où aucun Journal Officiel n'a été publié. "
        "Utile pour vérifier si une date particulière est un jour de parution du JO."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def legifrance_dates_sans_jo() -> str:
    c     = _get_client()
    data  = c._req("/misc/datesWithoutJo", method="GET")
    dates = data.get("dates", data.get("results", []))
    if not dates:
        return "Aucune date sans JO trouvée (ou liste indisponible)."
    lines = [f"**{len(dates)} date(s) sans Journal Officiel**\n"]
    for d in dates[:50]:
        if isinstance(d, str):
            lines.append(f"- {d}")
        elif isinstance(d, dict):
            lines.append(f"- {d.get('date', str(d))}")
    if len(dates) > 50:
        lines.append(f"\n*… {len(dates)-50} date(s) supplémentaire(s)*")
    return "\n".join(lines)


@tool(
    name="legifrance_annees_sans_table",
    description=(
        "Retourne la liste des années pour lesquelles aucune table annuelle du JO n'est disponible. "
        "La table annuelle recense tous les textes publiés au JO pour une année donnée."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def legifrance_annees_sans_table() -> str:
    c      = _get_client()
    data   = c._req("/misc/yearsWithoutTable", method="GET")
    annees = data.get("years", data.get("results", data.get("annees", [])))
    if not annees:
        return "Aucune année sans table trouvée (ou liste indisponible)."
    lines = [f"**{len(annees)} année(s) sans table annuelle du JO**\n"]
    for a in annees:
        lines.append(f"- {a}")
    return "\n".join(lines)


# ===========================================================================
# OUTILS MISC — Versioning
# ===========================================================================

@tool(
    name="legifrance_commit_id",
    description=(
        "Retourne les informations de déploiement et de versioning de l'API Légifrance. "
        "Utile pour connaître la version exacte de l'API en cours d'utilisation."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)
def legifrance_commit_id() -> str:
    c    = _get_client()
    data = c._req("/misc/commitId", method="GET")
    if not data:
        return "Informations de version indisponibles."
    lines = ["**Informations de version de l'API Légifrance**\n"]
    for k, v in data.items():
        if v:
            lines.append(f"- **{k}** : {v}")
    return "\n".join(lines) if len(lines) > 1 else "Aucune information de version disponible."


# ===========================================================================
# OUTILS LIST — BODMR
# ===========================================================================

@tool(
    name="legifrance_lister_bodmr",
    description=(
        "Liste les Bulletins Officiels des Décorations, Médailles et Récompenses (BODMR). "
        "Filtrable par années et triable."
    ),
    parameters={
        "type": "object",
        "properties": {
            "annees": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Années à filtrer (optionnel, ex: [2023, 2024])",
            },
            "nb_resultats": {
                "type": "integer",
                "default": 20,
                "description": "Nombre de résultats (défaut: 20)",
            },
        },
    },
)
def legifrance_lister_bodmr(
    annees: Optional[List[int]] = None,
    nb_resultats: int = 20,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"pageNumber": 1, "pageSize": nb_resultats}
    if annees:
        body["years"] = annees
    data  = c._req("/list/bodmr", body=body)
    items = data.get("results", data.get("bodmrs", []))
    if not items:
        return "Aucun BODMR trouvé."
    total = data.get("totalResultNumber", len(items))
    lines = [f"**{total} BODMR** — {len(items)} affiché(s)\n"]
    for b in items:
        num    = b.get("numero", b.get("num", ""))
        date_p = b.get("datePublication", b.get("date", ""))
        rid    = b.get("id", "")
        line   = f"- **BODMR {num}**"
        if date_p:
            line += f" — {date_p}"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Codes (compléments)
# ===========================================================================

@tool(
    name="legifrance_code_complet",
    description=(
        "Récupère le contenu complet d'un code juridique (articles inclus) à une date donnée. "
        "Contrairement à legifrance_consulter_code qui retourne uniquement la table des matières, "
        "cet outil retourne le texte intégral avec les articles. "
        "Attention : les codes volumineux peuvent retourner un résultat tronqué."
    ),
    parameters={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": (
                    "Nom du code (civil, penal, travail, commerce…) "
                    "ou directement un ID Légifrance (LEGITEXT...)."
                ),
            },
            "date": {
                "type": "string",
                "description": "Date de consultation YYYY-MM-DD (défaut: aujourd'hui)",
            },
        },
        "required": ["code"],
    },
)
def legifrance_code_complet(code: str, date: Optional[str] = None) -> str:
    c = _get_client()
    try:
        tid = c.resolve_code(code)
    except ValueError as e:
        return str(e)
    data    = c._req("/consult/code", body={
        "textId": tid,
        "date":   date or globals()["date"].today().isoformat(),
    })
    titre   = data.get("titre", data.get("title", code))
    lines   = [f"# {titre}\n"]
    articles = data.get("articles", data.get("sections", []))
    if articles:
        lines.append(f"**{len(articles)} article(s)/section(s)**\n")
        for a in articles[:30]:
            lines.append(_fmt_article(a))
            lines.append("")
        if len(articles) > 30:
            lines.append(f"*… {len(articles)-30} élément(s) supplémentaire(s) — utilisez legifrance_obtenir_article pour accéder aux articles individuels*")
    else:
        lines.append("*(contenu non disponible — utilisez legifrance_consulter_code pour la table des matières)*")
    return "\n".join(lines)


@tool(
    name="legifrance_code_par_ancien_id",
    description=(
        "Récupère le contenu d'un code juridique par son ancien identifiant Légifrance. "
        "Utile pour accéder à des codes référencés avec des identifiants obsolètes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "ancien_id": {
                "type": "string",
                "description": "Ancien identifiant du code",
            },
        },
        "required": ["ancien_id"],
    },
)
def legifrance_code_par_ancien_id(ancien_id: str) -> str:
    c    = _get_client()
    data = c._req("/consult/getCodeWithAncienId", body={"ancienId": ancien_id})
    return _fmt_toc(data, ancien_id)


@tool(
    name="legifrance_article_par_eli",
    description=(
        "Récupère un article juridique par son identifiant ELI (European Legislation Identifier) "
        "ou son alias. "
        "Exemple d'ELI : '/eli/decret/2021/7/13/PRMD2117108D/jo/article_1'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "id_eli_ou_alias": {
                "type": "string",
                "description": "Identifiant ELI ou alias de l'article",
            },
        },
        "required": ["id_eli_ou_alias"],
    },
)
def legifrance_article_par_eli(id_eli_ou_alias: str) -> str:
    c    = _get_client()
    data = c._req("/consult/getArticleWithIdEliOrAlias", body={"idEliOrAlias": id_eli_ou_alias})
    return _fmt_article(data)


@tool(
    name="legifrance_articles_meme_numero",
    description=(
        "Récupère la liste des articles qui ont eu le même numéro qu'un article donné "
        "au sein d'un texte. Utile pour retracer les renumérotations d'articles."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_cid": {
                "type": "string",
                "description": "CID de l'article de référence",
            },
            "article_num": {
                "type": "string",
                "description": "Numéro de l'article (ex: '1382', 'L1234-5')",
            },
            "text_cid": {
                "type": "string",
                "description": "CID du texte contenant l'article",
            },
            "date": {
                "type": "string",
                "description": "Date de référence au format YYYY-MM-DD",
            },
        },
        "required": ["article_cid", "article_num", "text_cid", "date"],
    },
)
def legifrance_articles_meme_numero(
    article_cid: str,
    article_num: str,
    text_cid: str,
    date: str,
) -> str:
    c    = _get_client()
    data = c._req("/consult/sameNumArticle", body={
        "articleCid": article_cid,
        "articleNum": article_num,
        "textCid":    text_cid,
        "date":       date,
    })
    articles = data.get("articles", data.get("results", []))
    if not articles:
        return f"Aucun autre article avec le numéro '{article_num}' trouvé dans ce texte."
    lines = [f"**{len(articles)} article(s) avec le numéro '{article_num}'**\n"]
    for a in articles:
        lines.append(_fmt_article(a))
        lines.append("")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Liens d'articles
# ===========================================================================

@tool(
    name="legifrance_liens_concordance",
    description=(
        "Récupère les liens de concordance d'un article juridique : "
        "autres textes ou articles qui font référence à cet article ou lui sont liés thématiquement."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_id": {
                "type": "string",
                "description": "Identifiant de l'article (ex: LEGIARTI000006436298)",
            },
        },
        "required": ["article_id"],
    },
)
def legifrance_liens_concordance(article_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/concordanceLinksArticle", body={"articleId": article_id})
    liens = data.get("links", data.get("concordances", data.get("results", [])))
    if not liens:
        return f"Aucun lien de concordance trouvé pour l'article `{article_id}`."
    lines = [f"**{len(liens)} lien(s) de concordance pour `{article_id}`**\n"]
    for l in liens:
        titre = l.get("titre", l.get("title", l.get("text", "")))
        rid   = l.get("id", "")
        lines.append(f"- {titre}" + (f" — `{rid}`" if rid else ""))
    return "\n".join(lines)


@tool(
    name="legifrance_liens_relatifs",
    description=(
        "Récupère les liens relatifs d'un article juridique : "
        "textes modificateurs, textes modifiés, citations et références croisées."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_id": {
                "type": "string",
                "description": "Identifiant de l'article (ex: LEGIARTI000006436298)",
            },
        },
        "required": ["article_id"],
    },
)
def legifrance_liens_relatifs(article_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/relatedLinksArticle", body={"articleId": article_id})
    liens = data.get("links", data.get("related", data.get("results", [])))
    if not liens:
        return f"Aucun lien relatif trouvé pour l'article `{article_id}`."
    lines = [f"**{len(liens)} lien(s) relatif(s) pour `{article_id}`**\n"]
    for l in liens:
        titre = l.get("titre", l.get("title", l.get("text", "")))
        type_lien = l.get("typeLien", l.get("type", ""))
        rid   = l.get("id", "")
        line  = f"- {titre}"
        if type_lien:
            line += f" ({type_lien})"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_liens_service_public",
    description=(
        "Récupère les liens vers service-public.fr associés à un article juridique. "
        "Permet de trouver les fiches pratiques correspondant à un article de loi."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_cid": {
                "type": "string",
                "description": "CID de l'article (optionnel)",
            },
            "fond": {
                "type": "string",
                "description": "Fond de consultation (optionnel, ex: 'JORF', 'CODE_DATE')",
            },
        },
    },
)
def legifrance_liens_service_public(
    article_cid: Optional[str] = None,
    fond: Optional[str] = None,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {}
    if article_cid:
        body["articleCid"] = article_cid
    if fond:
        body["fond"] = fond
    data  = c._req("/consult/servicePublicLinksArticle", body=body)
    liens = data.get("links", data.get("results", []))
    if not liens:
        return "Aucun lien service-public trouvé."
    lines = [f"**{len(liens)} lien(s) service-public**\n"]
    for l in liens:
        titre = l.get("titre", l.get("title", l.get("text", "")))
        url   = l.get("url", l.get("href", ""))
        line  = f"- {titre}"
        if url:
            line += f" — {url}"
        lines.append(line)
    return "\n".join(lines)


@tool(
    name="legifrance_a_liens_service_public",
    description=(
        "Vérifie quels articles parmi une liste possèdent des liens vers service-public.fr. "
        "Utile pour filtrer rapidement un ensemble d'articles avant d'appeler legifrance_liens_service_public."
    ),
    parameters={
        "type": "object",
        "properties": {
            "article_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Liste d'identifiants d'articles à vérifier",
            },
        },
        "required": ["article_ids"],
    },
)
def legifrance_a_liens_service_public(article_ids: List[str]) -> str:
    c    = _get_client()
    data = c._req("/consult/hasServicePublicLinksArticle", body={"ids": article_ids})
    avec = data.get("ids", data.get("results", data.get("articleIds", [])))
    if not avec:
        return "Aucun des articles fournis ne possède de liens service-public."
    lines = [f"**{len(avec)}/{len(article_ids)} article(s) avec liens service-public**\n"]
    for rid in avec:
        lines.append(f"- `{rid}`")
    sans = [i for i in article_ids if i not in avec]
    if sans:
        lines.append(f"\n*Sans lien : {', '.join(f'`{i}`' for i in sans)}*")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — JORF (compléments)
# ===========================================================================

@tool(
    name="legifrance_jorf_part",
    description=(
        "Consulte la partie d'un texte publié au Journal Officiel (JORF) par son CID. "
        "Complémentaire de legifrance_jorf — retourne la structure en parties du texte."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_cid": {
                "type": "string",
                "description": "CID du texte JORF (ex: JORFTEXT000000000001)",
            },
        },
        "required": ["text_cid"],
    },
)
def legifrance_jorf_part(text_cid: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/jorfPart", body={"textCid": text_cid})
    titre = data.get("titre", data.get("title", text_cid))
    lines = [f"# {titre}\n"]
    date_p = data.get("datePubliTexte", "")
    if date_p:
        lines.append(f"**Publication JO** : {date_p}")
    parties = data.get("parties", data.get("sections", data.get("articles", [])))
    if parties:
        lines.append(f"\n**{len(parties)} partie(s)**\n")
        for p in parties[:20]:
            t = p.get("titre", p.get("title", p.get("num", "")))
            if t:
                lines.append(f"- {t}")
    else:
        texte = _strip_html(data.get("texte", data.get("content", "")))
        if texte:
            lines.append(f"\n{texte[:4000]}")
    return "\n".join(lines)


@tool(
    name="legifrance_eli_alias_texte",
    description=(
        "Récupère un texte du Journal Officiel par son identifiant ELI "
        "(European Legislation Identifier) ou son alias. "
        "Exemple : '/eli/loi/2021/8/10/PRMD2117108L/jo/texte'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "id_eli_ou_alias": {
                "type": "string",
                "description": "Identifiant ELI ou alias du texte",
            },
        },
        "required": ["id_eli_ou_alias"],
    },
)
def legifrance_eli_alias_texte(id_eli_ou_alias: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/eliAndAliasRedirectionTexte", body={"idEliOrAlias": id_eli_ou_alias})
    titre = data.get("titre", data.get("title", id_eli_ou_alias))
    lines = [f"# {titre}\n"]
    date_p = data.get("datePubliTexte", "")
    if date_p:
        lines.append(f"**Publication JO** : {date_p}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:4000]}")
        if len(texte) > 4000:
            lines.append("\n*[Texte tronqué — consultez Légifrance pour le texte intégral]*")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — KALI (compléments)
# ===========================================================================

@tool(
    name="legifrance_convention_cont",
    description=(
        "Consulte le conteneur principal d'une convention collective par son identifiant KALI "
        "(format KALICONT...). Différent de legifrance_convention_par_idcc qui utilise le numéro IDCC."
    ),
    parameters={
        "type": "object",
        "properties": {
            "cont_id": {
                "type": "string",
                "description": "Identifiant du conteneur KALI (ex: KALICONT000005635370)",
            },
        },
        "required": ["cont_id"],
    },
)
def legifrance_convention_cont(cont_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/kaliCont", body={"id": cont_id})
    titre = data.get("titre", data.get("title", cont_id))
    lines = [f"# {titre}\n"]
    idcc  = data.get("idcc", "")
    if idcc:
        lines.append(f"**IDCC** : {idcc}")
    etat = data.get("etat", "")
    if etat:
        lines.append(f"**État** : {etat}")
    sections = data.get("sections", data.get("textes", []))
    if sections:
        lines.append(f"\n**{len(sections)} section(s)/texte(s)**")
        for s in sections[:20]:
            t = s.get("titre", s.get("title", s.get("num", "")))
            rid = s.get("id", "")
            if t:
                lines.append(f"  - {t}" + (f" (`{rid}`)" if rid else ""))
        if len(sections) > 20:
            lines.append(f"  *… {len(sections)-20} élément(s) supplémentaire(s)*")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Jurisprudence (compléments)
# ===========================================================================

@tool(
    name="legifrance_jurisprudence_ancien_id",
    description=(
        "Consulte une décision de jurisprudence par son ancien identifiant Légifrance. "
        "Utile pour accéder à des décisions référencées avec des identifiants obsolètes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "ancien_id": {
                "type": "string",
                "description": "Ancien identifiant de la décision de jurisprudence",
            },
        },
        "required": ["ancien_id"],
    },
)
def legifrance_jurisprudence_ancien_id(ancien_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/getJuriWithAncienId", body={"ancienId": ancien_id})
    titre = data.get("titre", data.get("title", ancien_id))
    lines = [f"# {titre}\n"]
    juri  = data.get("juridiction", "")
    dt    = data.get("dateDecision", data.get("date", ""))
    if juri:
        lines.append(f"**Juridiction** : {juri}")
    if dt:
        lines.append(f"**Date** : {dt}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:5000]}")
        if len(texte) > 5000:
            lines.append("\n*[Texte tronqué]*")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — CNIL (compléments)
# ===========================================================================

@tool(
    name="legifrance_cnil_ancien_id",
    description=(
        "Consulte une décision ou délibération de la CNIL par son ancien identifiant. "
        "Utile pour accéder à des décisions CNIL référencées avec des identifiants obsolètes."
    ),
    parameters={
        "type": "object",
        "properties": {
            "ancien_id": {
                "type": "string",
                "description": "Ancien identifiant de la décision CNIL",
            },
        },
        "required": ["ancien_id"],
    },
)
def legifrance_cnil_ancien_id(ancien_id: str) -> str:
    c     = _get_client()
    data  = c._req("/consult/getCnilWithAncienId", body={"ancienId": ancien_id})
    titre = data.get("titre", data.get("title", ancien_id))
    lines = [f"# {titre}\n"]
    date_d = data.get("dateDecision", data.get("date", ""))
    if date_d:
        lines.append(f"**Date** : {date_d}")
    texte = _strip_html(data.get("texte", data.get("content", "")))
    if texte:
        lines.append(f"\n{texte[:5000]}")
        if len(texte) > 5000:
            lines.append("\n*[Texte tronqué]*")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Fonds LEGI
# ===========================================================================

@tool(
    name="legifrance_legi_part",
    description=(
        "Consulte le contenu d'un texte du fonds LEGI (législation consolidée) par son identifiant. "
        "Retourne la partie du texte demandée avec ses articles."
    ),
    parameters={
        "type": "object",
        "properties": {
            "text_id": {
                "type": "string",
                "description": "Identifiant du texte LEGI (ex: LEGITEXT000006070721)",
            },
            "date": {
                "type": "string",
                "description": "Date de consultation YYYY-MM-DD (défaut: aujourd'hui)",
            },
        },
        "required": ["text_id"],
    },
)
def legifrance_legi_part(text_id: str, date: Optional[str] = None) -> str:
    c    = _get_client()
    data = c._req("/consult/legiPart", body={
        "textId": text_id,
        "date":   date or globals()["date"].today().isoformat(),
    })
    titre   = data.get("titre", data.get("title", text_id))
    lines   = [f"# {titre}\n"]
    etat    = data.get("etat", "")
    date_d  = data.get("dateDebut", "")
    if etat:
        lines.append(f"**État** : {etat}")
    if date_d:
        lines.append(f"**En vigueur depuis** : {date_d}")
    articles = data.get("articles", data.get("sections", []))
    if articles:
        lines.append(f"\n**{len(articles)} article(s)/section(s)**\n")
        for a in articles[:30]:
            lines.append(_fmt_article(a))
            lines.append("")
        if len(articles) > 30:
            lines.append(f"*… {len(articles)-30} élément(s) supplémentaire(s)*")
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Tables annuelles
# ===========================================================================

@tool(
    name="legifrance_tables_annuelles",
    description=(
        "Récupère la liste des tables annuelles du Journal Officiel disponibles dans Légifrance. "
        "Les tables annuelles recensent tous les textes publiés au JO pour une période donnée. "
        "Utilisez legifrance_annees_sans_table pour connaître les années sans table disponible."
    ),
    parameters={
        "type": "object",
        "properties": {
            "annee_fin": {
                "type": "integer",
                "description": "Année de fin de la période (ex: 2024)",
            },
            "annee_debut": {
                "type": "integer",
                "description": "Année de début de la période (optionnel)",
            },
        },
        "required": ["annee_fin"],
    },
)
def legifrance_tables_annuelles(
    annee_fin: int,
    annee_debut: Optional[int] = None,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {"endYear": annee_fin}
    if annee_debut is not None:
        body["startYear"] = annee_debut
    data  = c._req("/consult/getTables", body=body)
    items = data.get("tables", data.get("results", []))
    if not items:
        periode = f"{annee_debut}–{annee_fin}" if annee_debut else str(annee_fin)
        return f"Aucune table annuelle trouvée pour la période {periode}."
    lines = [f"**{len(items)} table(s) annuelle(s)**\n"]
    for t in items:
        annee = t.get("annee", t.get("year", ""))
        titre = t.get("titre", t.get("title", ""))
        rid   = t.get("id", "")
        line  = f"- **{annee}**"
        if titre:
            line += f" — {titre}"
        if rid:
            line += f" — `{rid}`"
        lines.append(line)
    return "\n".join(lines)


# ===========================================================================
# OUTILS CONSULT — Métadonnées BOCC
# ===========================================================================

@tool(
    name="legifrance_bocc_pdf_metadata",
    description=(
        "Récupère les métadonnées du PDF associé à un texte unitaire du BOCC "
        "(Bulletin Officiel des Conventions Collectives). "
        "Utile pour accéder au fichier PDF original d'un accord publié au BOCC."
    ),
    parameters={
        "type": "object",
        "properties": {
            "bocc_id": {
                "type": "string",
                "description": "Identifiant du texte BOCC (optionnel)",
            },
            "pour_bocc_global": {
                "type": "boolean",
                "description": "True pour cibler le BOCC global plutôt qu'un texte unitaire (optionnel)",
            },
        },
    },
)
def legifrance_bocc_pdf_metadata(
    bocc_id: Optional[str] = None,
    pour_bocc_global: Optional[bool] = None,
) -> str:
    c    = _get_client()
    body: Dict[str, Any] = {}
    if bocc_id:
        body["id"] = bocc_id
    if pour_bocc_global is not None:
        body["forGlobalBocc"] = pour_bocc_global
    data = c._req("/consult/getBoccTextPdfMetadata", body=body)
    if not data:
        return "Aucune métadonnée PDF BOCC trouvée."
    lines = ["**Métadonnées PDF BOCC**\n"]
    for k, v in data.items():
        if v:
            lines.append(f"- **{k}** : {v}")
    return "\n".join(lines) if len(lines) > 1 else "Aucune métadonnée disponible."


# ---------------------------------------------------------------------------
# Confirmation de chargement
# ---------------------------------------------------------------------------
_tools_count = sum(1 for name in [
    # Recherche
    "legifrance_rechercher", "legifrance_version_canonique_article",
    "legifrance_version_canonique", "legifrance_version_proche",
    # Consultation codes/lois
    "legifrance_consulter_code", "legifrance_obtenir_article",
    "legifrance_article_par_numero", "legifrance_versions_article",
    "legifrance_loi_decret", "legifrance_jorf",
    "legifrance_jo_par_nor", "legifrance_derniers_jo", "legifrance_sommaire_jorf",
    # KALI
    "legifrance_convention_par_idcc", "legifrance_convention_texte",
    "legifrance_convention_article", "legifrance_convention_section",
    # Jurisprudence
    "legifrance_jurisprudence", "legifrance_jurisprudence_plan_classement",
    # Divers
    "legifrance_cnil", "legifrance_acco", "legifrance_circulaire",
    "legifrance_debat", "legifrance_dossier_legislatif", "legifrance_section_par_cid",
    # Chrono
    "legifrance_historique_texte", "legifrance_versions_element", "legifrance_a_des_versions",
    # List
    "legifrance_lister_codes", "legifrance_conventions", "legifrance_lister_loda",
    "legifrance_lister_legislatures", "legifrance_lister_dossiers_legislatifs",
    "legifrance_lister_debats_parlementaires", "legifrance_lister_questions_parlementaires",
    "legifrance_lister_bocc", "legifrance_lister_bocc_textes",
    "legifrance_lister_boccs_et_textes", "legifrance_lister_docs_admins",
    # Suggest
    "legifrance_suggerer", "legifrance_suggerer_acco", "legifrance_suggerer_pdc",
    # Misc
    "legifrance_dates_sans_jo", "legifrance_annees_sans_table",
    "legifrance_commit_id",
    # List (nouveau)
    "legifrance_lister_bodmr",
    # Consult — codes (nouveaux)
    "legifrance_code_complet", "legifrance_code_par_ancien_id",
    "legifrance_article_par_eli", "legifrance_articles_meme_numero",
    # Consult — liens d'articles (nouveaux)
    "legifrance_liens_concordance", "legifrance_liens_relatifs",
    "legifrance_liens_service_public", "legifrance_a_liens_service_public",
    # Consult — JORF (nouveaux)
    "legifrance_jorf_part", "legifrance_eli_alias_texte",
    # Consult — KALI (nouveau)
    "legifrance_convention_cont",
    # Consult — JURI (nouveau)
    "legifrance_jurisprudence_ancien_id",
    # Consult — CNIL (nouveau)
    "legifrance_cnil_ancien_id",
    # Consult — LEGI (nouveau)
    "legifrance_legi_part",
    # Consult — tables annuelles (nouveau)
    "legifrance_tables_annuelles",
    # Consult — BOCC métadonnées (nouveau)
    "legifrance_bocc_pdf_metadata",
])
logger.info(f"✅ tools.legifrance_tools : {_tools_count} outils enregistrés dans Prométhée")
