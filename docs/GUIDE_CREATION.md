# Guide de création d'un module d'outils

Ce guide explique comment écrire un nouveau module `*_tools.py` compatible avec Prométhée, de zéro jusqu'à l'intégration.

---

## Sommaire

1. [Structure d'un module](#1-structure-dun-module)
2. [Le décorateur @tool](#2-le-décorateur-tool)
3. [Décrire les paramètres (JSON Schema)](#3-décrire-les-paramètres-json-schema)
4. [La fonction Python](#4-la-fonction-python)
5. [Valeurs de retour](#5-valeurs-de-retour)
6. [Gérer un état de session](#6-gérer-un-état-de-session)
7. [Appels HTTP et APIs externes](#7-appels-http-et-apis-externes)
8. [Variables d'environnement](#8-variables-denvironnement)
9. [Exemple complet annoté](#9-exemple-complet-annoté)
10. [Checklist avant commit](#10-checklist-avant-commit)

---

## 1. Structure d'un module

```
tools/
└── mon_module_tools.py   ← un fichier = un module = une famille d'outils
```

Structure minimale d'un fichier :

```python
# En-tête licence (obligatoire, copier depuis un fichier existant)
# ============================================================================
# Prométhée — Assistant IA desktop
# ...
# ============================================================================

"""
tools/mon_module_tools.py — Description courte
===============================================

Outils exposés (N) :
  - outil_un   : ce qu'il fait
  - outil_deux : ce qu'il fait

Prérequis :
    pip install ma-dependance
"""

from typing import Optional
from core.tools_engine import tool, set_current_family, _TOOL_ICONS

# Déclarer la famille — apparaît dans l'UI de Prométhée
set_current_family("mon_module_tools", "Nom affiché dans l'UI", "🔧")

# Icônes par outil (optionnel mais recommandé)
_TOOL_ICONS.update({
    "outil_un":   "🔧",
    "outil_deux": "🔨",
})

# ── État de session (si nécessaire) ─────────────────────────────────────────
_MON_ETAT: dict = {}

# ── Helpers privés ──────────────────────────────────────────────────────────
def _ma_fonction_interne(x):
    ...

# ── Outils ──────────────────────────────────────────────────────────────────

@tool(name="outil_un", description="...", parameters={...})
def outil_un(...) -> dict:
    ...
```

---

## 2. Le décorateur @tool

```python
@tool(
    name="outil_un",           # identifiant unique, snake_case
    description="...",         # texte lu par le LLM pour décider d'appeler l'outil
    parameters={...},          # JSON Schema des paramètres
)
def outil_un(param1: str, param2: int = 10) -> dict:
    ...
```

### Règles de nommage

- `name` : snake_case, préfixé par le domaine. Ex : `df_`, `sql_`, `web_`, `tb_`
- Les noms doivent être **uniques dans toute l'application** (vérifier les autres modules)
- La fonction Python doit avoir le **même nom** que `name`

### La description — point le plus critique

La description est le seul signal que le LLM utilise pour choisir quand et comment appeler l'outil. Elle doit répondre à :
- **Quoi** : que fait cet outil ?
- **Quand** : dans quel cas l'utiliser ?
- **Comment** : quels paramètres clés ? quelles valeurs possibles ?
- **Exemples** : cas d'usage concrets (recommandé)

```python
# ✅ Bonne description
description=(
    "Recherche des jeux de données sur data.gouv.fr par mots-clés. "
    "Retourne les titres, descriptions et identifiants des résultats. "
    "À utiliser quand l'utilisateur cherche des données publiques françaises. "
    "Exemple : 'population communes', 'accidents routiers 2023'."
),

# ❌ Description trop courte
description="Recherche sur data.gouv.fr.",
```

---

## 3. Décrire les paramètres (JSON Schema)

```python
parameters={
    "type": "object",
    "properties": {
        "query": {
            "type": "string",                          # type : string, integer, number, boolean, array, object
            "description": "Mots-clés de recherche.",  # description du paramètre (lue par le LLM)
        },
        "limite": {
            "type": "integer",
            "description": "Nombre max de résultats (défaut: 10).",
        },
        "formats": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Filtrer par format : 'csv', 'xlsx', 'json'.",
        },
        "type_recherche": {
            "type": "string",
            "description": "Mode : 'exact' ou 'fuzzy' (défaut: 'fuzzy').",
            "enum": ["exact", "fuzzy"],                # valeurs autorisées
        },
    },
    "required": ["query"],   # paramètres obligatoires
}
```

### Types courants

| Type JSON Schema | Python | Exemple |
|---|---|---|
| `string` | `str` | `"Paris"` |
| `integer` | `int` | `42` |
| `number` | `float` | `3.14` |
| `boolean` | `bool` | `true` |
| `array` | `list` | `["a", "b"]` |
| `object` | `dict` | `{"cle": "val"}` |

### Signature Python correspondante

La signature de la fonction doit **correspondre exactement** aux paramètres déclarés :

```python
@tool(name="rechercher", description="...", parameters={
    "type": "object",
    "properties": {
        "query":   {"type": "string"},
        "limite":  {"type": "integer"},
        "formats": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["query"],
})
def rechercher(
    query: str,
    limite: int = 10,
    formats: Optional[list] = None,
) -> dict:
    ...
```

---

## 4. La fonction Python

### Imports utiles

```python
from typing import Optional, Any
from pathlib import Path
import time
from datetime import datetime
```

### Pattern standard

```python
def mon_outil(param_requis: str, param_optionnel: int = 10) -> dict:
    # 1. Valider les entrées
    if not param_requis.strip():
        return {"status": "error", "error": "param_requis ne peut pas être vide."}

    # 2. Traitement
    try:
        t0 = time.perf_counter()
        resultat = faire_quelque_chose(param_requis)
        duree_ms = round((time.perf_counter() - t0) * 1000, 1)

        # 3. Retourner
        return {
            "status":   "success",
            "duree_ms": duree_ms,
            "resultat": resultat,
        }

    except MaException as e:
        return {"status": "error", "error": f"Erreur spécifique : {e}"}
    except Exception as e:
        return {"status": "error", "error": f"Erreur inattendue : {e}"}
```

---

## 5. Valeurs de retour

### Format obligatoire

Toujours un `dict` avec au minimum `"status"` :

```python
# Succès
{"status": "success", ...}

# Erreur
{"status": "error", "error": "Message clair et actionnable."}
```

### Bonnes pratiques

- Toujours inclure un champ `"message"` humainement lisible pour les succès
- Inclure `"duree_ms"` pour les opérations I/O
- Tronquer les résultats longs avec un indicateur `"tronque": true`
- **Jamais de valeurs non JSON-sérialisables** : `NaN`, `Timestamp`, `numpy.int64`… → les normaliser

```python
# ❌ Plante la sérialisation JSON
return {"valeur": float("nan"), "date": pd.Timestamp.now()}

# ✅ Normalisé
return {"valeur": None, "date": pd.Timestamp.now().isoformat()}
```

### Messages d'erreur utiles

```python
# ❌ Pas utile
return {"status": "error", "error": "Erreur"}

# ✅ Actionnable
return {
    "status": "error",
    "error": (
        f"Connexion '{nom_conn}' introuvable. "
        f"Connexions disponibles : {list(_CONNECTIONS.keys())}. "
        "Utilisez sql_connect pour ouvrir une connexion."
    )
}
```

---

## 6. Gérer un état de session

Certains outils maintiennent un état en mémoire entre les appels (connexions ouvertes, datasets chargés…). Utiliser un **dictionnaire global privé** :

```python
# État de session (réinitialisé à chaque démarrage de Prométhée)
_CONNECTIONS: dict[str, Any] = {}

@tool(name="sql_connect", ...)
def sql_connect(nom: str, url: str) -> dict:
    _CONNECTIONS[nom] = creer_connexion(url)
    return {"status": "success", "nom": nom}

@tool(name="sql_query", ...)
def sql_query(connexion: str, requete: str) -> dict:
    if connexion not in _CONNECTIONS:
        return {"status": "error",
                "error": f"Connexion '{connexion}' introuvable. "
                         f"Utilisez sql_connect d'abord."}
    ...
```

---

## 7. Appels HTTP et APIs externes

```python
import requests

def _appel_api(url: str, params: dict, timeout: int = 15) -> dict:
    """Helper réutilisable pour les appels HTTP."""
    try:
        r = requests.get(url, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.Timeout:
        raise RuntimeError(f"Timeout après {timeout}s : {url}")
    except requests.HTTPError as e:
        raise RuntimeError(f"HTTP {e.response.status_code} : {url}")
    except Exception as e:
        raise RuntimeError(f"Erreur réseau : {e}")
```

Pour les APIs avec authentification OAuth2, voir `legifrance_tools.py` comme référence.

---

## 8. Variables d'environnement

Utiliser `core.config.Config` pour accéder au `.env` de Prométhée :

```python
from core.config import Config

# Dans la fonction
api_key = getattr(Config, "MON_API_KEY", None)
if not api_key:
    return {
        "status": "error",
        "error": "MON_API_KEY non configurée. Ajouter dans le fichier .env."
    }
```

Documenter les variables dans le docstring du module et dans `.env.example` du projet principal.

---

## 9. Exemple complet annoté

Voir [tools/datagouv_tools.py](../tools/datagouv_tools.py) pour un exemple réel d'API publique sans authentification.

Voir [tools/legifrance_tools.py](../tools/legifrance_tools.py) pour OAuth2 + pagination + cache.

Voir [tools/data_file_tools.py](../tools/data_file_tools.py) pour état de session + transformation de données.

---

## 10. Checklist avant commit

- [ ] En-tête licence présent
- [ ] Docstring du module à jour (liste des outils, prérequis pip)
- [ ] `set_current_family()` appelé avec emoji
- [ ] Icônes déclarées dans `_TOOL_ICONS`
- [ ] Descriptions assez longues et avec exemples
- [ ] Paramètres `required` corrects (pas de paramètre optionnel en `required`)
- [ ] Signature Python cohérente avec le JSON Schema
- [ ] Toutes les sorties JSON-sérialisables (pas de NaN, Timestamp brut…)
- [ ] `{"status": "error", "error": "..."}` sur tous les chemins d'erreur
- [ ] Messages d'erreur actionnables (que faire pour corriger ?)
- [ ] Pas de `print()` dans le code (utiliser le retour JSON)
- [ ] Testé avec `scripts/test_tool.py` (voir [GUIDE_TEST.md](GUIDE_TEST.md))
- [ ] Module ajouté dans `tools/__init__.py` → `register_all()`
