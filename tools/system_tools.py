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
tools/system_tools.py — Outils d'accès au système de fichiers (20 outils)
==========================================================================

Outils exposés (20) :

  Lecture / Écriture (5) :
    - read_file, write_file, tail_file, head_file, find_and_replace

  Navigation (3) :
    - list_files, tree_view, search_files

  Gestion (6) :
    - copy_file, move_file, delete_file, create_directory, get_file_info, count_lines

  Archives (2) :
    - compress_files  : crée une archive ZIP ou TAR(.gz/.bz2/.xz)
    - extract_archive : extrait une archive avec protection zip-slip,
                        listing optionnel sans extraction, support ZIP/TAR/GZ/BZ2/XZ

  Comparaison (1) :
    - diff_files      : diff unifié ou côte-à-côte entre deux fichiers (ou textes bruts),
                        avec stats de modifications et contexte configurable

  Batch (2) :
    - batch_rename, batch_delete
"""

import os
import re
import shutil
import zipfile
import tarfile
import hashlib
import difflib
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from core.tools_engine import tool, set_current_family, _TOOL_ICONS

set_current_family("system_tools", "Système de fichiers", "🗂️")

# Configuration des icônes
_TOOL_ICONS.update({
    "read_file": "📄", "write_file": "✍️", "tail_file": "📜", "head_file": "📋",
    "find_and_replace": "🔍", "list_files": "📁", "tree_view": "🌳",
    "search_files": "🔎", "copy_file": "📋", "move_file": "🔄",
    "delete_file": "🗑️", "create_directory": "📂", "get_file_info": "ℹ️",
    "count_lines": "🔢", "compress_files": "📦", "extract_archive": "📂",
    "diff_files": "↔️", "batch_rename": "✏️", "batch_delete": "🗑️"
})

# Sécurité
_FORBIDDEN_NAMES = frozenset([
    ".env", ".ssh", "id_rsa", "id_ed25519", "passwd", "shadow",
    ".aws", "credentials", ".gnupg", "private", "secret"
])

_PROTECTED_PATHS = frozenset([
    "/etc", "/sys", "/proc", "/dev", "/boot", "/root",
    "/bin", "/sbin", "/usr/bin", "/usr/sbin"
])

_MAX_WRITE_SIZE = 10 * 1024 * 1024  # 10 MB

def _is_safe_path(path: Path, operation: str = "read") -> tuple[bool, str]:
    """Vérifie la sécurité d'un chemin."""
    try:
        resolved = path.expanduser().resolve()
    except Exception as e:
        return False, f"Chemin invalide: {e}"

    # Vérifier noms interdits
    for part in resolved.parts:
        if any(forbidden in part.lower() for forbidden in _FORBIDDEN_NAMES):
            return False, f"Accès refusé: '{part}' interdit"

    # Vérifier chemins protégés
    for protected in _PROTECTED_PATHS:
        if str(resolved).startswith(protected):
            return False, f"Chemin système protégé: {protected}"

    # Pour écriture/suppression: vérifier qu'on est sous HOME
    if operation in ("write", "delete"):
        home = Path.home()
        if not str(resolved).startswith(str(home)):
            return False, f"Écriture autorisée uniquement sous {home}"

    return True, ""

def _format_size(size_bytes: int) -> str:
    """Formate une taille en bytes."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

# ====================================================================================
# LECTURE / ÉCRITURE (5 outils)
# ====================================================================================

@tool(
    name="read_file",
    description="Lit un fichier texte avec support de plages de lignes et détection d'encoding.",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Chemin du fichier"},
            "max_chars": {"type": "integer", "default": 4000},
            "start_line": {"type": "integer", "description": "Ligne de départ (1-indexed)"},
            "end_line": {"type": "integer", "description": "Ligne de fin (-1 pour EOF)"},
            "encoding": {"type": "string", "default": "utf-8"}
        },
        "required": ["path"]
    }
)
def read_file(path: str, max_chars: int = 4000, start_line: Optional[int] = None,
              end_line: Optional[int] = None, encoding: str = "utf-8") -> dict:
    p = Path(path).expanduser().resolve()
    safe, error = _is_safe_path(p, "read")
    if not safe:
        return {"status": "error", "error": error}
    if not p.exists():
        return {"status": "error", "error": f"Fichier non trouvé: {path}"}

    try:
        content = p.read_text(encoding=encoding, errors="replace")
        if start_line or end_line:
            lines = content.split('\n')
            start = (start_line - 1) if start_line else 0
            end = end_line if end_line and end_line != -1 else len(lines)
            content = '\n'.join(lines[start:end])

        original_len = len(content)
        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]

        return {"status": "success", "content": content, "size": original_len,
                "truncated": truncated, "file": str(p)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(
    name="write_file",
    description="Écrit du contenu dans un fichier (max 10MB).",
    parameters={
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "mode": {"type": "string", "default": "w",
                    "description": "w (écraser), a (ajouter), x (créer uniquement)"},
            "encoding": {"type": "string", "default": "utf-8"}
        },
        "required": ["path", "content"]
    }
)
def write_file(path: str, content: str, mode: str = "w", encoding: str = "utf-8") -> dict:
    p = Path(path).expanduser().resolve()
    safe, error = _is_safe_path(p, "write")
    if not safe:
        return {"status": "error", "error": error}

    size = len(content.encode(encoding))
    if size > _MAX_WRITE_SIZE:
        return {"status": "error", "error": f"Trop gros: {_format_size(size)} > 10MB"}

    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding=encoding)
        return {"status": "success", "file": str(p), "size": _format_size(size)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="tail_file", description="Affiche les dernières lignes d'un fichier.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string"}, "lines": {"type": "integer", "default": 10}
      }, "required": ["path"]})
def tail_file(path: str, lines: int = 10) -> dict:
    p = Path(path).expanduser().resolve()
    safe, error = _is_safe_path(p, "read")
    if not safe:
        return {"status": "error", "error": error}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        all_lines = content.split('\n')
        tail = all_lines[-lines:]
        return {"status": "success", "content": '\n'.join(tail),
                "lines_shown": len(tail), "total_lines": len(all_lines)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="head_file", description="Affiche les premières lignes d'un fichier.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string"}, "lines": {"type": "integer", "default": 10}
      }, "required": ["path"]})
def head_file(path: str, lines: int = 10) -> dict:
    p = Path(path).expanduser().resolve()
    safe, error = _is_safe_path(p, "read")
    if not safe:
        return {"status": "error", "error": error}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        all_lines = content.split('\n')
        head = all_lines[:lines]
        return {"status": "success", "content": '\n'.join(head),
                "lines_shown": len(head), "total_lines": len(all_lines)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="find_and_replace", description="Recherche et remplace du texte dans des fichiers.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string"}, "find": {"type": "string"},
          "replace": {"type": "string"}, "pattern": {"type": "string", "default": "*.txt"},
          "recursive": {"type": "boolean", "default": True},
          "preview": {"type": "boolean", "default": True}
      }, "required": ["path", "find", "replace"]})
def find_and_replace(path: str, find: str, replace: str, pattern: str = "*.txt",
                     recursive: bool = True, preview: bool = True) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        return {"status": "error", "error": "Pas un dossier"}

    results = []
    files = p.rglob(pattern) if recursive else p.glob(pattern)

    for file in files:
        if not file.is_file():
            continue
        safe, _ = _is_safe_path(file, "read")
        if not safe:
            continue
        try:
            content = file.read_text(encoding="utf-8", errors="replace")
            if find in content:
                occurrences = content.count(find)
                if not preview:
                    file.write_text(content.replace(find, replace), encoding="utf-8")
                results.append({"file": str(file), "occurrences": occurrences})
        except:
            pass

    return {"status": "success", "mode": "preview" if preview else "applied",
            "files_found": len(results), "results": results[:20]}

# ====================================================================================
# NAVIGATION (3 outils)
# ====================================================================================

@tool(name="list_files", description="Liste les fichiers d'un dossier (amélioré).",
      parameters={"type": "object", "properties": {
          "path": {"type": "string", "default": "."},
          "pattern": {"type": "string", "default": "*"},
          "recursive": {"type": "boolean", "default": False},
          "sort_by": {"type": "string", "default": "name"},
          "show_hidden": {"type": "boolean", "default": False}
      }, "required": []})
def list_files(path: str = ".", pattern: str = "*", recursive: bool = False,
               sort_by: str = "name", show_hidden: bool = False) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        return {"status": "error", "error": "Pas un dossier"}

    try:
        files = p.rglob(pattern) if recursive else p.glob(pattern)
        entries = []
        for entry in files:
            if not show_hidden and entry.name.startswith('.'):
                continue
            stat = entry.stat()
            entries.append({
                "name": entry.name, "path": str(entry),
                "type": "file" if entry.is_file() else "dir",
                "size_kb": round(stat.st_size / 1024, 1) if entry.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })

        # Tri
        if sort_by == "size":
            entries.sort(key=lambda x: x["size_kb"] or 0, reverse=True)
        elif sort_by == "date":
            entries.sort(key=lambda x: x["modified"], reverse=True)
        else:
            entries.sort(key=lambda x: x["name"])

        return {"status": "success", "path": str(p), "count": len(entries),
                "files": entries[:50]}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="tree_view", description="Affiche l'arborescence d'un dossier.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string", "default": "."},
          "max_depth": {"type": "integer", "default": 3},
          "show_hidden": {"type": "boolean", "default": False}
      }, "required": []})
def tree_view(path: str = ".", max_depth: int = 3, show_hidden: bool = False) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        return {"status": "error", "error": "Pas un dossier"}

    def build_tree(directory: Path, prefix: str = "", depth: int = 0) -> List[str]:
        if depth > max_depth:
            return []
        lines = []
        try:
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            for i, entry in enumerate(entries):
                if not show_hidden and entry.name.startswith('.'):
                    continue
                is_last = i == len(entries) - 1
                current = "└── " if is_last else "├── "
                lines.append(f"{prefix}{current}{entry.name}")
                if entry.is_dir() and depth < max_depth:
                    extension = "    " if is_last else "│   "
                    lines.extend(build_tree(entry, prefix + extension, depth + 1))
        except PermissionError:
            pass
        return lines

    tree = [str(p)] + build_tree(p)
    return {"status": "success", "tree": '\n'.join(tree[:100])}

@tool(name="search_files", description="Recherche avancée de fichiers.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string", "default": "."},
          "name_pattern": {"type": "string"},
          "content": {"type": "string"},
          "recursive": {"type": "boolean", "default": True},
          "max_results": {"type": "integer", "default": 50}
      }, "required": []})
def search_files(path: str = ".", name_pattern: Optional[str] = None,
                 content: Optional[str] = None, recursive: bool = True,
                 max_results: int = 50) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        return {"status": "error", "error": "Pas un dossier"}

    results = []
    pattern = name_pattern or "*"
    files = p.rglob(pattern) if recursive else p.glob(pattern)

    for file in files:
        if len(results) >= max_results:
            break
        if not file.is_file():
            continue

        match = True
        if content:
            try:
                file_content = file.read_text(encoding="utf-8", errors="replace")
                match = content in file_content
            except:
                match = False

        if match:
            results.append({"path": str(file), "name": file.name,
                          "size": _format_size(file.stat().st_size)})

    return {"status": "success", "found": len(results), "results": results}

# ====================================================================================
# GESTION (6 outils)
# ====================================================================================

@tool(name="copy_file", description="Copie un fichier ou dossier.",
      parameters={"type": "object", "properties": {
          "source": {"type": "string"}, "destination": {"type": "string"},
          "overwrite": {"type": "boolean", "default": False}
      }, "required": ["source", "destination"]})
def copy_file(source: str, destination: str, overwrite: bool = False) -> dict:
    src = Path(source).expanduser().resolve()
    dst = Path(destination).expanduser().resolve()

    if not src.exists():
        return {"status": "error", "error": "Source introuvable"}

    safe, error = _is_safe_path(dst, "write")
    if not safe:
        return {"status": "error", "error": error}

    if dst.exists() and not overwrite:
        return {"status": "error", "error": "Destination existe (utilisez overwrite=True)"}

    try:
        if src.is_file():
            shutil.copy2(src, dst)
        else:
            shutil.copytree(src, dst, dirs_exist_ok=overwrite)
        return {"status": "success", "copied": str(src), "to": str(dst)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="move_file", description="Déplace ou renomme un fichier.",
      parameters={"type": "object", "properties": {
          "source": {"type": "string"}, "destination": {"type": "string"}
      }, "required": ["source", "destination"]})
def move_file(source: str, destination: str) -> dict:
    src = Path(source).expanduser().resolve()
    dst = Path(destination).expanduser().resolve()

    if not src.exists():
        return {"status": "error", "error": "Source introuvable"}

    safe, error = _is_safe_path(src, "delete")
    if not safe:
        return {"status": "error", "error": error}
    safe, error = _is_safe_path(dst, "write")
    if not safe:
        return {"status": "error", "error": error}

    try:
        shutil.move(str(src), str(dst))
        return {"status": "success", "moved": str(src), "to": str(dst)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="delete_file", description="Supprime un fichier (confirmation requise).",
      parameters={"type": "object", "properties": {
          "path": {"type": "string"},
          "confirm": {"type": "boolean", "description": "DOIT être True pour confirmer"}
      }, "required": ["path", "confirm"]})
def delete_file(path: str, confirm: bool) -> dict:
    if not confirm:
        return {"status": "cancelled", "message": "Suppression annulée (confirm=False)"}

    p = Path(path).expanduser().resolve()
    safe, error = _is_safe_path(p, "delete")
    if not safe:
        return {"status": "error", "error": error}

    if not p.exists():
        return {"status": "error", "error": "Fichier introuvable"}

    try:
        if p.is_file():
            p.unlink()
        else:
            shutil.rmtree(p)
        return {"status": "success", "deleted": str(p)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="create_directory", description="Crée un répertoire.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string"},
          "parents": {"type": "boolean", "default": True}
      }, "required": ["path"]})
def create_directory(path: str, parents: bool = True) -> dict:
    p = Path(path).expanduser().resolve()
    safe, error = _is_safe_path(p, "write")
    if not safe:
        return {"status": "error", "error": error}

    try:
        p.mkdir(parents=parents, exist_ok=False)
        return {"status": "success", "created": str(p)}
    except FileExistsError:
        return {"status": "error", "error": "Dossier existe déjà"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="get_file_info", description="Métadonnées complètes d'un fichier.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string"}
      }, "required": ["path"]})
def get_file_info(path: str) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"status": "error", "error": "Fichier introuvable"}

    try:
        stat = p.stat()
        info = {
            "status": "success",
            "path": str(p),
            "name": p.name,
            "type": "file" if p.is_file() else "directory",
            "size": _format_size(stat.st_size),
            "size_bytes": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "permissions": oct(stat.st_mode)[-3:]
        }

        # Hash MD5 pour fichiers < 100MB
        if p.is_file() and stat.st_size < 100 * 1024 * 1024:
            md5 = hashlib.md5()
            with open(p, 'rb') as f:
                md5.update(f.read())
            info["md5"] = md5.hexdigest()

        return info
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(name="count_lines", description="Compte les lignes de code.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string"},
          "pattern": {"type": "string", "default": "*.py"},
          "recursive": {"type": "boolean", "default": True}
      }, "required": ["path"]})
def count_lines(path: str, pattern: str = "*.py", recursive: bool = True) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return {"status": "error", "error": "Chemin introuvable"}

    total_lines = 0
    file_count = 0
    files = []

    if p.is_file():
        pattern_files = [p]
    else:
        pattern_files = p.rglob(pattern) if recursive else p.glob(pattern)

    for file in pattern_files:
        if not file.is_file():
            continue
        try:
            lines = len(file.read_text(encoding="utf-8", errors="replace").split('\n'))
            total_lines += lines
            file_count += 1
            files.append({"file": file.name, "lines": lines})
        except:
            pass

    return {"status": "success", "total_lines": total_lines, "files": file_count,
            "details": sorted(files, key=lambda x: x["lines"], reverse=True)[:10]}

# ====================================================================================
# ARCHIVES (2 outils)
# ====================================================================================

@tool(name="compress_files", description="Crée une archive ZIP ou TAR.",
      parameters={"type": "object", "properties": {
          "files": {"type": "array", "items": {"type": "string"}},
          "output": {"type": "string"},
          "format": {"type": "string", "default": "zip"}
      }, "required": ["files", "output"]})
def compress_files(files: List[str], output: str, format: str = "zip") -> dict:
    out_path = Path(output).expanduser().resolve()
    safe, error = _is_safe_path(out_path, "write")
    if not safe:
        return {"status": "error", "error": error}

    try:
        if format == "zip":
            with zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in files:
                    p = Path(file_path).expanduser().resolve()
                    if p.is_file():
                        zf.write(p, p.name)
                    elif p.is_dir():
                        for item in p.rglob("*"):
                            if item.is_file():
                                zf.write(item, item.relative_to(p.parent))
        elif format in ("tar", "tar.gz"):
            mode = "w:gz" if format == "tar.gz" else "w"
            with tarfile.open(out_path, mode) as tf:
                for file_path in files:
                    p = Path(file_path).expanduser().resolve()
                    if p.exists():
                        tf.add(p, arcname=p.name)
        else:
            return {"status": "error", "error": f"Format non supporté: {format}"}

        size = out_path.stat().st_size
        return {"status": "success", "archive": str(out_path),
                "size": _format_size(size), "files_added": len(files)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

@tool(
    name="extract_archive",
    description=(
        "Extrait une archive ou liste son contenu sans l'extraire. "
        "Formats supportés : .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tar.xz. "
        "Protégé contre le zip-slip (path traversal). "
        "Avec liste_seulement=true, retourne le contenu sans rien écrire sur disque."
    ),
    parameters={
        "type": "object",
        "properties": {
            "archive": {
                "type": "string",
                "description": "Chemin de l'archive à traiter.",
            },
            "destination": {
                "type": "string",
                "description": "Dossier de destination (défaut : même dossier que l'archive).",
            },
            "liste_seulement": {
                "type": "boolean",
                "description": (
                    "Si true, liste le contenu de l'archive sans extraire (défaut: false)."
                ),
            },
            "sous_dossier": {
                "type": "boolean",
                "description": (
                    "Si true (défaut), extrait dans un sous-dossier portant le nom de l'archive "
                    "pour éviter de polluer la destination."
                ),
            },
        },
        "required": ["archive"],
    },
)
def extract_archive(
    archive: str,
    destination: Optional[str] = None,
    liste_seulement: bool = False,
    sous_dossier: bool = True,
) -> dict:
    arc_path = Path(archive).expanduser().resolve()

    if not arc_path.exists():
        return {"status": "error", "error": "Archive introuvable"}

    safe, error = _is_safe_path(arc_path, "read")
    if not safe:
        return {"status": "error", "error": error}

    # Détecter le format
    name_lower = arc_path.name.lower()
    if name_lower.endswith(".zip"):
        fmt = "zip"
    elif name_lower.endswith((".tar.gz", ".tgz")):
        fmt = "tar"
        tar_mode = "r:gz"
    elif name_lower.endswith(".tar.bz2"):
        fmt = "tar"
        tar_mode = "r:bz2"
    elif name_lower.endswith(".tar.xz"):
        fmt = "tar"
        tar_mode = "r:xz"
    elif name_lower.endswith(".tar"):
        fmt = "tar"
        tar_mode = "r:"
    else:
        return {"status": "error", "error": f"Format non reconnu : {arc_path.suffix}"}

    # ── Mode listing ──────────────────────────────────────────────────────────
    if liste_seulement:
        try:
            if fmt == "zip":
                with zipfile.ZipFile(arc_path, "r") as zf:
                    entries = []
                    for info in zf.infolist():
                        entries.append({
                            "nom":   info.filename,
                            "taille": _format_size(info.file_size),
                            "compresse": _format_size(info.compress_size),
                            "dossier": info.filename.endswith("/"),
                        })
            else:
                with tarfile.open(arc_path, tar_mode) as tf:
                    entries = []
                    for member in tf.getmembers():
                        entries.append({
                            "nom":   member.name,
                            "taille": _format_size(member.size),
                            "compresse": None,
                            "dossier": member.isdir(),
                        })
            return {
                "status": "success",
                "archive": str(arc_path),
                "format": fmt.upper(),
                "nombre_entrees": len(entries),
                "entrees": entries[:100],
                "tronque": len(entries) > 100,
            }
        except Exception as e:
            return {"status": "error", "error": f"Erreur lecture archive : {e}"}

    # ── Mode extraction ───────────────────────────────────────────────────────
    if destination:
        dst_base = Path(destination).expanduser().resolve()
    else:
        dst_base = arc_path.parent

    if sous_dossier:
        # Retirer toutes les extensions connues pour obtenir le nom de base
        stem = arc_path.name
        for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tar", ".zip"):
            if stem.lower().endswith(ext):
                stem = stem[: -len(ext)]
                break
        dst_path = dst_base / stem
    else:
        dst_path = dst_base

    safe, error = _is_safe_path(dst_path, "write")
    if not safe:
        return {"status": "error", "error": error}

    try:
        dst_path.mkdir(parents=True, exist_ok=True)

        if fmt == "zip":
            with zipfile.ZipFile(arc_path, "r") as zf:
                # Protection zip-slip
                for member in zf.infolist():
                    member_path = (dst_path / member.filename).resolve()
                    if not str(member_path).startswith(str(dst_path)):
                        return {
                            "status": "error",
                            "error": f"Zip-slip détecté : '{member.filename}' sort de la destination.",
                        }
                zf.extractall(dst_path)
                nb = len(zf.namelist())

        else:
            with tarfile.open(arc_path, tar_mode) as tf:
                # Protection zip-slip
                for member in tf.getmembers():
                    member_path = (dst_path / member.name).resolve()
                    if not str(member_path).startswith(str(dst_path)):
                        return {
                            "status": "error",
                            "error": f"Path traversal détecté : '{member.name}' sort de la destination.",
                        }
                tf.extractall(dst_path)
                nb = len(tf.getmembers())

        return {
            "status":          "success",
            "archive":         str(arc_path),
            "extrait_dans":    str(dst_path),
            "fichiers_extraits": nb,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


# ====================================================================================
# COMPARAISON (1 outil)
# ====================================================================================

@tool(
    name="diff_files",
    description=(
        "Compare deux fichiers texte (ou deux chaînes) et retourne leurs différences. "
        "Produit un diff unifié (patch-style) ou côte-à-côte, avec statistiques "
        "(lignes ajoutées, supprimées, modifiées). "
        "Idéal pour : comparer des versions de code, vérifier des modifications de config, "
        "valider un find_and_replace avant de l'appliquer."
    ),
    parameters={
        "type": "object",
        "properties": {
            "source_a": {
                "type": "string",
                "description": "Chemin du premier fichier, ou texte brut si texte_brut=true.",
            },
            "source_b": {
                "type": "string",
                "description": "Chemin du second fichier, ou texte brut si texte_brut=true.",
            },
            "texte_brut": {
                "type": "boolean",
                "description": (
                    "Si true, source_a et source_b sont traités comme du texte brut "
                    "plutôt que comme des chemins de fichiers (défaut: false)."
                ),
            },
            "contexte": {
                "type": "integer",
                "description": "Nombre de lignes de contexte autour des changements (défaut: 3).",
            },
            "mode": {
                "type": "string",
                "description": (
                    "Format de sortie : "
                    "'unifie' (défaut) — diff patch standard, "
                    "'cote_a_cote' — tableau aligné colonne A | colonne B, "
                    "'stats' — statistiques uniquement sans le diff."
                ),
                "enum": ["unifie", "cote_a_cote", "stats"],
            },
            "ignorer_casse": {
                "type": "boolean",
                "description": "Ignore les différences de casse (défaut: false).",
            },
            "ignorer_espaces": {
                "type": "boolean",
                "description": "Ignore les espaces en début/fin de ligne (défaut: false).",
            },
        },
        "required": ["source_a", "source_b"],
    },
)
def diff_files(
    source_a: str,
    source_b: str,
    texte_brut: bool = False,
    contexte: int = 3,
    mode: str = "unifie",
    ignorer_casse: bool = False,
    ignorer_espaces: bool = False,
) -> dict:

    # ── Chargement du contenu ─────────────────────────────────────────────────
    if texte_brut:
        content_a = source_a
        content_b = source_b
        label_a = "<texte_a>"
        label_b = "<texte_b>"
    else:
        path_a = Path(source_a).expanduser().resolve()
        path_b = Path(source_b).expanduser().resolve()

        for p in (path_a, path_b):
            safe, error = _is_safe_path(p, "read")
            if not safe:
                return {"status": "error", "error": error}
            if not p.exists():
                return {"status": "error", "error": f"Fichier introuvable : {p}"}

        try:
            content_a = path_a.read_text(encoding="utf-8", errors="replace")
            content_b = path_b.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return {"status": "error", "error": f"Erreur lecture : {e}"}

        label_a = str(path_a)
        label_b = str(path_b)

    # ── Normalisation optionnelle ─────────────────────────────────────────────
    def _normalize(lines: list[str]) -> list[str]:
        result = lines
        if ignorer_espaces:
            result = [l.strip() + "\n" for l in result]
        if ignorer_casse:
            result = [l.lower() for l in result]
        return result

    lines_a = content_a.splitlines(keepends=True)
    lines_b = content_b.splitlines(keepends=True)

    lines_a_cmp = _normalize(lines_a)
    lines_b_cmp = _normalize(lines_b)

    # ── Statistiques ─────────────────────────────────────────────────────────
    matcher = difflib.SequenceMatcher(None, lines_a_cmp, lines_b_cmp, autojunk=False)
    ajoutees = supprimees = modifiees = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            ajoutees += j2 - j1
        elif tag == "delete":
            supprimees += i2 - i1
        elif tag == "replace":
            n = max(i2 - i1, j2 - j1)
            modifiees += n

    stats = {
        "lignes_a":        len(lines_a),
        "lignes_b":        len(lines_b),
        "ajoutees":        ajoutees,
        "supprimees":      supprimees,
        "modifiees":       modifiees,
        "identique":       ajoutees == 0 and supprimees == 0 and modifiees == 0,
    }

    if mode == "stats" or stats["identique"]:
        return {
            "status":  "success",
            "label_a": label_a,
            "label_b": label_b,
            "stats":   stats,
            "diff":    None if stats["identique"] else "(non calculé en mode stats)",
        }

    # ── Mode unifié ───────────────────────────────────────────────────────────
    if mode == "unifie":
        diff_lines = list(difflib.unified_diff(
            lines_a_cmp, lines_b_cmp,
            fromfile=label_a,
            tofile=label_b,
            n=contexte,
        ))
        diff_text = "".join(diff_lines)

        # Tronquer si trop long
        MAX_DIFF = 20_000
        tronque = len(diff_text) > MAX_DIFF
        if tronque:
            diff_text = diff_text[:MAX_DIFF] + "\n... [diff tronqué]"

        return {
            "status":  "success",
            "label_a": label_a,
            "label_b": label_b,
            "stats":   stats,
            "diff":    diff_text,
            "tronque": tronque,
        }

    # ── Mode côte-à-côte ──────────────────────────────────────────────────────
    if mode == "cote_a_cote":
        table = list(difflib.ndiff(lines_a_cmp, lines_b_cmp))

        rows = []
        col_a: Optional[str] = None
        col_b: Optional[str] = None

        for line in table:
            tag = line[:2]
            text = line[2:].rstrip("\n")
            if tag == "  ":        # inchangé
                rows.append({"etat": "=", "a": text, "b": text})
            elif tag == "- ":      # supprimé
                col_a = text
                col_b = None
            elif tag == "+ ":      # ajouté
                if col_a is not None:
                    rows.append({"etat": "~", "a": col_a, "b": text})
                    col_a = None
                else:
                    rows.append({"etat": "+", "a": "", "b": text})
            elif tag == "? ":
                pass              # hints difflib, ignorés
        if col_a is not None:
            rows.append({"etat": "-", "a": col_a, "b": ""})

        MAX_ROWS = 500
        tronque = len(rows) > MAX_ROWS
        return {
            "status":  "success",
            "label_a": label_a,
            "label_b": label_b,
            "stats":   stats,
            "tableau": rows[:MAX_ROWS],
            "tronque": tronque,
            "legende": {"=": "identique", "~": "modifiée", "+": "ajoutée", "-": "supprimée"},
        }

    return {"status": "error", "error": f"Mode inconnu : {mode}"}


# ====================================================================================
# BATCH (2 outils)
# ====================================================================================

@tool(name="batch_rename", description="Renomme plusieurs fichiers.",
      parameters={"type": "object", "properties": {
          "path": {"type": "string"},
          "find": {"type": "string"},
          "replace": {"type": "string"},
          "pattern": {"type": "string", "default": "*"},
          "preview": {"type": "boolean", "default": True}
      }, "required": ["path", "find", "replace"]})
def batch_rename(path: str, find: str, replace: str, pattern: str = "*",
                 preview: bool = True) -> dict:
    p = Path(path).expanduser().resolve()
    if not p.is_dir():
        return {"status": "error", "error": "Pas un dossier"}

    renames = []
    for file in p.glob(pattern):
        if find in file.name:
            new_name = file.name.replace(find, replace)
            new_path = file.parent / new_name

            if not preview:
                try:
                    file.rename(new_path)
                    renames.append({"from": file.name, "to": new_name, "done": True})
                except:
                    renames.append({"from": file.name, "to": new_name, "done": False})
            else:
                renames.append({"from": file.name, "to": new_name})

    return {"status": "success", "mode": "preview" if preview else "applied",
            "renamed": len(renames), "results": renames[:20]}

@tool(name="batch_delete", description="Supprime plusieurs fichiers (confirmation requise).",
      parameters={"type": "object", "properties": {
          "files": {"type": "array", "items": {"type": "string"}},
          "confirm": {"type": "boolean"}
      }, "required": ["files", "confirm"]})
def batch_delete(files: List[str], confirm: bool) -> dict:
    if not confirm:
        return {"status": "cancelled", "message": "Suppression annulée"}

    deleted = []
    errors = []

    for file_path in files:
        p = Path(file_path).expanduser().resolve()
        safe, error = _is_safe_path(p, "delete")
        if not safe:
            errors.append({"file": str(p), "error": error})
            continue

        try:
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                shutil.rmtree(p)
            deleted.append(str(p))
        except Exception as e:
            errors.append({"file": str(p), "error": str(e)})

    return {"status": "success", "deleted": len(deleted), "errors": len(errors),
            "deleted_files": deleted[:20], "error_files": errors[:10]}
