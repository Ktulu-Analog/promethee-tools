# Conventions et bonnes pratiques

Ce document définit les règles partagées par tous les modules d'outils Prométhée.

---

## Nommage

### Modules

| Convention | Exemple |
|---|---|
| `<domaine>_tools.py` | `data_file_tools.py`, `sql_tools.py` |
| Toujours suffixé `_tools` | ✅ `legifrance_tools.py` / ❌ `legifrance.py` |
| snake_case | ✅ `datagouv_tools.py` / ❌ `DataGouvTools.py` |

### Outils (`name`)

| Convention | Exemple |
|---|---|
| Préfixe du domaine | `df_`, `sql_`, `web_`, `tb_`, `grist_` |
| Verbe ou verbe + nom | `df_read`, `sql_query`, `web_fetch` |
| snake_case strict | ✅ `df_value_counts` / ❌ `df_valueCounts` |
| Unique dans toute l'application | Vérifier avant d'ajouter |

### Fonctions helpers privées

Préfixées d'un `_` :

```python
def _detect_encoding(path):  ...   # ✅ privé
def detect_encoding(path):   ...   # ❌ visible dans l'espace de noms
```

---

## Structure d'un fichier

Ordre obligatoire :

```python
# 1. En-tête licence
# 2. Docstring du module
# 3. Imports stdlib
# 4. Imports tiers (pandas, requests…)
# 5. Import core.tools_engine
# 6. set_current_family()
# 7. _TOOL_ICONS.update(...)
# 8. Constantes du module
# 9. État de session (dict global _NOM)
# 10. Helpers privés (_fonctions)
# 11. Outils (@tool décorés)
```

---

## Descriptions

### Longueur cible

- Outil simple : 1-3 phrases
- Outil complexe / multi-modes : 4-8 phrases + exemples

### Structure recommandée

```
[Ce que fait l'outil.] [Cas d'usage / quand l'utiliser.] [Paramètres importants et valeurs.] [Exemples concrets.]
```

### Exemples dans les descriptions

Toujours inclure des exemples pour les outils qui acceptent des expressions :

```python
# ✅ Avec exemples
description=(
    "Filtre un dataset avec une expression pandas. "
    "Exemples : 'age > 30 and ville == \"Paris\"', "
    "'salaire.between(30000, 60000)', "
    "'nom.str.startswith(\"Du\")'."
),

# ❌ Sans exemples
description="Filtre un dataset avec une expression pandas.",
```

---

## Paramètres

### Nommage des paramètres

Utiliser le français pour les paramètres exposés au LLM (cohérence avec les autres modules) :

```python
# ✅ Cohérent avec le reste
def df_query(nom, filtre, colonnes, trier_par, ordre_desc, sauvegarder_sous): ...

# ❌ Mélange
def df_query(name, filter_expr, columns, sort_by, descending, save_as): ...
```

### Paramètres `sauvegarder_sous`

Convention partagée par tous les outils de transformation : si fourni, persiste le résultat comme nouveau dataset. Si absent, retourne uniquement les données (sans persistance).

### Limites de taille

Pour tout outil retournant des listes potentiellement longues, définir une limite avec constante :

```python
_MAX_ROWS_DISPLAY = 100   # lignes max retournées en JSON

@tool(name="df_query", ...)
def df_query(..., limite: int = _MAX_ROWS_DISPLAY) -> dict:
    limite = min(max(1, limite), _MAX_ROWS_DISPLAY)  # clamp
```

---

## Valeurs de retour

### Champs standard par type d'outil

**Outils de lecture** :
```python
{
    "status":      "success",
    "nom":         "...",           # identifiant de la ressource
    "nb_lignes":   int,
    "nb_colonnes": int,
    "colonnes":    list[str],
    "duree_ms":    float,
    "message":     "...",           # résumé humain
}
```

**Outils de transformation** :
```python
{
    "status":          "success",
    "nom_source":      "...",       # dataset d'entrée
    "sauvegarde_sous": "..." | None,
    "nb_lignes":       int,
    "nb_colonnes":     int,
    "tronque":         bool,        # true si résultat tronqué
    "colonnes":        list[str],
    "lignes":          list[dict],  # données (tronquées si > _MAX_ROWS_DISPLAY)
}
```

**Outils d'écriture / action** :
```python
{
    "status":   "success",
    "fichier":  "...",              # chemin absolu du fichier créé
    "taille":   "1.2 Mo",
    "duree_ms": float,
    "message":  "...",
}
```

**Erreurs** :
```python
{
    "status": "error",
    "error":  "Message clair. Conseil pour corriger. Valeurs attendues si enum.",
}
```

### Sérialisation JSON

Tous les champs doivent être JSON-sérialisables. Normaliser systématiquement :

| Type Python | Normaliser en |
|---|---|
| `numpy.int64` | `int(val)` |
| `numpy.float64` | `float(val)` |
| `numpy.bool_` | `bool(val)` |
| `pandas.Timestamp` | `val.isoformat()` |
| `pandas.NaT` | `None` |
| `float("nan")` | `None` |
| `float("inf")` | `None` |
| `numpy.ndarray` | `val.tolist()` |
| `bytes` | `f"<bytes {len(val)}>"` |

Utiliser le helper `_safe()` de `data_file_tools.py` comme référence.

---

## Gestion des erreurs

### Règle des trois niveaux

```python
try:
    # Validation des entrées
    if colonne not in df.columns:
        return {"status": "error",
                "error": f"Colonne '{colonne}' introuvable. "
                         f"Colonnes disponibles : {list(df.columns)}."}

    # Traitement principal
    try:
        resultat = operation_specifique()
    except SpecificError as e:
        return {"status": "error", "error": f"Erreur spécifique : {e}"}

except Exception as e:
    return {"status": "error", "error": f"Erreur inattendue dans mon_outil : {e}"}
```

### Messages d'erreur actionnables

Chaque message doit répondre à : **que faire pour corriger ?**

```python
# ❌ Pas actionnable
"error": "Dataset introuvable."

# ✅ Actionnable
"error": (
    f"Dataset '{nom}' introuvable. "
    f"Datasets disponibles : {list(_DATASETS.keys())}. "
    "Utilisez df_read pour charger un fichier."
)
```

---

## Icônes

Choisir une icône cohérente avec le type d'action :

| Action | Icône suggérée |
|---|---|
| Lire / charger | 📂 📥 |
| Lister / inventorier | 📋 |
| Afficher / explorer | 👁️ |
| Analyser / statistiques | 📊 📈 |
| Filtrer / rechercher | 🔍 |
| Transformer | 🔄 ⚙️ |
| Nettoyer | 🧹 |
| Fusionner / joindre | 🔗 |
| Empiler | 📎 |
| Calculer | ➗ 🔢 |
| Exporter / écrire | 💾 📤 |
| Supprimer | 🗑️ |
| Sécuriser / anonymiser | 🔒 |
| Alerter / détecter | ⚠️ |
| Aléatoire | 🎲 |
| Date / temps | 📅 ⏱️ |

---

## Dépendances

### Déclarer dans le docstring

```python
"""
...
Prérequis :
    pip install pandas openpyxl         # obligatoire
    pip install xlrd                    # optionnel, pour .xls ancien format
"""
```

### Imports conditionnels pour les dépendances optionnelles

```python
try:
    import pytesseract
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

def ocr_image(chemin: str) -> dict:
    if not _OCR_AVAILABLE:
        return {
            "status": "error",
            "error": "pytesseract non installé. Installer avec : pip install pytesseract"
        }
    ...
```

---

## Sécurité

### `eval()` et `exec()`

Utiliser uniquement pour des outils explicitement conçus pour l'exécution de code (`python_tools`, `df_apply`). Toujours :
- Restreindre les builtins : `{"__builtins__": {}}`
- Documenter le risque dans le docstring
- Ne jamais exposer `os`, `subprocess`, `open` dans le contexte

### Secrets et credentials

- Jamais de credentials dans le code ou les tests
- Toujours passer par `core.config.Config` / `.env`
- Les clés API ne doivent jamais apparaître dans les retours JSON

### Chemins de fichiers

Toujours utiliser `Path(...).expanduser()` et vérifier l'existence avant traitement :

```python
path = Path(chemin).expanduser()
if not path.exists():
    return {"status": "error", "error": f"Fichier introuvable : {chemin}"}
```
