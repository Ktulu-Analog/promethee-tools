# Guide de modification d'un outil existant

Ce guide couvre les cas de modification les plus courants : ajout de paramètre, changement de comportement, refactoring.

---

## Sommaire

1. [Ajouter un paramètre optionnel](#1-ajouter-un-paramètre-optionnel)
2. [Modifier la description](#2-modifier-la-description)
3. [Étendre les valeurs autorisées d'un enum](#3-étendre-les-valeurs-autorisées-dun-enum)
4. [Ajouter un outil à un module existant](#4-ajouter-un-outil-à-un-module-existant)
5. [Modifier le comportement d'un outil](#5-modifier-le-comportement-dun-outil)
6. [Renommer un outil](#6-renommer-un-outil)
7. [Supprimer un outil](#7-supprimer-un-outil)
8. [Compatibilité et rétrocompatibilité](#8-compatibilité-et-rétrocompatibilité)

---

## 1. Ajouter un paramètre optionnel

Modification la plus fréquente et la plus sûre : **toujours optionnel avec une valeur par défaut** qui reproduit le comportement actuel.

### Dans le JSON Schema (`parameters`)

```python
# Avant
"properties": {
    "nom":    {"type": "string", "description": "..."},
    "limite": {"type": "integer", "description": "..."},
},
"required": ["nom"],

# Après — ajout de "trier_par"
"properties": {
    "nom":      {"type": "string",  "description": "..."},
    "limite":   {"type": "integer", "description": "..."},
    "trier_par":{"type": "string",  "description": "Colonne de tri (défaut: aucun tri)."},
},
"required": ["nom"],   # ← ne pas ajouter le nouveau paramètre ici
```

### Dans la signature Python

```python
# Avant
def mon_outil(nom: str, limite: int = 10) -> dict:

# Après
def mon_outil(nom: str, limite: int = 10, trier_par: Optional[str] = None) -> dict:
```

### Dans le corps de la fonction

```python
    # Après récupération du résultat...
    if trier_par:
        resultats = sorted(resultats, key=lambda x: x.get(trier_par, ""))
```

---

## 2. Modifier la description

La description est lue à chaque échange par le LLM. Une meilleure description améliore directement la qualité des appels.

```python
# Avant — trop vague
description="Recherche dans Légifrance.",

# Après — précise et avec exemples
description=(
    "Recherche des textes juridiques dans Légifrance : codes, lois, décrets, "
    "jurisprudence, conventions collectives. "
    "Retourne une liste de résultats avec titre, date, identifiant et extrait. "
    "Exemples : 'licenciement économique', 'Code du travail article L1234', "
    "'ordonnance 2023'."
),
```

**Ne pas** modifier `name`, cela casserait les sessions actives.

---

## 3. Étendre les valeurs autorisées d'un enum

```python
# Avant
"agregation": {
    "type": "string",
    "description": "Fonction : 'sum', 'mean', 'count'.",
    "enum": ["sum", "mean", "count"],
},

# Après — ajout de 'median' et 'std'
"agregation": {
    "type": "string",
    "description": "Fonction : 'sum', 'mean', 'count', 'min', 'max', 'median', 'std'.",
    "enum": ["sum", "mean", "count", "min", "max", "median", "std"],
},
```

Et mettre à jour la validation dans la fonction :

```python
# Avant
AGGS = {"sum", "mean", "count"}

# Après
AGGS = {"sum", "mean", "count", "min", "max", "median", "std"}
```

---

## 4. Ajouter un outil à un module existant

1. **Choisir le bon module** : l'outil doit être thématiquement cohérent avec les autres
2. **Vérifier que le nom est unique** dans toute l'application
3. **Placer le `@tool` dans l'ordre logique** du fichier (regrouper par catégorie)
4. **Mettre à jour le docstring** du module (liste des outils, compteur)
5. **Ajouter l'icône** dans `_TOOL_ICONS`

```python
# Dans le docstring
"""
Outils exposés (N+1) :   ← incrémenter
  ...
  - mon_nouvel_outil : description
"""

# Dans _TOOL_ICONS
_TOOL_ICONS.update({
    ...
    "mon_nouvel_outil": "🆕",
})
```

---

## 5. Modifier le comportement d'un outil

Avant de modifier un outil utilisé en production :

1. **Lire le code aval** : y a-t-il des outils qui appellent cet outil ? (chercher le `name` dans les autres fichiers)
2. **Ne pas changer le format de retour** sans rétrocompatibilité
3. **Préférer des ajouts aux suppressions** de champs dans le retour

```python
# ❌ Risqué — supprime un champ existant
return {"status": "success", "data": resultats}
# (si le code appelant utilisait "items", il casse)

# ✅ Rétrocompatible — ajoute sans supprimer
return {"status": "success", "items": resultats, "data": resultats}
```

---

## 6. Renommer un outil

Le renommage doit être fait avec soin car le LLM peut avoir mémorisé l'ancien nom dans des conversations actives.

**Procédure recommandée :**

```python
# Étape 1 — créer le nouvel outil avec le nouveau nom
@tool(name="df_rename", ...)
def df_rename(...) -> dict:
    return _rename_impl(...)

# Étape 2 — conserver temporairement l'ancien nom comme alias déprécié
@tool(
    name="df_rename_columns",
    description="⚠️ DÉPRÉCIÉ — utiliser df_rename. " + ...,
    parameters=...
)
def df_rename_columns(...) -> dict:
    return _rename_impl(...)   # même implémentation

# Étape 3 — après une période de transition, supprimer l'alias
```

---

## 7. Supprimer un outil

Même procédure de dépréciation progressive. Dans le cas d'un outil rarement utilisé, la suppression directe est acceptable si :

- Le module vient d'être ajouté (pas encore en production)
- L'outil n'a aucun équivalent que le LLM pourrait confondre
- Le `CHANGELOG.md` documente la suppression

---

## 8. Compatibilité et rétrocompatibilité

### Ce qui est sûr

| Modification | Impact |
|---|---|
| Ajouter un paramètre optionnel | ✅ Aucun |
| Améliorer la description | ✅ Aucun |
| Ajouter une valeur à un enum | ✅ Aucun |
| Ajouter un champ dans le retour | ✅ Aucun |
| Corriger un bug (comportement plus correct) | ✅ Positif |

### Ce qui est risqué

| Modification | Impact | Mitigation |
|---|---|---|
| Renommer `name` | ❌ Sessions actives cassées | Alias de dépréciation |
| Supprimer un paramètre | ❌ Appels existants cassés | Garder avec warning |
| Rendre optionnel → obligatoire | ❌ | Ne pas faire |
| Supprimer un champ du retour | ⚠️ Code aval cassé | Garder l'ancien champ |
| Changer le type d'un champ retour | ⚠️ | Ajouter un nouveau champ |

### Documenter les changements

Toute modification non triviale doit être documentée dans [CHANGELOG.md](../CHANGELOG.md) :

```markdown
## [1.2.0] — 2026-03-07

### Ajouts
- `data_file_tools` : `df_anonymize` — anonymisation RGPD (hachage, masquage, bruit gaussien)
- `data_file_tools` : `df_apply` — accès à `today`, `cut`, `qcut` pour les calculs RH

### Corrections
- `data_file_tools` : `df_apply` — `pd.Timestamp.now()` accessible dans le contexte eval
```
