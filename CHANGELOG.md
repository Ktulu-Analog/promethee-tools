# Changelog

Toutes les modifications notables de la bibliothèque d'outils Prométhée sont documentées ici.

Format : [Semantic Versioning](https://semver.org/lang/fr/)

---

## [1.2.0] — 2026-03-25

### Ajouts — Physique-Chimie

**Nouveaux modules (6) :**

- `chemistry_tools` (1) : `search_chemical_compound` — Recherche de molécules sur PubChem
- `physics_tools` (2) : `get_physical_constant`, `convert_units` — Constantes CODATA/NIST et conversion d'unités
- `curriculum_tools` (1) : `get_curriculum_guidelines` — Programmes Eduscol via RAG ou recherche locale
- `lms_tools` (1) : `export_moodle_xml` — Export QCM Moodle XML pour ENT/Pronote
- `web_search_tools` (3) : `web_search`, `web_search_news`, `web_search_engine` — Recherche web DDG/SearXNG
- `tool_maker_tools` (1) : `create_skill` — Auto-développement et correction d'outils

**Total : 216 outils répartis dans 21 modules.**

### Documentation

- Ajout de `docs/DEPENDENCIES.md` : Liste complète des dépendances par module

---

## [1.1.0] — 2026-03-07

### Ajouts — `data_file_tools`

Outils d'analyse :
- `df_groupby` — agrégation par groupe (GROUP BY SQL), multi-fonctions simultanées
- `df_correlate` — matrice de corrélation (Pearson, Spearman, Kendall) avec classement des paires
- `df_outliers` — détection des valeurs aberrantes (IQR et z-score)

Outils de transformation :
- `df_concat` — empilement vertical de datasets (UNION SQL), avec colonne `_source` optionnelle
- `df_clean` — nettoyage en une passe : NaN, doublons, strip, renommage, suppression de colonnes
- `df_cast` — conversion de types (int, float, str, bool, datetime, category), avec support des formats de date
- `df_apply` — création de colonnes calculées via expressions Python
- `df_rename` — renommage direct de colonnes

Échantillonnage :
- `df_sample` — tirage aléatoire ou stratifié, avec graine pour reproductibilité

Conformité RGPD :
- `df_anonymize` — anonymisation et pseudonymisation : suppression, hachage SHA-256 avec sel, masquage, généralisation de dates, généralisation de nombres, bruit gaussien

### Corrections — `data_file_tools`

- `df_apply` : le contexte `eval()` expose désormais `today` / `date_auj`, `now`, `Timestamp`, `Timedelta`, `to_datetime`, `cut`, `qcut`, ainsi que `int`, `float`, `str`, `sum`, `list`. Permet les calculs d'ancienneté, d'âge et de tranches sans contournement.

---

## [1.0.0] — 2026-01-01

### Outils initiaux

- `data_file_tools` (10) : `df_read`, `df_list`, `df_head`, `df_info`, `df_value_counts`, `df_query`, `df_pivot`, `df_merge`, `df_write`, `df_drop`
- `data_tools` (18) : datetime, text, json, encode, hash, number, stats
- `datagouv_tools` (10) : search, dataset, resource, dataservice, metrics
- `export_template_tools` (3) : list styles, export docx/pptx depuis gabarits
- `export_tools` (9) : md, docx, xlsx, pptx, pdf, libreoffice
- `grist_tools` (17) : orgs, workspaces, docs, tables, columns, records, SQL
- `judilibre_tools` (6) : recherche, décision, scan, taxonomie, stats, historique
- `legifrance_tools` (62) : codes, articles, lois, jurisprudence, conventions, JORF, CNIL…
- `ocr_tools` (4) : image, pdf, detect, languages
- `python_tools` (4) : exec, install, run_script, reset_env
- `skill_tools` (2) : list, read
- `sql_tools` (9) : connect, query, execute, explain, export
- `system_tools` (20) : read/write/find/copy/move/delete/archive/diff…
- `thunderbird_tools` (12) : mails, agenda, todos
- `web_tools` (10) : search, fetch, screenshot, extract, links, tables, rss, download
