# Dépendances par Module
# ========================

## Modules Physique-Chimie (nouveaux)

### chemistry_tools.py
- `pubchempy` (obligatoire) : Accès à l'API PubChem

```bash
pip install pubchempy
```

### physics_tools.py
- `scipy` (obligatoire) : Constantes CODATA/NIST

```bash
pip install scipy
```

### curriculum_tools.py
- `pypdf` (obligatoire) : Lecture PDF locale (fallback sans RAG)

```bash
pip install pypdf
```

- `qdrant-client` (optionnel) : Base vectorielle pour RAG
- `sentence-transformers` (optionnel) : Embeddings pour RAG

```bash
# Optionnel : pour activer le RAG vectoriel
pip install qdrant-client sentence-transformers
```

Configuration `.env` (optionnelle) :
```
RAG_ENABLED=false                 # désactive le RAG, lecture locale uniquement
RAG_COLLECTION=curriculum_memory
RAG_MODEL=all-MiniLM-L6-v2
```

### lms_tools.py
- Aucune dépendance externe (bibliothèque standard uniquement)

### web_search_tools.py
- `requests` (obligatoire) : Appels HTTP
- `beautifulsoup4` (obligatoire) : Parsing HTML
- `lxml` (obligatoire) : Parser BeautifulSoup

```bash
pip install requests beautifulsoup4 lxml
```

Configuration `.env` (optionnelle) :
```
WEB_SEARCH_ENGINE=ddg                    # "ddg" (défaut) ou "searxng"
WEB_SEARCH_SEARXNG_URL=http://localhost:8080   # URL instance SearXNG
WEB_SEARCH_DEFAULT_LANG=fr-FR            # langue des résultats
```

### tool_maker_tools.py
- Dépendance interne : `core.dynamic_tools` (mode agentique de Prométhée)
- Aucune installation externe requise

---

## Modules Existants (référence)

Pour information, voici les dépendances des modules déjà présents dans promethee-tools :

- `data_file_tools.py` : `pandas`, `openpyxl`, `xlrd`
- `data_tools.py` : aucune dépendance externe
- `datagouv_tools.py` : `requests`
- `export_template_tools.py` : `python-docx`, `python-pptx`
- `export_tools.py` : `python-docx`, `python-pptx`, `reportlab`, `libreoffice` (optionnel)
- `grist_tools.py` : `requests`
- `judilibre_tools.py` : `requests`
- `legifrance_tools.py` : `requests`, `oauthlib`
- `ocr_tools.py` : `pytesseract`, `Pillow`
- `python_tools.py` : aucune dépendance externe
- `skill_tools.py` : aucune dépendance externe
- `sql_tools.py` : `sqlalchemy`
- `system_tools.py` : aucune dépendance externe
- `thunderbird_tools.py` : `requests`
- `web_tools.py` : `requests`, `beautifulsoup4`, `lxml`
