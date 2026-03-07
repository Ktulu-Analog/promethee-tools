# Tests — Prométhée Tools

## Lancer les tests

```bash
# Tous les tests (depuis la racine du dépôt ou depuis promethee/)
python scripts/run_tests.py

# Un module spécifique
python scripts/run_tests.py --module data_file_tools
python scripts/run_tests.py --module data_tools
python scripts/run_tests.py --module system_tools   # couvre aussi sql/python/export

# Options
python scripts/run_tests.py --verbose     # détail chaque test
python scripts/run_tests.py --fail-fast   # arrêt au premier échec
python scripts/run_tests.py --rapport rapport.txt  # sauvegarde le rapport
```

## Couverture (289 tests)

| Fichier de test | Outils couverts | Tests |
|---|---|---|
| `test_data_file_tools.py` | 21 outils df_* | 143 |
| `test_data_tools.py` | 18 outils (dates, texte, JSON, encodage, stats) | 80 |
| `test_system_sql_python_export.py` | 19 outils system + 9 SQL + 2 python + 6 export | 66 |

## Résultats attendus

```
✅ test_data_file_tools    143/143 passés
✅ test_data_tools          80/80  passés
✅ test_system_sql_python_export  66/66 passés
Total : 289 ✅  —  Durée : ~6s
```

## Prérequis

- Python 3.11+
- Prométhée installé (ou stub généré automatiquement)
- `pandas`, `numpy`, `openpyxl`, `python-docx`, `python-pptx`, `reportlab`

Le runner détecte automatiquement le chemin de Prométhée parmi :
`../promethee`, `~/promethee`, `.`, `..`

Si Prométhée est absent, un stub minimal est généré dans `core/tools_engine.py`
pour permettre les tests standalone.
