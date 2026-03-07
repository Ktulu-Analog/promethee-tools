# Changelog

Toutes les modifications notables de la bibliothèque d'outils Prométhée sont documentées ici.

Format : [Semantic Versioning](https://semver.org/lang/fr/)

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
