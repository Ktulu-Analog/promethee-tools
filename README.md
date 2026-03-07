# Prométhée — Bibliothèque d'outils

Dépôt public des **outils** de [Prométhée](https://github.com/Ktulu-Analog/promethee), l'assistant IA desktop.

Les outils sont indépendants du cœur de l'application : ils peuvent être développés, testés, partagés et intégrés sans toucher au moteur principal.

---

## Sommaire

- [Qu'est-ce qu'un outil ?](#quest-ce-quun-outil-)
- [Référence des outils](#référence-des-outils)
- [Intégration dans Prométhée](#intégration-dans-prométhée)
- [Créer un nouvel outil](#créer-un-nouvel-outil)
- [Modifier un outil existant](#modifier-un-outil-existant)
- [Tester ses outils](#tester-ses-outils)
- [Conventions et bonnes pratiques](#conventions-et-bonnes-pratiques)
- [Contribuer](#contribuer)

---

## Qu'est-ce qu'un outil ?

Un **outil** est une fonction Python décorée avec `@tool(...)` qui expose une capacité à l'assistant. L'assistant peut l'appeler dynamiquement, avec des arguments typés, pour effectuer une action concrète : lire un fichier, interroger une API, transformer des données…

Chaque **module d'outils** (`*_tools.py`) regroupe des outils thématiquement cohérents. Il est autonome : pas de dépendance au code UI ni au moteur de chat.

L'interface entre un outil et Prométhée est standardisée via `core.tools_engine` (fourni par l'application principale) :

```python
from core.tools_engine import tool, set_current_family, _TOOL_ICONS

set_current_family("mon_module", "Nom affiché", "🔧")

@tool(
    name="mon_outil",
    description="Ce que fait l'outil, comment l'utiliser, exemples.",
    parameters={ ... }   # JSON Schema
)
def mon_outil(param1: str, param2: int = 10) -> dict:
    ...
    return {"status": "success", ...}
```

---

## Référence des outils

| Module | Famille | Nb | Outils |
|--------|---------|---:|--------|
| [data_file_tools.py](tools/data_file_tools.py) | 📊 Fichiers de données | 21 | `df_read` `df_list` `df_head` `df_info` `df_value_counts` `df_query` `df_pivot` `df_merge` `df_groupby` `df_correlate` `df_outliers` `df_concat` `df_clean` `df_cast` `df_apply` `df_rename` `df_sample` `df_write` `df_anonymize` `df_drop` |
| [data_tools.py](tools/data_tools.py) | 🛠️ Données & Utilitaires | 18 | `datetime_now` `datetime_parse` `datetime_diff` `datetime_range` `datetime_convert_tz` `text_regex` `text_stats` `text_diff` `text_template` `json_formatter` `json_diff` `json_schema_infer` `json_flatten` `json_transform` `encode_decode` `hash_text` `number_format` `stats_describe` |
| [datagouv_tools.py](tools/datagouv_tools.py) | 🏛️ Data.gouv.fr | 10 | `datagouv_search_datasets` `datagouv_get_dataset_info` `datagouv_list_dataset_resources` `datagouv_get_resource_info` `datagouv_query_resource_data` `datagouv_download_resource` `datagouv_search_dataservices` `datagouv_get_dataservice_info` `datagouv_get_dataservice_spec` `datagouv_get_metrics` |
| [export_template_tools.py](tools/export_template_tools.py) | 📄 Export gabarits | 3 | `list_docx_template_styles` `export_docx_template` `export_pptx_template` |
| [export_tools.py](tools/export_tools.py) | 📤 Export | 9 | `export_md` `export_docx` `export_xlsx_json` `export_xlsx_csv` `export_pptx_json` `export_pptx_outline` `export_pdf` `export_libreoffice` `export_libreoffice_native` |
| [grist_tools.py](tools/grist_tools.py) | 📋 Grist | 17 | `grist_list_orgs` `grist_list_workspaces` `grist_list_docs` `grist_describe_doc` `grist_create_doc` `grist_delete_doc` `grist_move_doc_to_trash` `grist_list_tables` `grist_create_table` `grist_delete_table` `grist_list_columns` `grist_add_columns` `grist_list_records` `grist_add_records` `grist_update_records` `grist_delete_records` `grist_run_sql` |
| [judilibre_tools.py](tools/judilibre_tools.py) | ⚖️ Judilibre | 6 | `judilibre_rechercher` `judilibre_decision` `judilibre_scan` `judilibre_taxonomie` `judilibre_stats` `judilibre_historique` |
| [legifrance_tools.py](tools/legifrance_tools.py) | 📜 Légifrance | 62 | `legifrance_rechercher` `legifrance_consulter_code` `legifrance_obtenir_article` … (voir fichier) |
| [ocr_tools.py](tools/ocr_tools.py) | 🔎 OCR | 4 | `ocr_image` `ocr_pdf` `ocr_pdf_detect` `ocr_languages` |
| [python_tools.py](tools/python_tools.py) | 🐍 Python | 4 | `python_exec` `python_install` `python_run_script` `python_reset_env` |
| [skill_tools.py](tools/skill_tools.py) | 📚 Skills | 2 | `skill_list` `skill_read` |
| [sql_tools.py](tools/sql_tools.py) | 🗄️ SQL | 9 | `sql_connect` `sql_disconnect` `sql_list_connections` `sql_list_tables` `sql_describe` `sql_query` `sql_execute` `sql_explain` `sql_export_csv` |
| [system_tools.py](tools/system_tools.py) | 💻 Système | 20 | `read_file` `write_file` `tail_file` `head_file` `find_and_replace` `list_files` `tree_view` `search_files` `copy_file` `move_file` `delete_file` `create_directory` `get_file_info` `count_lines` `compress_files` `extract_archive` `diff_files` `batch_rename` `batch_delete` |
| [thunderbird_tools.py](tools/thunderbird_tools.py) | 📧 Thunderbird | 12 | `tb_list_mails` `tb_search_mails` `tb_read_mail` `tb_mark_mail` `tb_move_mail` `tb_create_draft` `tb_agenda_upcoming` `tb_agenda_search` `tb_todo_list` `tb_agenda_create` `tb_agenda_update` `tb_agenda_delete` |
| [web_tools.py](tools/web_tools.py) | 🌐 Web | 10 | `web_search` `web_search_news` `web_search_engine` `web_fetch` `web_screenshot` `web_extract` `web_links` `web_tables` `web_rss` `web_download_file` |

**Total : 207 outils répartis dans 15 modules.**

---

## Intégration dans Prométhée

Copier le ou les fichiers `*_tools.py` souhaités dans le dossier `tools/` de Prométhée, puis les déclarer dans `tools/__init__.py` :

```python
def register_all() -> None:
    from tools import mon_nouveau_module   # ← ajouter cette ligne
    ...
```

C'est tout. Le décorateur `@tool` s'occupe de l'enregistrement automatique au moment de l'import.

---

## Créer un nouvel outil

Voir le guide complet : **[docs/GUIDE_CREATION.md](docs/GUIDE_CREATION.md)**

Démarrage rapide avec le script de génération :

```bash
python scripts/new_tool_module.py --nom mon_module --famille "Ma famille" --emoji 🔧
# → génère tools/mon_module_tools.py avec la structure de base
```

---

## Modifier un outil existant

Voir : **[docs/GUIDE_MODIFICATION.md](docs/GUIDE_MODIFICATION.md)**

---

## Tester ses outils

Voir : **[docs/GUIDE_TEST.md](docs/GUIDE_TEST.md)**

Lancement rapide :

```bash
python scripts/test_tool.py --module data_file_tools --outil df_info --args '{"nom": "mon_dataset"}'
```

---

## Conventions et bonnes pratiques

Voir : **[docs/CONVENTIONS.md](docs/CONVENTIONS.md)**

---

## Contribuer

1. Forker le dépôt
2. Créer une branche `feature/nom-du-module`
3. Développer et tester (voir guides)
4. Ouvrir une Pull Request avec la description des outils ajoutés

Les contributions doivent respecter les [conventions](docs/CONVENTIONS.md) et inclure des tests dans `scripts/`.
