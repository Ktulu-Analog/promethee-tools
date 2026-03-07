# Guide de test des outils

Les outils sont des fonctions Python pures (ou presque). Ils se testent directement, sans lancer Prométhée.

---

## Sommaire

1. [Prérequis](#1-prérequis)
2. [Test rapide en ligne de commande](#2-test-rapide-en-ligne-de-commande)
3. [Test interactif (script Python)](#3-test-interactif-script-python)
4. [Écrire des tests unitaires](#4-écrire-des-tests-unitaires)
5. [Tester les outils avec état de session](#5-tester-les-outils-avec-état-de-session)
6. [Tester les outils qui appellent des APIs](#6-tester-les-outils-qui-appellent-des-apis)
7. [Vérifier la cohérence JSON Schema / signature](#7-vérifier-la-cohérence-json-schema--signature)

---

## 1. Prérequis

Les outils nécessitent `core.tools_engine` de Prométhée. Deux options :

### Option A — Depuis le répertoire Prométhée (recommandé)

```bash
cd /chemin/vers/promethee
python -c "from tools import data_file_tools; print('OK')"
```

### Option B — Stub minimal (sans Prométhée)

Créer un fichier `core/tools_engine.py` minimal pour les tests isolés :

```python
# core/tools_engine.py — stub pour tests standalone
_TOOLS = {}
_TOOL_ICONS = {}
_CURRENT_FAMILY = {}

def set_current_family(module, label, emoji):
    _CURRENT_FAMILY['module'] = module

def tool(name, description, parameters):
    def decorator(func):
        _TOOLS[name] = {"func": func, "description": description, "parameters": parameters}
        return func
    return decorator
```

Puis lancer les tests depuis la racine du dépôt :
```bash
cd /chemin/vers/promethee-tools
PYTHONPATH=. python scripts/test_tool.py ...
```

---

## 2. Test rapide en ligne de commande

Le script `scripts/test_tool.py` permet de tester un outil sans écrire de code :

```bash
# Tester df_info sur un fichier CSV
python scripts/test_tool.py \
  --module data_file_tools \
  --setup "df_read chemin=/tmp/employes.csv nom=rh" \
  --outil df_info \
  --args '{"nom": "rh"}'

# Tester web_search
python scripts/test_tool.py \
  --module web_tools \
  --outil web_search \
  --args '{"query": "open data emploi france", "max_results": 3}'

# Tester df_anonymize
python scripts/test_tool.py \
  --module data_file_tools \
  --setup "df_read chemin=/tmp/rh.csv nom=employes" \
  --outil df_anonymize \
  --args '{"nom": "employes", "operations": {"email": "hacher", "salaire": {"op": "generaliser_nombre", "arrondi": 5000}}}'
```

---

## 3. Test interactif (script Python)

Pour des scénarios plus complexes (chaînes d'outils, état de session) :

```python
# test_scenario_rh.py
import sys
sys.path.insert(0, "/chemin/vers/promethee")

import pandas as pd
from tools.data_file_tools import df_read, df_apply, df_groupby, df_anonymize, _DATASETS

# 1. Injecter des données de test directement
_DATASETS["employes"] = {
    "df": pd.DataFrame({
        "nom":            ["Dupont", "Martin", "Durand", "Petit"],
        "service":        ["RH", "IT", "RH", "IT"],
        "salaire":        [42000, 58000, 39000, 62000],
        "date_entree":    pd.to_datetime(["2018-03-15", "2015-09-01", "2021-11-20", "2019-06-01"]),
        "date_naissance": pd.to_datetime(["1985-07-22", "1990-03-10", "1975-08-05", "1988-12-15"]),
    }),
    "source": "test",
    "loaded_at": "2026-03-07 10:00:00",
}

# 2. Calculer ancienneté et âge
r = df_apply("employes", [
    "anciennete_ans = (today - date_entree).dt.days / 365.25",
    "age = (today - date_naissance).dt.days // 365",
], sauvegarder_sous="employes_enrichis")
assert r["status"] == "success", f"df_apply a échoué : {r}"
print("✅ df_apply OK — colonnes :", r["colonnes"])

# 3. Masse salariale par service
r = df_groupby("employes_enrichis", ["service"],
               {"salaire": ["sum", "mean"], "anciennete_ans": "mean"},
               sauvegarder_sous="masse_salariale")
assert r["status"] == "success"
print("✅ df_groupby OK — groupes :", r["nb_groupes"])
for ligne in r["lignes"]:
    print(f"   {ligne['service']:5} | total: {ligne['salaire_sum']:,.0f}€ | moy: {ligne['salaire_mean']:,.0f}€")

# 4. Anonymiser avant export
r = df_anonymize("employes_enrichis", {
    "nom":            "pseudonymiser",
    "salaire":        {"op": "generaliser_nombre", "arrondi": 5000},
    "date_naissance": {"op": "generaliser_date", "precision": "annee"},
}, sel="test_sel_rh")
assert r["status"] == "success"
print("✅ df_anonymize OK — opérations :", len(r["operations"]))

print("\n🎉 Tous les tests passent.")
```

```bash
python test_scenario_rh.py
```

---

## 4. Écrire des tests unitaires

Structure recommandée avec `pytest` :

```python
# tests/test_data_file_tools.py
import pytest
import pandas as pd
import sys
sys.path.insert(0, "/chemin/vers/promethee")

from tools.data_file_tools import (
    df_apply, df_groupby, df_correlate, df_outliers,
    df_anonymize, _DATASETS
)

# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def dataset_rh():
    """Injecte un dataset RH de test avant chaque test, le supprime après."""
    _DATASETS["rh_test"] = {
        "df": pd.DataFrame({
            "nom":      ["A", "B", "C", "D", "E"],
            "service":  ["RH", "IT", "RH", "IT", "RH"],
            "salaire":  [40000, 55000, 38000, 60000, 42000],
            "age":      [35, 28, 45, 32, 51],
        }),
        "source": "fixture",
        "loaded_at": "2026-01-01 00:00:00",
    }
    yield
    _DATASETS.pop("rh_test", None)
    _DATASETS.pop("rh_test_out", None)


# ── Tests df_groupby ──────────────────────────────────────────────────────────

def test_groupby_sum():
    r = df_groupby("rh_test", ["service"], {"salaire": "sum"})
    assert r["status"] == "success"
    assert r["nb_groupes"] == 2

def test_groupby_multi_agg():
    r = df_groupby("rh_test", ["service"], {"salaire": ["sum", "mean"], "age": "median"})
    assert r["status"] == "success"
    cols = r["colonnes"]
    assert "salaire_sum" in cols
    assert "salaire_mean" in cols

def test_groupby_colonne_inexistante():
    r = df_groupby("rh_test", ["colonne_fantome"], {"salaire": "sum"})
    assert r["status"] == "error"
    assert "introuvable" in r["error"]

def test_groupby_fonction_invalide():
    r = df_groupby("rh_test", ["service"], {"salaire": "variance"})
    assert r["status"] == "error"


# ── Tests df_anonymize ────────────────────────────────────────────────────────

def test_anonymize_supprimer():
    r = df_anonymize("rh_test", {"nom": "supprimer"})
    assert r["status"] == "success"
    assert "nom" not in _DATASETS["rh_test_anon"]["df"].columns

def test_anonymize_hacher_reproductible():
    r1 = df_anonymize("rh_test", {"nom": "hacher"}, sel="sel_test")
    r2 = df_anonymize("rh_test", {"nom": "hacher"}, sel="sel_test")
    df1 = _DATASETS["rh_test_anon"]["df"]["nom"].tolist()
    df2 = _DATASETS["rh_test_anon"]["df"]["nom"].tolist()
    assert df1 == df2, "Le hachage avec le même sel doit être reproductible"

def test_anonymize_avertissement_sans_sel():
    r = df_anonymize("rh_test", {"nom": "hacher"})
    assert r["status"] == "success"
    assert len(r["avertissements"]) > 0

def test_anonymize_generaliser_nombre():
    r = df_anonymize("rh_test", {"salaire": {"op": "generaliser_nombre", "arrondi": 10000}})
    assert r["status"] == "success"
    df_anon = _DATASETS["rh_test_anon"]["df"]
    # Tous les salaires doivent être multiples de 10000
    assert all(s % 10000 == 0 for s in df_anon["salaire"].dropna())


# ── Tests df_correlate ────────────────────────────────────────────────────────

def test_correlate_pearson():
    r = df_correlate("rh_test", methode="pearson")
    assert r["status"] == "success"
    assert "matrice" in r
    assert len(r["top_paires"]) > 0

def test_correlate_methode_invalide():
    r = df_correlate("rh_test", methode="cosine")
    assert r["status"] == "error"
```

```bash
pytest tests/test_data_file_tools.py -v
```

---

## 5. Tester les outils avec état de session

Certains outils (SQL, datasets) maintiennent un état. Toujours nettoyer entre les tests :

```python
from tools.data_file_tools import _DATASETS
from tools.sql_tools import _CONNECTIONS

@pytest.fixture(autouse=True)
def clean_state():
    """Remet les états de session à zéro entre chaque test."""
    _DATASETS.clear()
    _CONNECTIONS.clear()
    yield
    _DATASETS.clear()
    _CONNECTIONS.clear()
```

---

## 6. Tester les outils qui appellent des APIs

Deux approches :

### A — Tests d'intégration réels (nécessitent les clés API)

```python
# Ne lancer que si les credentials sont présents
import os
import pytest

@pytest.mark.skipif(
    not os.getenv("LEGIFRANCE_CLIENT_ID"),
    reason="Credentials Légifrance non configurés"
)
def test_legifrance_rechercher_integration():
    from tools.legifrance_tools import legifrance_rechercher
    r = legifrance_rechercher("licenciement économique", limit=3)
    assert r["status"] == "success"
    assert len(r["resultats"]) > 0
```

### B — Tests unitaires avec mock

```python
from unittest.mock import patch, MagicMock

def test_web_search_mock():
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [{"title": "Test", "url": "https://example.com", "snippet": "..."}]
    }
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        from tools.web_tools import web_search
        r = web_search("test query")
        assert r["status"] == "success"
```

---

## 7. Vérifier la cohérence JSON Schema / signature

Le script `scripts/check_schema.py` détecte les incohérences :

```bash
python scripts/check_schema.py --module data_file_tools
# Vérifie que chaque paramètre du JSON Schema a un argument Python correspondant
# et vice-versa
```

Exemple de problème détecté :

```
⚠️  df_groupby.sauvegarder_sous : présent dans JSON Schema mais absent de la signature Python
⚠️  df_clean.sauvegarder_sous   : présent dans la signature Python mais absent du JSON Schema
```
