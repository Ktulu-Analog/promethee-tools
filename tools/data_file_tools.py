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
tools/data_file_tools.py — Outils CSV / Excel avancés
=======================================================

Outils exposés (21) :

  Lecture (2) :
    - df_read           : charge un CSV ou Excel en mémoire sous un nom de dataset
    - df_list           : liste les datasets chargés en session (noms, dimensions, colonnes)

  Exploration (3) :
    - df_head           : affiche les premières/dernières lignes d'un dataset
    - df_info           : statistiques descriptives et infos sur les colonnes
    - df_value_counts   : fréquence des valeurs d'une colonne

  Analyse (3) :
    - df_groupby        : agrégation par groupe (équivalent GROUP BY SQL)
    - df_correlate      : matrice de corrélation entre colonnes numériques
    - df_outliers       : détection des valeurs aberrantes (IQR ou z-score)

  Transformation (8) :
    - df_query          : filtre / sélectionne / trie avec une expression pandas
    - df_pivot          : tableau croisé dynamique (pivot table)
    - df_merge          : fusionne deux datasets (JOIN)
    - df_concat         : empile des datasets verticalement (UNION SQL)
    - df_clean          : nettoyage en une passe (NaN, doublons, types, renommage)
    - df_cast           : conversion de types de colonnes
    - df_apply          : création de colonnes calculées (calculs de dates, tranches d'âge…)
    - df_rename         : renomme des colonnes

  Échantillonnage (1) :
    - df_sample         : tirage aléatoire ou stratifié

  Conformité (1) :
    - df_anonymize      : anonymisation / pseudonymisation RGPD (hachage, masquage,
                          généralisation, bruit gaussien)

  Écriture (2) :
    - df_write          : exporte un dataset en CSV ou Excel
    - df_drop           : supprime un dataset de la mémoire session

Stratégie :
  - Les datasets sont nommés et conservés en session (dict global)
  - Tout passe par pandas ; les feuilles Excel multiples sont supportées
  - Les résultats volumineux sont tronqués avec indicateur
  - Les valeurs non JSON-sérialisables (NaT, NaN, Decimal…) sont normalisées
  - df_apply expose today/date_auj, Timedelta, cut, qcut pour les calculs RH

Prérequis :
    pip install pandas openpyxl
"""

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Any

import pandas as pd
import numpy as np

from core.tools_engine import tool, set_current_family, _TOOL_ICONS

set_current_family("data_file_tools", "Fichiers de données", "📊")

# ── Icônes ────────────────────────────────────────────────────────────────────
_TOOL_ICONS.update({
    "df_read":         "📂",
    "df_list":         "📋",
    "df_head":         "👁️",
    "df_info":         "📊",
    "df_value_counts": "🔢",
    "df_groupby":      "📦",
    "df_correlate":    "🔗",
    "df_outliers":     "⚠️",
    "df_query":        "🔍",
    "df_pivot":        "🔄",
    "df_merge":        "🔗",
    "df_concat":       "📎",
    "df_clean":        "🧹",
    "df_cast":         "🔁",
    "df_apply":        "⚙️",
    "df_rename":       "✏️",
    "df_sample":       "🎲",
    "df_anonymize":    "🔒",
    "df_write":        "💾",
    "df_drop":         "🗑️",
})

# ── Registre de datasets (session) ────────────────────────────────────────────
# { nom: { "df": DataFrame, "source": str, "loaded_at": str } }
_DATASETS: dict[str, dict] = {}

_MAX_ROWS_DISPLAY = 100     # lignes max dans les retours JSON
_MAX_COLS_DISPLAY = 50      # colonnes max dans les retours JSON


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _safe(val: Any) -> Any:
    """Normalise les valeurs non JSON-sérialisables."""
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, (pd.Timestamp, datetime)):
        return val.isoformat()
    if isinstance(val, pd.NaT.__class__):
        return None
    if isinstance(val, np.integer):
        return int(val)
    if isinstance(val, np.floating):
        v = float(val)
        return None if math.isnan(v) or math.isinf(v) else v
    if isinstance(val, np.bool_):
        return bool(val)
    if isinstance(val, np.ndarray):
        return val.tolist()
    if isinstance(val, bytes):
        return f"<bytes {len(val)}>"
    return val


def _df_to_records(df: pd.DataFrame, max_rows: int = _MAX_ROWS_DISPLAY) -> tuple[list, bool]:
    """Convertit un DataFrame en liste de dicts JSON-safe. Retourne (records, tronqué)."""
    truncated = len(df) > max_rows
    subset = df.head(max_rows)
    records = []
    for row in subset.itertuples(index=False):
        records.append({
            col: _safe(val)
            for col, val in zip(subset.columns, row)
        })
    return records, truncated


def _get_df(nom: str) -> pd.DataFrame:
    """Retourne le DataFrame nommé ou lève une erreur explicite."""
    if nom not in _DATASETS:
        noms = list(_DATASETS.keys())
        hint = f" Datasets disponibles : {noms}." if noms else " Aucun dataset chargé."
        raise KeyError(
            f"Dataset '{nom}' introuvable.{hint} "
            "Utilisez df_read pour charger un fichier."
        )
    return _DATASETS[nom]["df"]


def _detect_encoding(path: Path) -> str:
    """Détecte l'encodage d'un fichier CSV (UTF-8 BOM, latin-1, etc.)."""
    try:
        with open(path, "rb") as f:
            raw = f.read(4096)
        if raw.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        # Tentative UTF-8
        raw.decode("utf-8")
        return "utf-8"
    except Exception:
        return "latin-1"


def _infer_separator(path: Path, encoding: str) -> str:
    """Détecte le séparateur CSV (virgule, point-virgule, tabulation)."""
    try:
        with open(path, encoding=encoding, errors="replace") as f:
            first_line = f.readline()
        counts = {sep: first_line.count(sep) for sep in (",", ";", "\t", "|")}
        return max(counts, key=counts.get)
    except Exception:
        return ","


# ══════════════════════════════════════════════════════════════════════════════
# OUTILS
# ══════════════════════════════════════════════════════════════════════════════

@tool(
    name="df_read",
    description=(
        "Charge un fichier CSV ou Excel (.xlsx, .xls, .ods) en mémoire sous un nom court. "
        "Détecte automatiquement l'encodage et le séparateur des fichiers CSV. "
        "Pour les Excel multi-feuilles, utiliser le paramètre 'feuille'. "
        "Le dataset reste disponible pour toute la session sous le nom donné."
    ),
    parameters={
        "type": "object",
        "properties": {
            "chemin": {
                "type": "string",
                "description": "Chemin absolu ou relatif du fichier CSV ou Excel.",
            },
            "nom": {
                "type": "string",
                "description": (
                    "Nom court pour référencer ce dataset (ex: 'ventes', 'clients'). "
                    "Défaut : nom du fichier sans extension."
                ),
            },
            "feuille": {
                "type": "string",
                "description": "Nom ou index (0-basé) de la feuille Excel (défaut : première feuille).",
            },
            "separateur": {
                "type": "string",
                "description": "Séparateur CSV (défaut : détection automatique parmi , ; \\t |).",
            },
            "encodage": {
                "type": "string",
                "description": "Encodage du fichier CSV (défaut : détection automatique).",
            },
            "lignes_header": {
                "type": "integer",
                "description": "Numéro de la ligne d'en-têtes (0-basé, défaut: 0).",
            },
            "ignorer_lignes": {
                "type": "integer",
                "description": "Nombre de lignes à sauter en début de fichier (défaut: 0).",
            },
        },
        "required": ["chemin"],
    },
)
def df_read(
    chemin: str,
    nom: Optional[str] = None,
    feuille: Optional[str] = None,
    separateur: Optional[str] = None,
    encodage: Optional[str] = None,
    lignes_header: int = 0,
    ignorer_lignes: int = 0,
) -> dict:
    path = Path(chemin).expanduser()
    if not path.exists():
        return {"status": "error", "error": f"Fichier introuvable : {chemin}"}

    dataset_name = nom or path.stem
    ext = path.suffix.lower()

    try:
        t0 = time.perf_counter()

        if ext in (".xlsx", ".xls", ".ods", ".xlsm"):
            # ── Excel ──
            xl = pd.ExcelFile(path, engine="openpyxl" if ext != ".xls" else "xlrd")
            sheet_names = xl.sheet_names

            sheet = feuille
            if sheet is None:
                sheet = sheet_names[0]
            elif isinstance(sheet, str) and sheet.isdigit():
                sheet = sheet_names[int(sheet)]

            df = pd.read_excel(
                xl, sheet_name=sheet,
                header=lignes_header,
                skiprows=ignorer_lignes if ignorer_lignes > 0 else None,
            )
            source_info = f"{path.name} / feuille '{sheet}'"
            extra = {"feuilles_disponibles": sheet_names, "feuille_chargee": sheet}

        elif ext in (".csv", ".tsv", ".txt"):
            # ── CSV ──
            enc = encodage or _detect_encoding(path)
            sep = separateur or _infer_separator(path, enc)

            df = pd.read_csv(
                path,
                sep=sep,
                encoding=enc,
                header=lignes_header,
                skiprows=range(1, ignorer_lignes + 1) if ignorer_lignes > 0 else None,
                low_memory=False,
                na_values=["", "NA", "N/A", "NULL", "null", "None", "#N/A"],
            )
            source_info = path.name
            extra = {"separateur_detecte": sep, "encodage_detecte": enc}

        else:
            return {
                "status": "error",
                "error": f"Format non supporté : '{ext}'. Formats acceptés : .csv, .tsv, .xlsx, .xls, .ods",
            }

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

        # Nettoyer les noms de colonnes
        df.columns = [str(c).strip() for c in df.columns]

        # Stocker
        _DATASETS[dataset_name] = {
            "df":        df,
            "source":    source_info,
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # Aperçu des types
        types = {col: str(dtype) for col, dtype in df.dtypes.items()}

        return {
            "status":       "success",
            "nom":          dataset_name,
            "source":       source_info,
            "nb_lignes":    len(df),
            "nb_colonnes":  len(df.columns),
            "colonnes":     list(df.columns),
            "types":        types,
            "duree_ms":     elapsed_ms,
            "message":      f"Dataset '{dataset_name}' chargé : {len(df)} lignes × {len(df.columns)} colonnes.",
            **extra,
        }

    except Exception as e:
        return {"status": "error", "error": f"Erreur lecture : {e}"}


@tool(
    name="df_list",
    description="Liste tous les datasets chargés en session avec leurs dimensions et source.",
    parameters={"type": "object", "properties": {}, "required": []},
)
def df_list() -> dict:
    if not _DATASETS:
        return {
            "status":   "success",
            "nombre":   0,
            "datasets": [],
            "message":  "Aucun dataset en mémoire. Utilisez df_read pour charger un fichier.",
        }
    datasets = []
    for nom, info in _DATASETS.items():
        df = info["df"]
        datasets.append({
            "nom":         nom,
            "source":      info["source"],
            "nb_lignes":   len(df),
            "nb_colonnes": len(df.columns),
            "colonnes":    list(df.columns),
            "charge_le":   info["loaded_at"],
        })
    return {"status": "success", "nombre": len(datasets), "datasets": datasets}


@tool(
    name="df_head",
    description=(
        "Affiche les premières ou dernières lignes d'un dataset. "
        "Utile pour vérifier rapidement le contenu après chargement."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset.",
            },
            "n": {
                "type": "integer",
                "description": "Nombre de lignes à afficher (défaut: 10). Négatif = dernières lignes.",
            },
            "colonnes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Sous-ensemble de colonnes à afficher (défaut: toutes).",
            },
        },
        "required": ["nom"],
    },
)
def df_head(
    nom: str,
    n: int = 10,
    colonnes: Optional[list] = None,
) -> dict:
    try:
        df = _get_df(nom)
        n = max(-len(df), min(n, _MAX_ROWS_DISPLAY))

        if colonnes:
            manquantes = [c for c in colonnes if c not in df.columns]
            if manquantes:
                return {
                    "status": "error",
                    "error": f"Colonnes introuvables : {manquantes}. "
                             f"Colonnes disponibles : {list(df.columns)}",
                }
            subset = df[colonnes]
        else:
            subset = df

        view = subset.tail(abs(n)) if n < 0 else subset.head(n)
        records, _ = _df_to_records(view, max_rows=abs(n))

        return {
            "status":      "success",
            "nom":         nom,
            "nb_lignes":   len(df),
            "nb_colonnes": len(df.columns),
            "affichees":   len(records),
            "sens":        "fin" if n < 0 else "début",
            "lignes":      records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_head : {e}"}


@tool(
    name="df_info",
    description=(
        "Retourne des statistiques descriptives complètes sur un dataset : "
        "types de colonnes, valeurs manquantes, min/max/moyenne/médiane/écart-type "
        "pour les colonnes numériques, valeurs uniques pour les colonnes texte. "
        "Idéal pour comprendre rapidement la structure et la qualité des données."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset.",
            },
            "colonnes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes à analyser (défaut: toutes).",
            },
        },
        "required": ["nom"],
    },
)
def df_info(nom: str, colonnes: Optional[list] = None) -> dict:
    try:
        df = _get_df(nom)

        if colonnes:
            manquantes = [c for c in colonnes if c not in df.columns]
            if manquantes:
                return {"status": "error",
                        "error": f"Colonnes introuvables : {manquantes}"}
            df = df[colonnes]

        infos = []
        for col in df.columns:
            series = df[col]
            nb_null = int(series.isna().sum())
            nb_unique = int(series.nunique(dropna=True))
            col_info: dict = {
                "colonne":         col,
                "type":            str(series.dtype),
                "nb_valeurs":      len(series),
                "nb_manquants":    nb_null,
                "pct_manquants":   round(nb_null / len(series) * 100, 1) if len(series) else 0,
                "nb_uniques":      nb_unique,
            }

            if pd.api.types.is_numeric_dtype(series):
                desc = series.describe()
                col_info.update({
                    "min":    _safe(desc.get("min")),
                    "max":    _safe(desc.get("max")),
                    "moyenne":  _safe(desc.get("mean")),
                    "mediane":  _safe(series.median()),
                    "ecart_type": _safe(desc.get("std")),
                    "q25":    _safe(desc.get("25%")),
                    "q75":    _safe(desc.get("75%")),
                })
            elif pd.api.types.is_datetime64_any_dtype(series):
                col_info.update({
                    "min": _safe(series.min()),
                    "max": _safe(series.max()),
                })
            else:
                # Texte : top valeurs
                top = series.value_counts(dropna=True).head(5)
                col_info["top_valeurs"] = [
                    {"valeur": _safe(v), "occurrences": int(c)}
                    for v, c in top.items()
                ]

            infos.append(col_info)

        # Doublons
        nb_doublons = int(df.duplicated().sum())

        return {
            "status":       "success",
            "nom":          nom,
            "nb_lignes":    len(df),
            "nb_colonnes":  len(df.columns),
            "nb_doublons":  nb_doublons,
            "pct_doublons": round(nb_doublons / len(df) * 100, 1) if len(df) else 0,
            "colonnes":     infos,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_info : {e}"}


@tool(
    name="df_value_counts",
    description=(
        "Compte la fréquence de chaque valeur dans une colonne. "
        "Permet de détecter rapidement les valeurs dominantes, les anomalies "
        "ou la distribution d'une variable catégorielle."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset.",
            },
            "colonne": {
                "type": "string",
                "description": "Colonne à analyser.",
            },
            "limite": {
                "type": "integer",
                "description": "Nombre max de valeurs à retourner (défaut: 20).",
            },
            "normaliser": {
                "type": "boolean",
                "description": "Si true, retourne les pourcentages plutôt que les comptages bruts.",
            },
            "inclure_nan": {
                "type": "boolean",
                "description": "Si true, inclut les valeurs manquantes dans le décompte (défaut: false).",
            },
        },
        "required": ["nom", "colonne"],
    },
)
def df_value_counts(
    nom: str,
    colonne: str,
    limite: int = 20,
    normaliser: bool = False,
    inclure_nan: bool = False,
) -> dict:
    try:
        df = _get_df(nom)
        if colonne not in df.columns:
            return {
                "status": "error",
                "error": f"Colonne '{colonne}' introuvable. "
                         f"Colonnes disponibles : {list(df.columns)}",
            }

        vc = df[colonne].value_counts(normalize=normaliser, dropna=not inclure_nan)
        total = len(df[colonne].dropna() if not inclure_nan else df[colonne])

        resultats = []
        for val, count in vc.head(limite).items():
            entry: dict = {"valeur": _safe(val)}
            if normaliser:
                entry["pourcentage"] = round(float(count) * 100, 2)
            else:
                entry["occurrences"] = int(count)
                entry["pourcentage"] = round(int(count) / total * 100, 2) if total else 0
            resultats.append(entry)

        return {
            "status":          "success",
            "nom":             nom,
            "colonne":         colonne,
            "nb_valeurs_total": total,
            "nb_valeurs_uniques": int(df[colonne].nunique(dropna=not inclure_nan)),
            "nb_manquants":    int(df[colonne].isna().sum()),
            "affichees":       len(resultats),
            "resultats":       resultats,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_value_counts : {e}"}


@tool(
    name="df_query",
    description=(
        "Filtre, sélectionne, trie et transforme un dataset avec une expression pandas. "
        "Peut créer un nouveau dataset ou retourner le résultat directement. "
        "Exemples d'expression : "
        "'age > 30 and ville == \"Paris\"' — "
        "'salaire.between(30000, 60000)' — "
        "'dept.str.contains(\"Tech\", case=False)'. "
        "Pour le tri, utiliser le paramètre 'trier_par'. "
        "Pour sélectionner des colonnes, utiliser 'colonnes'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset source.",
            },
            "filtre": {
                "type": "string",
                "description": "Expression de filtre pandas (ex: 'age > 30 and pays == \"FR\"').",
            },
            "colonnes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes à conserver dans le résultat (défaut: toutes).",
            },
            "trier_par": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes de tri (ex: ['date', 'montant']).",
            },
            "ordre_desc": {
                "type": "boolean",
                "description": "Si true, tri décroissant (défaut: false = croissant).",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Si fourni, sauvegarde le résultat comme nouveau dataset sous ce nom.",
            },
            "limite": {
                "type": "integer",
                "description": f"Nombre max de lignes retournées (défaut: {_MAX_ROWS_DISPLAY}).",
            },
        },
        "required": ["nom"],
    },
)
def df_query(
    nom: str,
    filtre: Optional[str] = None,
    colonnes: Optional[list] = None,
    trier_par: Optional[list] = None,
    ordre_desc: bool = False,
    sauvegarder_sous: Optional[str] = None,
    limite: int = _MAX_ROWS_DISPLAY,
) -> dict:
    limite = min(max(1, limite), _MAX_ROWS_DISPLAY)

    try:
        df = _get_df(nom).copy()

        # Filtre
        if filtre:
            try:
                df = df.query(filtre, engine="python")
            except Exception as e:
                return {
                    "status": "error",
                    "error":  f"Expression de filtre invalide : {e}. "
                              f"Vérifiez la syntaxe (guillemets doubles pour les chaînes).",
                }

        # Sélection de colonnes
        if colonnes:
            manquantes = [c for c in colonnes if c not in df.columns]
            if manquantes:
                return {"status": "error",
                        "error": f"Colonnes introuvables : {manquantes}"}
            df = df[colonnes]

        # Tri
        if trier_par:
            manquantes = [c for c in trier_par if c not in df.columns]
            if manquantes:
                return {"status": "error",
                        "error": f"Colonnes de tri introuvables : {manquantes}"}
            df = df.sort_values(trier_par, ascending=not ordre_desc)

        # Sauvegarder si demandé
        if sauvegarder_sous:
            _DATASETS[sauvegarder_sous] = {
                "df":        df.reset_index(drop=True),
                "source":    f"df_query({nom})",
                "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        records, truncated = _df_to_records(df, limite)

        return {
            "status":         "success",
            "nom_source":     nom,
            "filtre":         filtre,
            "nb_lignes":      len(df),
            "nb_colonnes":    len(df.columns),
            "tronque":        truncated,
            "sauvegarde_sous": sauvegarder_sous,
            "colonnes":       list(df.columns),
            "lignes":         records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_query : {e}"}


@tool(
    name="df_pivot",
    description=(
        "Crée un tableau croisé dynamique (pivot table) à partir d'un dataset. "
        "Permet d'agréger des données par groupes (somme, moyenne, comptage, min, max…). "
        "Exemple : résumé des ventes par région et par produit."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset source.",
            },
            "index": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes à utiliser comme index des lignes du pivot.",
            },
            "colonnes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes à déployer en en-têtes de colonnes (optionnel).",
            },
            "valeurs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes numériques à agréger.",
            },
            "agregation": {
                "type": "string",
                "description": "Fonction d'agrégation : 'sum', 'mean', 'count', 'min', 'max', 'median', 'std' (défaut: 'sum').",
            },
            "totaux": {
                "type": "boolean",
                "description": "Ajouter des totaux de lignes et colonnes (défaut: true).",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Si fourni, sauvegarde le pivot comme nouveau dataset.",
            },
        },
        "required": ["nom", "index"],
    },
)
def df_pivot(
    nom: str,
    index: list,
    colonnes: Optional[list] = None,
    valeurs: Optional[list] = None,
    agregation: str = "sum",
    totaux: bool = True,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    AGGS = {"sum", "mean", "count", "min", "max", "median", "std", "nunique"}
    if agregation not in AGGS:
        return {"status": "error",
                "error": f"Agrégation '{agregation}' non supportée. Valeurs : {sorted(AGGS)}"}

    try:
        df = _get_df(nom)

        # Vérifier les colonnes
        all_cols = index + (colonnes or []) + (valeurs or [])
        manquantes = [c for c in all_cols if c not in df.columns]
        if manquantes:
            return {"status": "error",
                    "error": f"Colonnes introuvables : {manquantes}"}

        pivot = pd.pivot_table(
            df,
            index=index,
            columns=colonnes if colonnes else None,
            values=valeurs if valeurs else None,
            aggfunc=agregation,
            margins=totaux,
            margins_name="Total",
        )

        # Aplatir les multi-index de colonnes
        if isinstance(pivot.columns, pd.MultiIndex):
            pivot.columns = [" / ".join(str(c) for c in col).strip()
                             for col in pivot.columns]

        pivot = pivot.reset_index()

        if sauvegarder_sous:
            _DATASETS[sauvegarder_sous] = {
                "df":        pivot,
                "source":    f"df_pivot({nom})",
                "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        records, truncated = _df_to_records(pivot)

        return {
            "status":          "success",
            "nom_source":      nom,
            "agregation":      agregation,
            "nb_lignes":       len(pivot),
            "nb_colonnes":     len(pivot.columns),
            "tronque":         truncated,
            "sauvegarde_sous": sauvegarder_sous,
            "colonnes":        list(pivot.columns),
            "lignes":          records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_pivot : {e}"}


@tool(
    name="df_merge",
    description=(
        "Fusionne deux datasets (JOIN). "
        "Types de jointure : 'inner' (intersection), 'left', 'right', 'outer' (union). "
        "Equivalent SQL : SELECT * FROM gauche JOIN droite ON gauche.cle = droite.cle"
    ),
    parameters={
        "type": "object",
        "properties": {
            "gauche": {
                "type": "string",
                "description": "Nom du dataset gauche.",
            },
            "droite": {
                "type": "string",
                "description": "Nom du dataset droit.",
            },
            "sur": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonne(s) commune(s) pour la jointure (même nom dans les deux datasets).",
            },
            "sur_gauche": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonne(s) de jointure dans le dataset gauche (si noms différents).",
            },
            "sur_droite": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonne(s) de jointure dans le dataset droit (si noms différents).",
            },
            "type_jointure": {
                "type": "string",
                "description": "Type de jointure : 'inner' (défaut), 'left', 'right', 'outer'.",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset résultat (obligatoire pour conserver le résultat).",
            },
        },
        "required": ["gauche", "droite"],
    },
)
def df_merge(
    gauche: str,
    droite: str,
    sur: Optional[list] = None,
    sur_gauche: Optional[list] = None,
    sur_droite: Optional[list] = None,
    type_jointure: str = "inner",
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    TYPES = {"inner", "left", "right", "outer"}
    if type_jointure not in TYPES:
        return {"status": "error",
                "error": f"Type de jointure invalide : '{type_jointure}'. Valeurs : {sorted(TYPES)}"}

    try:
        df_g = _get_df(gauche)
        df_d = _get_df(droite)

        merged = pd.merge(
            df_g, df_d,
            on=sur if sur else None,
            left_on=sur_gauche if sur_gauche else None,
            right_on=sur_droite if sur_droite else None,
            how=type_jointure,
            suffixes=("_g", "_d"),
        )

        if sauvegarder_sous:
            _DATASETS[sauvegarder_sous] = {
                "df":        merged,
                "source":    f"df_merge({gauche}, {droite})",
                "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        records, truncated = _df_to_records(merged)

        return {
            "status":          "success",
            "gauche":          gauche,
            "droite":          droite,
            "type_jointure":   type_jointure,
            "cle_jointure":    sur or {"gauche": sur_gauche, "droite": sur_droite},
            "nb_lignes":       len(merged),
            "nb_colonnes":     len(merged.columns),
            "tronque":         truncated,
            "sauvegarde_sous": sauvegarder_sous,
            "colonnes":        list(merged.columns),
            "lignes":          records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_merge : {e}"}


@tool(
    name="df_groupby",
    description=(
        "Agrège un dataset par groupe (équivalent SQL GROUP BY). "
        "Permet d'appliquer plusieurs fonctions d'agrégation simultanément sur plusieurs colonnes. "
        "Exemple : total des ventes et nombre de commandes par région et par mois. "
        "Fonctions disponibles : sum, mean, count, min, max, median, std, nunique, first, last."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset source.",
            },
            "grouper_par": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes de regroupement (ex: ['region', 'mois']).",
            },
            "agregations": {
                "type": "object",
                "description": (
                    "Dictionnaire colonne → fonction(s) d'agrégation. "
                    "Exemples : {'ca': 'sum', 'nb_clients': 'count'} "
                    "ou {'ca': ['sum', 'mean'], 'age': 'median'}."
                ),
            },
            "trier_par": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes de tri du résultat (défaut : colonnes de groupement).",
            },
            "ordre_desc": {
                "type": "boolean",
                "description": "Tri décroissant (défaut: false).",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset résultat à sauvegarder.",
            },
        },
        "required": ["nom", "grouper_par", "agregations"],
    },
)
def df_groupby(
    nom: str,
    grouper_par: list,
    agregations: dict,
    trier_par: Optional[list] = None,
    ordre_desc: bool = False,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    AGGS = {"sum", "mean", "count", "min", "max", "median", "std", "nunique", "first", "last"}
    try:
        df = _get_df(nom)

        # Vérifier les colonnes de groupement
        manquantes = [c for c in grouper_par if c not in df.columns]
        if manquantes:
            return {"status": "error", "error": f"Colonnes de groupement introuvables : {manquantes}"}

        # Vérifier et normaliser les agrégations
        agg_dict: dict = {}
        for col, funcs in agregations.items():
            if col not in df.columns:
                return {"status": "error", "error": f"Colonne d'agrégation introuvable : '{col}'"}
            funcs_list = [funcs] if isinstance(funcs, str) else list(funcs)
            invalides = [f for f in funcs_list if f not in AGGS]
            if invalides:
                return {"status": "error",
                        "error": f"Fonctions inconnues : {invalides}. Disponibles : {sorted(AGGS)}"}
            agg_dict[col] = funcs_list if len(funcs_list) > 1 else funcs_list[0]

        result = df.groupby(grouper_par, dropna=False).agg(agg_dict)

        # Aplatir les multi-index de colonnes (cas multi-fonctions)
        if isinstance(result.columns, pd.MultiIndex):
            result.columns = ["_".join(str(c) for c in col).strip("_")
                               for col in result.columns]

        result = result.reset_index()

        # Tri
        sort_cols = trier_par or grouper_par
        sort_cols_valides = [c for c in sort_cols if c in result.columns]
        if sort_cols_valides:
            result = result.sort_values(sort_cols_valides, ascending=not ordre_desc)

        if sauvegarder_sous:
            _DATASETS[sauvegarder_sous] = {
                "df":        result.reset_index(drop=True),
                "source":    f"df_groupby({nom})",
                "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        records, truncated = _df_to_records(result)
        return {
            "status":          "success",
            "nom_source":      nom,
            "grouper_par":     grouper_par,
            "nb_groupes":      len(result),
            "nb_colonnes":     len(result.columns),
            "tronque":         truncated,
            "sauvegarde_sous": sauvegarder_sous,
            "colonnes":        list(result.columns),
            "lignes":          records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_groupby : {e}"}


@tool(
    name="df_correlate",
    description=(
        "Calcule la matrice de corrélation entre les colonnes numériques d'un dataset. "
        "Méthodes disponibles : 'pearson' (linéaire, défaut), 'spearman' (rang, robuste aux outliers), "
        "'kendall' (rang, petits échantillons). "
        "Retourne aussi les paires les plus corrélées pour faciliter l'interprétation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset.",
            },
            "colonnes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes numériques à inclure (défaut: toutes les colonnes numériques).",
            },
            "methode": {
                "type": "string",
                "description": "Méthode de corrélation : 'pearson' (défaut), 'spearman', 'kendall'.",
            },
            "seuil": {
                "type": "number",
                "description": "Seuil absolu pour filtrer les paires faiblement corrélées (défaut: 0.0 = tout afficher).",
            },
            "top_n": {
                "type": "integer",
                "description": "Nombre de paires les plus corrélées à retourner (défaut: 10).",
            },
        },
        "required": ["nom"],
    },
)
def df_correlate(
    nom: str,
    colonnes: Optional[list] = None,
    methode: str = "pearson",
    seuil: float = 0.0,
    top_n: int = 10,
) -> dict:
    METHODES = {"pearson", "spearman", "kendall"}
    if methode not in METHODES:
        return {"status": "error",
                "error": f"Méthode '{methode}' inconnue. Disponibles : {sorted(METHODES)}"}
    try:
        df = _get_df(nom)

        # Sélectionner les colonnes numériques
        if colonnes:
            manquantes = [c for c in colonnes if c not in df.columns]
            if manquantes:
                return {"status": "error", "error": f"Colonnes introuvables : {manquantes}"}
            num_df = df[colonnes].select_dtypes(include="number")
        else:
            num_df = df.select_dtypes(include="number")

        if num_df.empty or len(num_df.columns) < 2:
            return {"status": "error",
                    "error": "Au moins 2 colonnes numériques sont nécessaires pour calculer une corrélation."}

        corr = num_df.corr(method=methode)

        # Matrice complète
        matrice = {
            col: {c: round(_safe(v), 4) for c, v in row.items()}
            for col, row in corr.to_dict().items()
        }

        # Top paires (triangle supérieur, sans diagonale)
        paires = []
        cols = list(corr.columns)
        for i in range(len(cols)):
            for j in range(i + 1, len(cols)):
                val = corr.iloc[i, j]
                if not math.isnan(val) and abs(val) >= seuil:
                    paires.append({
                        "colonne_a":    cols[i],
                        "colonne_b":    cols[j],
                        "correlation":  round(float(val), 4),
                        "intensite":    (
                            "forte" if abs(val) >= 0.7
                            else "modérée" if abs(val) >= 0.4
                            else "faible"
                        ),
                        "sens": "positive" if val > 0 else "négative",
                    })

        paires.sort(key=lambda x: abs(x["correlation"]), reverse=True)

        return {
            "status":          "success",
            "nom":             nom,
            "methode":         methode,
            "nb_colonnes":     len(num_df.columns),
            "colonnes":        list(num_df.columns),
            "matrice":         matrice,
            "top_paires":      paires[:top_n],
            "nb_paires_total": len(paires),
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_correlate : {e}"}


@tool(
    name="df_outliers",
    description=(
        "Détecte les valeurs aberrantes dans les colonnes numériques d'un dataset. "
        "Méthode IQR (interquartile range, robuste) : valeurs en dehors de [Q1 - k*IQR, Q3 + k*IQR]. "
        "Méthode z-score (distribution normale) : valeurs dont |z| > seuil. "
        "Retourne les lignes concernées et des statistiques par colonne."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset.",
            },
            "colonnes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes numériques à analyser (défaut: toutes).",
            },
            "methode": {
                "type": "string",
                "description": "Méthode : 'iqr' (défaut, robuste) ou 'zscore'.",
            },
            "k": {
                "type": "number",
                "description": "Multiplicateur IQR (défaut: 1.5 = standard, 3.0 = outliers extrêmes).",
            },
            "seuil_z": {
                "type": "number",
                "description": "Seuil z-score (défaut: 3.0).",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Sauvegarde les lignes aberrantes comme nouveau dataset.",
            },
        },
        "required": ["nom"],
    },
)
def df_outliers(
    nom: str,
    colonnes: Optional[list] = None,
    methode: str = "iqr",
    k: float = 1.5,
    seuil_z: float = 3.0,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    if methode not in ("iqr", "zscore"):
        return {"status": "error", "error": "Méthode invalide. Utilisez 'iqr' ou 'zscore'."}
    try:
        df = _get_df(nom)

        if colonnes:
            manquantes = [c for c in colonnes if c not in df.columns]
            if manquantes:
                return {"status": "error", "error": f"Colonnes introuvables : {manquantes}"}
            num_df = df[colonnes].select_dtypes(include="number")
        else:
            num_df = df.select_dtypes(include="number")

        if num_df.empty:
            return {"status": "error", "error": "Aucune colonne numérique trouvée."}

        outlier_mask = pd.Series(False, index=df.index)
        stats_par_colonne = []

        for col in num_df.columns:
            series = num_df[col].dropna()
            if len(series) < 4:
                continue

            if methode == "iqr":
                q1, q3 = series.quantile(0.25), series.quantile(0.75)
                iqr = q3 - q1
                borne_basse = q1 - k * iqr
                borne_haute = q3 + k * iqr
                mask_col = (df[col] < borne_basse) | (df[col] > borne_haute)
                stats_par_colonne.append({
                    "colonne":      col,
                    "methode":      "iqr",
                    "q1":           round(float(q1), 4),
                    "q3":           round(float(q3), 4),
                    "iqr":          round(float(iqr), 4),
                    "borne_basse":  round(float(borne_basse), 4),
                    "borne_haute":  round(float(borne_haute), 4),
                    "nb_outliers":  int(mask_col.sum()),
                    "pct_outliers": round(mask_col.sum() / len(df) * 100, 2),
                })
            else:  # zscore
                z = (df[col] - series.mean()) / series.std()
                mask_col = z.abs() > seuil_z
                stats_par_colonne.append({
                    "colonne":      col,
                    "methode":      "zscore",
                    "moyenne":      round(float(series.mean()), 4),
                    "ecart_type":   round(float(series.std()), 4),
                    "seuil_z":      seuil_z,
                    "nb_outliers":  int(mask_col.sum()),
                    "pct_outliers": round(mask_col.sum() / len(df) * 100, 2),
                })

            outlier_mask = outlier_mask | mask_col.fillna(False)

        outliers_df = df[outlier_mask].copy()

        if sauvegarder_sous:
            _DATASETS[sauvegarder_sous] = {
                "df":        outliers_df.reset_index(drop=True),
                "source":    f"df_outliers({nom})",
                "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        records, truncated = _df_to_records(outliers_df)

        return {
            "status":            "success",
            "nom":               nom,
            "methode":           methode,
            "nb_lignes_total":   len(df),
            "nb_outliers":       int(outlier_mask.sum()),
            "pct_outliers":      round(outlier_mask.sum() / len(df) * 100, 2) if len(df) else 0,
            "stats_par_colonne": stats_par_colonne,
            "tronque":           truncated,
            "sauvegarde_sous":   sauvegarder_sous,
            "lignes":            records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_outliers : {e}"}


@tool(
    name="df_concat",
    description=(
        "Empile plusieurs datasets verticalement (équivalent SQL UNION ALL). "
        "Les datasets doivent avoir des colonnes compatibles. "
        "Option pour ne garder que les colonnes communes (inner) ou toutes (outer avec NaN). "
        "Utile pour consolider plusieurs fichiers de même structure (ex: exports mensuels)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "noms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Liste des noms de datasets à empiler (dans l'ordre).",
            },
            "jointure": {
                "type": "string",
                "description": "'outer' (défaut, toutes les colonnes, NaN si absente) ou 'inner' (colonnes communes uniquement).",
            },
            "ajouter_colonne_source": {
                "type": "boolean",
                "description": "Si true, ajoute une colonne '_source' avec le nom du dataset d'origine (défaut: false).",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset résultat (obligatoire pour conserver le résultat).",
            },
        },
        "required": ["noms", "sauvegarder_sous"],
    },
)
def df_concat(
    noms: list,
    sauvegarder_sous: str,
    jointure: str = "outer",
    ajouter_colonne_source: bool = False,
) -> dict:
    if jointure not in ("inner", "outer"):
        return {"status": "error", "error": "jointure doit être 'inner' ou 'outer'."}
    if len(noms) < 2:
        return {"status": "error", "error": "Au moins 2 datasets sont nécessaires."}
    try:
        frames = []
        for n in noms:
            df_n = _get_df(n)  # lève KeyError si absent
            if ajouter_colonne_source:
                df_n = df_n.copy()
                df_n["_source"] = n
            frames.append(df_n)

        result = pd.concat(frames, axis=0, join=jointure, ignore_index=True)

        _DATASETS[sauvegarder_sous] = {
            "df":        result,
            "source":    f"df_concat({', '.join(noms)})",
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        records, truncated = _df_to_records(result)
        return {
            "status":          "success",
            "sources":         noms,
            "jointure":        jointure,
            "sauvegarde_sous": sauvegarder_sous,
            "nb_lignes":       len(result),
            "nb_colonnes":     len(result.columns),
            "tronque":         truncated,
            "colonnes":        list(result.columns),
            "lignes":          records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_concat : {e}"}


@tool(
    name="df_clean",
    description=(
        "Nettoie un dataset en une seule passe : "
        "gestion des valeurs manquantes (suppression ou imputation), "
        "suppression des doublons, "
        "renommage de colonnes, "
        "suppression de colonnes inutiles, "
        "suppression des espaces superflus dans les chaînes. "
        "Retourne un rapport détaillé des modifications effectuées."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset à nettoyer.",
            },
            "nan_strategie": {
                "type": "string",
                "description": (
                    "Stratégie pour les valeurs manquantes : "
                    "'supprimer_lignes' (supprime toute ligne avec au moins un NaN), "
                    "'supprimer_colonnes' (supprime les colonnes avec trop de NaN), "
                    "'imputer_moyenne' (remplace par la moyenne pour les numériques), "
                    "'imputer_mediane', 'imputer_mode', "
                    "'imputer_valeur' (utiliser nan_valeur), "
                    "'ignorer' (défaut, ne touche pas aux NaN)."
                ),
            },
            "nan_seuil_colonnes": {
                "type": "number",
                "description": "Pour 'supprimer_colonnes' : seuil de NaN (0.0-1.0) au-delà duquel supprimer la colonne (défaut: 0.5).",
            },
            "nan_valeur": {
                "type": "string",
                "description": "Valeur de remplacement pour 'imputer_valeur' (ex: '0', 'Inconnu').",
            },
            "deduplication": {
                "type": "boolean",
                "description": "Supprimer les lignes en double (défaut: false).",
            },
            "dedup_colonnes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes à considérer pour la détection des doublons (défaut: toutes).",
            },
            "strip_strings": {
                "type": "boolean",
                "description": "Supprimer les espaces en début/fin des chaînes (défaut: true).",
            },
            "supprimer_colonnes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Colonnes à supprimer du dataset.",
            },
            "renommer_colonnes": {
                "type": "object",
                "description": "Dictionnaire ancien_nom → nouveau_nom pour renommer des colonnes.",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset nettoyé (défaut: écrase le dataset source).",
            },
        },
        "required": ["nom"],
    },
)
def df_clean(
    nom: str,
    nan_strategie: str = "ignorer",
    nan_seuil_colonnes: float = 0.5,
    nan_valeur: Optional[str] = None,
    deduplication: bool = False,
    dedup_colonnes: Optional[list] = None,
    strip_strings: bool = True,
    supprimer_colonnes: Optional[list] = None,
    renommer_colonnes: Optional[dict] = None,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    NAN_STRATEGIES = {
        "ignorer", "supprimer_lignes", "supprimer_colonnes",
        "imputer_moyenne", "imputer_mediane", "imputer_mode", "imputer_valeur",
    }
    if nan_strategie not in NAN_STRATEGIES:
        return {"status": "error",
                "error": f"nan_strategie '{nan_strategie}' invalide. Valeurs : {sorted(NAN_STRATEGIES)}"}
    try:
        df = _get_df(nom).copy()
        rapport = []
        nb_lignes_init = len(df)
        nb_cols_init = len(df.columns)

        # ── Suppression de colonnes ──────────────────────────────────────
        if supprimer_colonnes:
            existantes = [c for c in supprimer_colonnes if c in df.columns]
            df = df.drop(columns=existantes)
            rapport.append(f"Colonnes supprimées : {existantes} ({len(existantes)})")

        # ── Renommage ────────────────────────────────────────────────────
        if renommer_colonnes:
            df = df.rename(columns=renommer_colonnes)
            rapport.append(f"Colonnes renommées : {renommer_colonnes}")

        # ── Strip strings ────────────────────────────────────────────────
        if strip_strings:
            str_cols = df.select_dtypes(include="object").columns
            for c in str_cols:
                df[c] = df[c].str.strip()
            if str_cols.any():
                rapport.append(f"Espaces supprimés sur {len(str_cols)} colonne(s) texte")

        # ── Valeurs manquantes ───────────────────────────────────────────
        nb_nan_avant = int(df.isna().sum().sum())
        if nan_strategie == "supprimer_lignes":
            df = df.dropna()
            rapport.append(f"Lignes avec NaN supprimées : {nb_lignes_init - len(df)}")
        elif nan_strategie == "supprimer_colonnes":
            seuil = nan_seuil_colonnes
            cols_a_suppr = [c for c in df.columns if df[c].isna().mean() > seuil]
            df = df.drop(columns=cols_a_suppr)
            rapport.append(f"Colonnes > {seuil*100:.0f}% NaN supprimées : {cols_a_suppr}")
        elif nan_strategie == "imputer_moyenne":
            num_cols = df.select_dtypes(include="number").columns
            df[num_cols] = df[num_cols].fillna(df[num_cols].mean())
            rapport.append(f"NaN imputés par la moyenne sur {len(num_cols)} colonne(s) numérique(s)")
        elif nan_strategie == "imputer_mediane":
            num_cols = df.select_dtypes(include="number").columns
            df[num_cols] = df[num_cols].fillna(df[num_cols].median())
            rapport.append(f"NaN imputés par la médiane sur {len(num_cols)} colonne(s) numérique(s)")
        elif nan_strategie == "imputer_mode":
            for c in df.columns:
                mode = df[c].mode()
                if not mode.empty:
                    df[c] = df[c].fillna(mode[0])
            rapport.append("NaN imputés par le mode sur toutes les colonnes")
        elif nan_strategie == "imputer_valeur":
            if nan_valeur is None:
                return {"status": "error", "error": "nan_valeur requis pour la stratégie 'imputer_valeur'."}
            df = df.fillna(nan_valeur)
            rapport.append(f"NaN remplacés par '{nan_valeur}'")

        nb_nan_apres = int(df.isna().sum().sum())
        if nan_strategie != "ignorer":
            rapport.append(f"NaN : {nb_nan_avant} → {nb_nan_apres}")

        # ── Déduplication ────────────────────────────────────────────────
        if deduplication:
            nb_avant = len(df)
            df = df.drop_duplicates(subset=dedup_colonnes or None, keep="first")
            nb_suppr = nb_avant - len(df)
            rapport.append(f"Doublons supprimés : {nb_suppr}")

        dest = sauvegarder_sous or nom
        _DATASETS[dest] = {
            "df":        df.reset_index(drop=True),
            "source":    f"df_clean({nom})",
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return {
            "status":          "success",
            "nom_source":      nom,
            "sauvegarde_sous": dest,
            "nb_lignes_avant": nb_lignes_init,
            "nb_lignes_apres": len(df),
            "nb_cols_avant":   nb_cols_init,
            "nb_cols_apres":   len(df.columns),
            "nb_nan_restants": nb_nan_apres,
            "rapport":         rapport,
            "message":         f"Nettoyage terminé : {len(rapport)} opération(s) effectuée(s).",
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_clean : {e}"}


@tool(
    name="df_cast",
    description=(
        "Convertit le type d'une ou plusieurs colonnes d'un dataset. "
        "Types supportés : 'int', 'float', 'str', 'bool', 'datetime', 'category'. "
        "Pour les dates, un format strftime peut être précisé (ex: '%d/%m/%Y'). "
        "Les valeurs non convertibles deviennent NaN (avec un avertissement)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset.",
            },
            "conversions": {
                "type": "object",
                "description": (
                    "Dictionnaire colonne → type cible. "
                    "Exemples : {'age': 'int', 'date_cmd': 'datetime', 'region': 'category'}. "
                    "Pour les dates avec format : {'date': {'type': 'datetime', 'format': '%d/%m/%Y'}}."
                ),
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset résultat (défaut: écrase le dataset source).",
            },
        },
        "required": ["nom", "conversions"],
    },
)
def df_cast(
    nom: str,
    conversions: dict,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    TYPES_VALIDES = {"int", "float", "str", "bool", "datetime", "category"}
    try:
        df = _get_df(nom).copy()
        rapport = []
        avertissements = []

        for col, type_cible in conversions.items():
            if col not in df.columns:
                return {"status": "error", "error": f"Colonne introuvable : '{col}'"}

            # Normaliser : accepte str ou dict {"type": ..., "format": ...}
            fmt = None
            if isinstance(type_cible, dict):
                fmt = type_cible.get("format")
                type_cible = type_cible.get("type", "")

            if type_cible not in TYPES_VALIDES:
                return {"status": "error",
                        "error": f"Type '{type_cible}' invalide pour '{col}'. Valides : {sorted(TYPES_VALIDES)}"}

            type_avant = str(df[col].dtype)
            try:
                if type_cible == "int":
                    df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                elif type_cible == "float":
                    df[col] = pd.to_numeric(df[col], errors="coerce")
                elif type_cible == "str":
                    df[col] = df[col].astype(str)
                elif type_cible == "bool":
                    df[col] = df[col].map(
                        lambda x: True if str(x).lower() in ("1", "true", "oui", "yes")
                        else (False if str(x).lower() in ("0", "false", "non", "no") else None)
                    )
                elif type_cible == "datetime":
                    df[col] = pd.to_datetime(df[col], format=fmt, errors="coerce", dayfirst=True)
                elif type_cible == "category":
                    df[col] = df[col].astype("category")

                nb_nan = int(df[col].isna().sum())
                rapport.append({
                    "colonne":     col,
                    "avant":       type_avant,
                    "apres":       str(df[col].dtype),
                    "nb_nan_apres": nb_nan,
                })
                if nb_nan > 0 and type_cible in ("int", "float", "datetime"):
                    avertissements.append(
                        f"'{col}' : {nb_nan} valeur(s) non convertible(s) → NaN"
                    )
            except Exception as e:
                return {"status": "error", "error": f"Erreur conversion colonne '{col}' : {e}"}

        dest = sauvegarder_sous or nom
        _DATASETS[dest] = {
            "df":        df,
            "source":    f"df_cast({nom})",
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return {
            "status":          "success",
            "nom_source":      nom,
            "sauvegarde_sous": dest,
            "conversions":     rapport,
            "avertissements":  avertissements,
            "message":         f"{len(rapport)} colonne(s) convertie(s).",
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_cast : {e}"}


@tool(
    name="df_apply",
    description=(
        "Crée de nouvelles colonnes calculées à partir d'expressions Python sur les colonnes existantes. "
        "Chaque expression a accès aux colonnes du dataset directement par leur nom. "
        "Variables spéciales disponibles : "
        "'today' / 'date_auj' (date du jour sans heure), 'now' (horodatage courant), "
        "'pd', 'np', 'cut', 'qcut', 'to_datetime', 'Timestamp', 'Timedelta'. "
        "Exemples généraux : "
        "'marge = (prix_vente - prix_achat) / prix_vente * 100', "
        "'nom_complet = prenom + \" \" + nom'. "
        "Exemples RH : "
        "'anciennete_ans = (today - date_entree).dt.days / 365.25', "
        "'age = (today - date_naissance).dt.days // 365', "
        "'tranche_age = cut(age, bins=[0,25,35,45,55,100], labels=[\"<25\",\"25-34\",\"35-44\",\"45-54\",\"55+\"])'."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset.",
            },
            "expressions": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Liste d'expressions de la forme 'nouvelle_colonne = expression'. "
                    "Les colonnes existantes sont accessibles directement par leur nom. "
                    "Exemples : ['ttc = ht * 1.2', 'ecart = valeur - moyenne', "
                    "'statut = \"ok\" if score > 0.5 else \"ko\"']."
                ),
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset résultat (défaut: écrase le dataset source).",
            },
        },
        "required": ["nom", "expressions"],
    },
)
def df_apply(
    nom: str,
    expressions: list,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    try:
        df = _get_df(nom).copy()
        rapport = []

        for expr in expressions:
            # Parser "nouvelle_col = expression"
            match = re.match(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$", expr.strip(), re.DOTALL)
            if not match:
                return {"status": "error",
                        "error": f"Expression invalide : '{expr}'. Format attendu : 'nom_colonne = expression'."}

            col_dest = match.group(1).strip()
            formule  = match.group(2).strip()

            # Construire le contexte d'évaluation avec les colonnes du df
            # et les bibliothèques utiles, y compris les fonctions de dates
            # nécessaires pour les calculs RH (ancienneté, âge, délais…)
            context = {col: df[col] for col in df.columns}
            context.update({
                # Bibliothèques
                "pd": pd, "np": np,
                # Builtins utiles
                "len": len, "abs": abs, "round": round, "min": min, "max": max,
                "int": int, "float": float, "str": str, "bool": bool,
                "sum": sum, "list": list,
                # Dates — essentiels pour les calculs RH
                "today":     pd.Timestamp.today().normalize(),
                "now":       pd.Timestamp.now(),
                "Timestamp": pd.Timestamp,
                "Timedelta": pd.Timedelta,
                "datetime":  datetime,
                "date_auj":  pd.Timestamp.today().normalize(),  # alias francophone
                # Fonctions pandas utiles
                "to_datetime": pd.to_datetime,
                "cut":         pd.cut,     # tranches (ex: tranches d'âge)
                "qcut":        pd.qcut,    # quartiles
                "isna":        pd.isna,
                "notna":       pd.notna,
            })

            try:
                result = eval(formule, {"__builtins__": {}}, context)  # noqa: S307
                df[col_dest] = result
                rapport.append({
                    "colonne_cree": col_dest,
                    "expression":  formule,
                    "type":        str(df[col_dest].dtype),
                })
            except Exception as e:
                return {"status": "error",
                        "error": f"Erreur dans l'expression '{expr}' : {e}"}

        dest = sauvegarder_sous or nom
        _DATASETS[dest] = {
            "df":        df,
            "source":    f"df_apply({nom})",
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        records, truncated = _df_to_records(df)
        return {
            "status":          "success",
            "nom_source":      nom,
            "sauvegarde_sous": dest,
            "colonnes_creees": rapport,
            "nb_lignes":       len(df),
            "nb_colonnes":     len(df.columns),
            "tronque":         truncated,
            "colonnes":        list(df.columns),
            "lignes":          records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_apply : {e}"}


@tool(
    name="df_rename",
    description=(
        "Renomme une ou plusieurs colonnes d'un dataset. "
        "Plus direct que df_clean pour un simple renommage."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset.",
            },
            "renommage": {
                "type": "object",
                "description": "Dictionnaire ancien_nom → nouveau_nom. Ex: {'CA HT': 'ca_ht', 'Nb clients': 'nb_clients'}.",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset résultat (défaut: écrase le dataset source).",
            },
        },
        "required": ["nom", "renommage"],
    },
)
def df_rename(
    nom: str,
    renommage: dict,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    try:
        df = _get_df(nom)
        manquantes = [c for c in renommage if c not in df.columns]
        if manquantes:
            return {"status": "error",
                    "error": f"Colonnes introuvables : {manquantes}. "
                             f"Colonnes disponibles : {list(df.columns)}"}

        df = df.rename(columns=renommage)
        dest = sauvegarder_sous or nom
        _DATASETS[dest] = {
            "df":        df,
            "source":    f"df_rename({nom})",
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return {
            "status":          "success",
            "nom_source":      nom,
            "sauvegarde_sous": dest,
            "renommage":       renommage,
            "colonnes":        list(df.columns),
            "message":         f"{len(renommage)} colonne(s) renommée(s).",
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_rename : {e}"}


@tool(
    name="df_sample",
    description=(
        "Extrait un échantillon aléatoire ou stratifié d'un dataset. "
        "Utile pour travailler sur un sous-ensemble représentatif avant des calculs lourds, "
        "ou pour préparer des jeux de test. "
        "L'échantillonnage stratifié garantit la représentation proportionnelle d'une variable catégorielle."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset source.",
            },
            "n": {
                "type": "integer",
                "description": "Nombre de lignes à échantillonner (exclusif avec 'fraction').",
            },
            "fraction": {
                "type": "number",
                "description": "Fraction des lignes à échantillonner, entre 0 et 1 (ex: 0.1 = 10%).",
            },
            "stratifier_par": {
                "type": "string",
                "description": "Colonne catégorielle pour l'échantillonnage stratifié.",
            },
            "graine": {
                "type": "integer",
                "description": "Graine aléatoire pour la reproductibilité (défaut: None).",
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset résultat (obligatoire pour conserver l'échantillon).",
            },
        },
        "required": ["nom"],
    },
)
def df_sample(
    nom: str,
    n: Optional[int] = None,
    fraction: Optional[float] = None,
    stratifier_par: Optional[str] = None,
    graine: Optional[int] = None,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    if n is None and fraction is None:
        return {"status": "error", "error": "Spécifier 'n' (nombre) ou 'fraction' (ex: 0.1)."}
    if n is not None and fraction is not None:
        return {"status": "error", "error": "'n' et 'fraction' sont mutuellement exclusifs."}
    if fraction is not None and not (0 < fraction < 1):
        return {"status": "error", "error": "'fraction' doit être entre 0 et 1 (exclus)."}
    try:
        df = _get_df(nom)

        if stratifier_par:
            if stratifier_par not in df.columns:
                return {"status": "error",
                        "error": f"Colonne de stratification introuvable : '{stratifier_par}'"}

            # Échantillonnage stratifié : proportionnel par groupe
            frac = fraction if fraction else (n / len(df))
            frac = min(frac, 1.0)
            sample = df.groupby(stratifier_par, group_keys=False).apply(
                lambda x: x.sample(frac=frac, random_state=graine)
            )
            if n is not None:
                sample = sample.head(n)
        else:
            if n is not None:
                n = min(n, len(df))
            sample = df.sample(n=n, frac=fraction, random_state=graine)

        sample = sample.reset_index(drop=True)

        if sauvegarder_sous:
            _DATASETS[sauvegarder_sous] = {
                "df":        sample,
                "source":    f"df_sample({nom})",
                "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        records, truncated = _df_to_records(sample)
        return {
            "status":           "success",
            "nom_source":       nom,
            "nb_lignes_source": len(df),
            "nb_lignes_sample": len(sample),
            "fraction_reelle":  round(len(sample) / len(df), 4) if len(df) else 0,
            "stratifie_par":    stratifier_par,
            "sauvegarde_sous":  sauvegarder_sous,
            "tronque":          truncated,
            "colonnes":         list(sample.columns),
            "lignes":           records,
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_sample : {e}"}



@tool(
    name="df_write",
    description=(
        "Exporte un dataset en CSV ou Excel. "
        "Pour Excel, possibilité d'écrire plusieurs datasets dans des feuilles séparées. "
        "Le fichier est créé ou écrasé à l'emplacement indiqué."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset à exporter.",
            },
            "destination": {
                "type": "string",
                "description": "Chemin du fichier de sortie (.csv, .xlsx). Défaut : ~/export_<nom>_<timestamp>.csv",
            },
            "format": {
                "type": "string",
                "description": "Format de sortie : 'csv' (défaut si .csv) ou 'excel' (défaut si .xlsx).",
            },
            "separateur": {
                "type": "string",
                "description": "Séparateur CSV (défaut: ',').",
            },
            "inclure_index": {
                "type": "boolean",
                "description": "Inclure l'index pandas dans l'export (défaut: false).",
            },
            "feuille": {
                "type": "string",
                "description": "Nom de la feuille Excel (défaut: nom du dataset).",
            },
            "datasets_supplementaires": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Autres datasets à inclure comme feuilles supplémentaires (Excel uniquement).",
            },
        },
        "required": ["nom"],
    },
)
def df_write(
    nom: str,
    destination: Optional[str] = None,
    format: Optional[str] = None,
    separateur: str = ",",
    inclure_index: bool = False,
    feuille: Optional[str] = None,
    datasets_supplementaires: Optional[list] = None,
) -> dict:
    try:
        df = _get_df(nom)

        # Déterminer le format et le chemin
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if destination:
            dest = Path(destination).expanduser()
            fmt = format or ("excel" if dest.suffix.lower() in (".xlsx", ".xls") else "csv")
        else:
            fmt = format or "csv"
            ext = ".xlsx" if fmt == "excel" else ".csv"
            dest = Path.home() / f"export_{nom}_{ts}{ext}"

        dest.parent.mkdir(parents=True, exist_ok=True)

        t0 = time.perf_counter()

        if fmt == "csv":
            df.to_csv(dest, sep=separateur, index=inclure_index, encoding="utf-8-sig")
            nb_lignes = len(df)

        elif fmt == "excel":
            sheet_name = feuille or nom[:31]  # Excel limite les noms à 31 chars
            with pd.ExcelWriter(dest, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=inclure_index)
                if datasets_supplementaires:
                    for ds_nom in datasets_supplementaires:
                        if ds_nom in _DATASETS:
                            ds_df = _DATASETS[ds_nom]["df"]
                            ds_df.to_excel(writer, sheet_name=ds_nom[:31], index=inclure_index)
            nb_lignes = len(df)

        else:
            return {"status": "error", "error": f"Format inconnu : '{fmt}'. Utilisez 'csv' ou 'excel'."}

        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        taille = dest.stat().st_size
        taille_str = f"{taille / 1024:.1f} Ko" if taille < 1_048_576 else f"{taille / 1_048_576:.2f} Mo"

        return {
            "status":    "success",
            "nom":       nom,
            "fichier":   str(dest),
            "format":    fmt,
            "nb_lignes": nb_lignes,
            "taille":    taille_str,
            "duree_ms":  elapsed_ms,
            "message":   f"Dataset '{nom}' exporté dans {dest.name} ({taille_str}).",
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except PermissionError:
        return {"status": "error", "error": f"Permission refusée pour écrire dans : {dest}"}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_write : {e}"}


@tool(
    name="df_anonymize",
    description=(
        "Anonymise ou pseudonymise un dataset pour la conformité RGPD. "
        "Opérations disponibles par colonne : "
        "'supprimer' (retire la colonne), "
        "'hacher' (SHA-256 irréversible, conserve la cohérence pour les jointures), "
        "'pseudonymiser' (remplace par un identifiant opaque reproductible — même valeur = même pseudo), "
        "'masquer' (remplace par '***'), "
        "'generaliser_date' (conserve uniquement l'année ou année+mois), "
        "'generaliser_nombre' (arrondit à la dizaine, centaine, etc.), "
        "'bruit_gaussien' (ajoute un bruit aléatoire sur les numériques — irréversible). "
        "Utile avant de partager un fichier RH, de l'ingérer dans le RAG ou de l'envoyer à une API externe."
    ),
    parameters={
        "type": "object",
        "properties": {
            "nom": {
                "type": "string",
                "description": "Nom du dataset à anonymiser.",
            },
            "operations": {
                "type": "object",
                "description": (
                    "Dictionnaire colonne → opération (str) ou config (dict). "
                    "Exemples : "
                    "{'nom': 'supprimer', 'email': 'hacher', 'nir': 'pseudonymiser', "
                    "'salaire': 'masquer', 'date_naissance': {'op': 'generaliser_date', 'precision': 'annee'}, "
                    "'age': {'op': 'generaliser_nombre', 'arrondi': 10}, "
                    "'revenu': {'op': 'bruit_gaussien', 'ecart_type': 0.05}}."
                ),
            },
            "sel": {
                "type": "string",
                "description": (
                    "Sel (secret) utilisé pour le hachage et la pseudonymisation. "
                    "Si omis, un sel aléatoire est généré (non reproductible entre sessions). "
                    "À conserver précieusement si la cohérence entre datasets est nécessaire."
                ),
            },
            "sauvegarder_sous": {
                "type": "string",
                "description": "Nom du dataset anonymisé (défaut: <nom>_anon).",
            },
        },
        "required": ["nom", "operations"],
    },
)
def df_anonymize(
    nom: str,
    operations: dict,
    sel: Optional[str] = None,
    sauvegarder_sous: Optional[str] = None,
) -> dict:
    import hashlib
    import secrets

    OPS_VALIDES = {
        "supprimer", "hacher", "pseudonymiser", "masquer",
        "generaliser_date", "generaliser_nombre", "bruit_gaussien",
    }

    try:
        df = _get_df(nom).copy()
        rapport = []
        avertissements = []

        # Sel pour hachage/pseudonymisation
        sel_effectif = sel or secrets.token_hex(16)
        if not sel:
            avertissements.append(
                "Aucun sel fourni : sel aléatoire généré. "
                "La pseudonymisation ne sera pas reproductible entre sessions. "
                "Fournir un paramètre 'sel' si la cohérence est nécessaire."
            )

        for col, config in operations.items():
            if col not in df.columns:
                return {"status": "error", "error": f"Colonne introuvable : '{col}'"}

            # Normaliser config
            if isinstance(config, str):
                op = config
                params: dict = {}
            elif isinstance(config, dict):
                op = config.get("op", "")
                params = {k: v for k, v in config.items() if k != "op"}
            else:
                return {"status": "error", "error": f"Configuration invalide pour '{col}'."}

            if op not in OPS_VALIDES:
                return {"status": "error",
                        "error": f"Opération '{op}' invalide pour '{col}'. "
                                 f"Valides : {sorted(OPS_VALIDES)}"}

            if op == "supprimer":
                df = df.drop(columns=[col])
                rapport.append({"colonne": col, "operation": "supprimée"})

            elif op in ("hacher", "pseudonymiser"):
                # SHA-256 avec sel — même entrée = même sortie (cohérence jointures)
                prefix = "P" if op == "pseudonymiser" else "H"
                def _hash(val, _sel=sel_effectif, _prefix=prefix):
                    if pd.isna(val):
                        return None
                    h = hashlib.sha256(f"{_sel}:{val}".encode()).hexdigest()[:12]
                    return f"{_prefix}_{h}"
                df[col] = df[col].apply(_hash)
                rapport.append({"colonne": col, "operation": op,
                                 "note": "SHA-256 avec sel, reproductible"})

            elif op == "masquer":
                df[col] = df[col].apply(lambda v: None if pd.isna(v) else "***")
                rapport.append({"colonne": col, "operation": "masquée"})

            elif op == "generaliser_date":
                precision = params.get("precision", "annee")  # 'annee' ou 'mois'
                try:
                    dates = pd.to_datetime(df[col], errors="coerce")
                    if precision == "mois":
                        df[col] = dates.dt.to_period("M").astype(str)
                        df[col] = df[col].where(dates.notna(), None)
                    else:
                        df[col] = dates.dt.year.astype("Int64")
                    rapport.append({"colonne": col, "operation": f"date généralisée à l'{precision}"})
                except Exception as e:
                    avertissements.append(f"'{col}' : erreur généralisation date — {e}")

            elif op == "generaliser_nombre":
                arrondi = int(params.get("arrondi", 10))
                try:
                    df[col] = (pd.to_numeric(df[col], errors="coerce") / arrondi).round(0) * arrondi
                    rapport.append({"colonne": col, "operation": f"arrondi à {arrondi}"})
                except Exception as e:
                    avertissements.append(f"'{col}' : erreur généralisation nombre — {e}")

            elif op == "bruit_gaussien":
                ecart = float(params.get("ecart_type", 0.05))
                try:
                    num = pd.to_numeric(df[col], errors="coerce")
                    bruit = np.random.normal(0, ecart * num.abs().mean(), size=len(num))
                    df[col] = (num + bruit).where(num.notna(), None)
                    rapport.append({"colonne": col, "operation": f"bruit gaussien σ={ecart*100:.1f}% de la moyenne"})
                except Exception as e:
                    avertissements.append(f"'{col}' : erreur bruit gaussien — {e}")

        dest = sauvegarder_sous or f"{nom}_anon"
        _DATASETS[dest] = {
            "df":        df.reset_index(drop=True),
            "source":    f"df_anonymize({nom})",
            "loaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        return {
            "status":          "success",
            "nom_source":      nom,
            "sauvegarde_sous": dest,
            "nb_lignes":       len(df),
            "nb_colonnes":     len(df.columns),
            "operations":      rapport,
            "avertissements":  avertissements,
            "sel_utilise":     "fourni" if sel else "aléatoire (non reproductible)",
            "message":         f"{len(rapport)} colonne(s) anonymisée(s). "
                               "Vérifier le résultat avant tout partage.",
        }

    except KeyError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"Erreur df_anonymize : {e}"}



@tool(
    name="df_drop",
    description=(
        "Supprime un ou plusieurs datasets de la mémoire session pour libérer des ressources. "
        "Les fichiers sources ne sont pas modifiés."
    ),
    parameters={
        "type": "object",
        "properties": {
            "noms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Liste des noms de datasets à supprimer.",
            },
        },
        "required": ["noms"],
    },
)
def df_drop(noms: list) -> dict:
    supprimes = []
    introuvables = []
    for nom in noms:
        if nom in _DATASETS:
            del _DATASETS[nom]
            supprimes.append(nom)
        else:
            introuvables.append(nom)

    return {
        "status":       "success",
        "supprimes":    supprimes,
        "introuvables": introuvables,
        "restants":     list(_DATASETS.keys()),
        "message":      f"{len(supprimes)} dataset(s) supprimé(s) de la mémoire.",
    }
