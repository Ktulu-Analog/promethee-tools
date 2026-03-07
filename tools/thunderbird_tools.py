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
tools/thunderbird_tools.py — Outils d'accès à Thunderbird (mails + agenda)
===========================================================================

Outils exposés (12) :

  Mails — lecture (3) :
    - tb_list_mails         : liste les N derniers mails d'un dossier
                              (aliases fr/en intégrés, filtres date inclus)
    - tb_search_mails       : recherche multicritères dans les mails
    - tb_read_mail          : lit un mail complet (headers + corps + PJ)

  Mails — écriture (3, Thunderbird doit être fermé) :
    - tb_mark_mail          : marque un mail (lu, non-lu, important, supprimé)
    - tb_move_mail          : déplace un mail vers un autre dossier
    - tb_create_draft       : crée un brouillon ou prépare une réponse

  Agenda — lecture (3) :
    - tb_agenda_upcoming    : événements des N prochains jours
    - tb_agenda_search      : recherche par titre, date, participant, lieu
    - tb_todo_list          : liste les tâches (todos) avec statut

  Agenda — écriture (3, Thunderbird doit être fermé) :
    - tb_agenda_create      : crée un événement dans l'agenda local
    - tb_agenda_update      : modifie un événement existant
    - tb_agenda_delete      : supprime un événement ou une tâche

Stratégie d'accès :
  - Mails     : global-messages-db.sqlite (Gloda) en lecture immutable
                + fichiers mbox via mailbox.mbox() pour le contenu complet
  - Agenda    : calendar-data/local.sqlite en lecture/écriture
  - Écriture  : toujours protégée par _check_tb_closed() qui vérifie que
                le processus Thunderbird n'est pas en cours d'exécution

Profil :
  Détection automatique de ~/.thunderbird/*.default-release ou *.default
  Surcharge possible via la variable d'environnement TB_PROFILE_PATH

Note :
  tb_find_profile et tb_list_folders sont des helpers internes non exposés
  comme outils LLM. Chaque outil est autonome et résout lui-même le profil
  et les dossiers, ce qui évite des appels préliminaires inutiles.

Usage :
    import tools.thunderbird_tools   # suffit à enregistrer les outils
"""

import email
import email.policy
import email.utils
import json
import mailbox
import os
import re
import sqlite3
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from core.tools_engine import tool, set_current_family, _TOOL_ICONS

set_current_family("thunderbird_tools", "Thunderbird", "📧")

# ── Icônes UI ──────────────────────────────────────────────────────────────────
_TOOL_ICONS.update({
    "tb_list_mails":      "📬",
    "tb_search_mails":    "🔎",
    "tb_read_mail":       "📧",
    "tb_mark_mail":       "🏷️",
    "tb_move_mail":       "📤",
    "tb_create_draft":    "✏️",
    "tb_agenda_upcoming": "📅",
    "tb_agenda_search":   "🗓️",
    "tb_todo_list":       "✅",
    "tb_agenda_create":   "➕",
    "tb_agenda_update":   "🔄",
    "tb_agenda_delete":   "🗑️",
})


# ══════════════════════════════════════════════════════════════════════════════
# Helpers internes
# ══════════════════════════════════════════════════════════════════════════════

def _find_tb_profile() -> tuple[bool, Path | str]:
    """
    Détecte le profil Thunderbird actif.
    Priorité : Config.TB_PROFILE_PATH > TB_PROFILE_PATH env > *.default-release > *.default

    Returns:
        (success, profile_path | error_message)
    """
    # 1. Valeur dans Config (lue depuis .env via dotenv)
    from core.config import Config
    config_path = Config.TB_PROFILE_PATH.strip()
    if config_path:
        p = Path(config_path).expanduser()
        if p.is_dir():
            return True, p
        return False, (
            f"TB_PROFILE_PATH invalide dans .env : '{config_path}' n'est pas un dossier."
        )

    # 2. Variable d'environnement brute (surcharge manuelle au lancement)
    env_path = os.environ.get("TB_PROFILE_PATH")
    if env_path:
        p = Path(env_path).expanduser()
        if p.is_dir():
            return True, p
        return False, f"TB_PROFILE_PATH invalide : {env_path}"

    tb_dir = Path.home() / ".thunderbird"
    if not tb_dir.exists():
        return False, "Répertoire ~/.thunderbird introuvable. Thunderbird est-il installé ?"

    # Chercher dans profiles.ini le profil par défaut
    profiles_ini = tb_dir / "profiles.ini"
    if profiles_ini.exists():
        content = profiles_ini.read_text(errors="replace")
        # Chercher Default=1 dans les sections
        sections = re.split(r'\[Profile\d+\]', content)
        for section in sections:
            if "Default=1" in section or "default-release" in section.lower():
                m = re.search(r'Path=(.+)', section)
                if m:
                    rel = m.group(1).strip()
                    if rel.startswith("/"):
                        candidate = Path(rel)
                    else:
                        candidate = tb_dir / rel
                    if candidate.is_dir():
                        return True, candidate

    # Fallback : chercher les répertoires de profil classiques
    for pattern in ("*.default-release", "*.default"):
        candidates = sorted(tb_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            return True, candidates[0]

    return False, "Aucun profil Thunderbird trouvé dans ~/.thunderbird"


def _check_tb_closed() -> tuple[bool, str]:
    """
    Vérifie que Thunderbird n'est pas en cours d'exécution.
    Obligatoire avant toute opération d'écriture.

    Returns:
        (is_closed, message)
    """
    try:
        result = subprocess.run(
            ["pgrep", "-x", "thunderbird"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            pids = result.stdout.strip()
            return False, (
                f"Thunderbird est en cours d'exécution (PID : {pids}). "
                "Fermez Thunderbird avant d'effectuer des opérations d'écriture."
            )
        return True, "OK"
    except FileNotFoundError:
        # pgrep non disponible, essayer ps
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True
            )
            if "thunderbird" in result.stdout.lower():
                return False, "Thunderbird semble en cours d'exécution. Fermez-le avant d'écrire."
        except Exception:
            pass
        return True, "OK (vérification de processus non disponible)"


def _open_gloda(profile: Path) -> sqlite3.Connection:
    """
    Ouvre global-messages-db.sqlite en lecture seule immutable.
    Le mode immutable permet de lire même quand TB a un verrou WAL.
    """
    db_path = profile / "global-messages-db.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(
            f"Base Gloda introuvable : {db_path}\n"
            "Thunderbird doit avoir été lancé au moins une fois."
        )
    uri = f"file:{db_path}?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _open_calendar(profile: Path, readonly: bool = True) -> sqlite3.Connection:
    """Ouvre calendar-data/local.sqlite (lecture ou lecture/écriture)."""
    db_path = profile / "calendar-data" / "local.sqlite"
    if not db_path.exists():
        raise FileNotFoundError(
            f"Base agenda introuvable : {db_path}\n"
            "Le Lightning/Thunderbird Calendar doit avoir été utilisé au moins une fois."
        )
    if readonly:
        uri = f"file:{db_path}?mode=ro&immutable=1"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _folder_columns(conn: sqlite3.Connection) -> set[str]:
    """
    Retourne l'ensemble des colonnes disponibles dans folderLocations.
    Permet d'adapter les requêtes au schéma réel (qui varie selon la version de Gloda).
    """
    rows = conn.execute("PRAGMA table_info(folderLocations)").fetchall()
    return {row["name"] for row in rows}


def _select_folder_cols(conn: sqlite3.Connection) -> str:
    """
    Retourne la clause SELECT adaptée au schéma réel de folderLocations.
    Inclut 'uri' seulement si la colonne existe.
    """
    cols = _folder_columns(conn)
    parts = ["id", "name"]
    if "uri" in cols:
        parts.append("uri")
    if "folderType" in cols:
        parts.append("folderType")
    return ", ".join(parts)


def _folder_uri(row: sqlite3.Row, profile: Path) -> str:
    """
    Retourne l'URI d'un dossier depuis la ligne Gloda, ou la reconstruit
    depuis le filesystem si la colonne 'uri' est absente du schéma.
    """
    try:
        uri = row["uri"]
        if uri:
            return uri
    except IndexError:
        pass

    # Fallback : reconstruire un URI à partir du nom et du profil
    name = (row["name"] or "").strip()
    # Chercher le fichier mbox correspondant dans Mail/ et ImapMail/
    for mail_root in (profile / "Mail", profile / "ImapMail"):
        if not mail_root.exists():
            continue
        for srv_dir in mail_root.iterdir():
            if not srv_dir.is_dir():
                continue
            candidate = srv_dir / name
            if candidate.exists():
                # Reconstruire un URI mailbox canonique
                rel = candidate.relative_to(profile / "Mail") if mail_root.name == "Mail" else None
                if rel:
                    return f"mailbox://nobody@Local%20Folders/{name}"
                return f"imap://user@{srv_dir.name}/{name}"
    return ""


def _find_mbox(profile: Path, folder_uri: str) -> Optional[Path]:
    """
    Résout un URI de dossier Gloda (ex: mailbox://nobody@Local Folders/INBOX)
    vers le chemin du fichier mbox correspondant.
    """
    # URI typiques :
    #   mailbox://nobody@Local%20Folders/Inbox
    #   imap://user@server/INBOX
    uri = folder_uri.replace("%20", " ").replace("%2F", "/")

    # Dossiers locaux
    local_m = re.search(r'Local Folders[/\\](.+)', uri, re.IGNORECASE)
    if local_m:
        rel = local_m.group(1).replace("/", os.sep)
        candidate = profile / "Mail" / "Local Folders" / rel
        if candidate.exists():
            return candidate
        # Sans extension
        for name in [rel, rel.split(os.sep)[-1]]:
            for base in (profile / "Mail" / "Local Folders").glob("**"):
                if base.stem.lower() == name.lower() and not base.suffix:
                    return base

    # Dossiers IMAP : chercher dans ImapMail/
    imap_m = re.search(r'imap://[^/]+@([^/]+)/(.+)', uri, re.IGNORECASE)
    if imap_m:
        server = imap_m.group(1)
        folder = imap_m.group(2).replace("/", os.sep)
        imap_root = profile / "ImapMail"
        # Le répertoire du serveur peut avoir un suffixe
        for srv_dir in imap_root.iterdir() if imap_root.exists() else []:
            if server.lower() in srv_dir.name.lower():
                candidate = srv_dir / folder
                if candidate.exists():
                    return candidate
    return None


def _read_mbox_at_offset(mbox_path: Path, message_key: int) -> "Optional[email.message.Message]":
    """
    Lit un message dans un fichier mbox en utilisant le byte offset (messageKey Thunderbird).

    Dans Thunderbird, messageKey pour les dossiers locaux correspond au byte offset
    de la ligne "From " qui commence le message dans le fichier mbox.
    Ce n'est PAS un index ordinal Python — mailbox.mbox.get(messageKey) est donc
    presque toujours None (bug corrigé ici).

    Pour IMAP, messageKey est l'UID IMAP et ne peut pas être utilisé comme offset ;
    dans ce cas on retourne None et le fallback par sujet/Message-ID prend le relais.
    """
    try:
        with open(mbox_path, "rb") as f:
            # Vérifier que l'offset pointe bien sur une ligne "From "
            f.seek(message_key)
            header = f.read(5)
            if header != b"From ":
                return None  # messageKey = UID IMAP, pas un byte offset
            # Relire depuis le début de la ligne jusqu'au prochain séparateur mbox
            f.seek(message_key)
            chunks: list[bytes] = []
            first = True
            for raw_line in f:
                if not first and raw_line.startswith(b"From "):
                    break
                chunks.append(raw_line)
                first = False
        return email.message_from_bytes(b"".join(chunks))
    except (OSError, ValueError):
        return None


def _ts_to_dt(ts_microseconds: Optional[int]) -> Optional[str]:
    """Convertit un timestamp Thunderbird (microsecondes) en chaîne ISO."""
    if ts_microseconds is None:
        return None
    try:
        dt = datetime.fromtimestamp(ts_microseconds / 1_000_000, tz=timezone.utc)
        return dt.astimezone().strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts_microseconds)


def _dt_to_ts(dt_str: str) -> int:
    """Convertit une chaîne ISO en timestamp Thunderbird (microsecondes UTC)."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(dt_str, fmt)
            # Considérer l'heure locale
            local_ts = dt.timestamp()
            return int(local_ts * 1_000_000)
        except ValueError:
            continue
    raise ValueError(f"Format de date non reconnu : '{dt_str}'. Utilisez YYYY-MM-DD HH:MM")


def _decode_header(val: Optional[str]) -> str:
    """Décode un en-tête email encodé (RFC 2047)."""
    if not val:
        return ""
    try:
        parts = email.header.decode_header(val)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(part)
        return " ".join(decoded)
    except Exception:
        return str(val)


def _extract_body(msg) -> tuple[str, str]:
    """
    Extrait le corps texte et HTML d'un message email.

    Returns:
        (text_body, html_body)
    """
    text_parts, html_parts = [], []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            charset = part.get_content_charset() or "utf-8"
            if ct == "text/plain":
                try:
                    text_parts.append(part.get_payload(decode=True).decode(charset, errors="replace"))
                except Exception:
                    pass
            elif ct == "text/html":
                try:
                    html_parts.append(part.get_payload(decode=True).decode(charset, errors="replace"))
                except Exception:
                    pass
    else:
        charset = msg.get_content_charset() or "utf-8"
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                content = payload.decode(charset, errors="replace")
                if msg.get_content_type() == "text/html":
                    html_parts.append(content)
                else:
                    text_parts.append(content)
        except Exception:
            pass

    return "\n".join(text_parts), "\n".join(html_parts)


def _list_attachments(msg) -> list[dict]:
    """Liste les pièces jointes d'un message."""
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd or part.get_filename():
                name = _decode_header(part.get_filename() or "inconnu")
                payload = part.get_payload(decode=True)
                size = len(payload) if payload else 0
                attachments.append({
                    "nom": name,
                    "type": part.get_content_type(),
                    "taille": f"{size:,} octets",
                })
    return attachments


# ══════════════════════════════════════════════════════════════════════════════
# OUTILS — Mails / Lecture
# ══════════════════════════════════════════════════════════════════════════════

def tb_find_profile() -> dict:
    """Wrapper interne — non exposé comme outil LLM."""
    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}

    profile = result
    info = {
        "status": "success",
        "profile_path": str(profile),
    }

    # Présence des bases
    info["gloda_disponible"] = (profile / "global-messages-db.sqlite").exists()
    info["agenda_disponible"] = (profile / "calendar-data" / "local.sqlite").exists()

    # Dossiers mail disponibles
    mail_roots = []
    for sub in ["Mail", "ImapMail"]:
        root = profile / sub
        if root.exists():
            for srv in root.iterdir():
                if srv.is_dir():
                    mail_roots.append(str(srv))
    info["racines_mail"] = mail_roots

    return info


def tb_list_folders() -> dict:
    """Wrapper interne — non exposé comme outil LLM."""
    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result

    try:
        conn = _open_gloda(profile)
    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}

    try:
        sel = _select_folder_cols(conn)
        order = "uri" if "uri" in _folder_columns(conn) else "name"
        rows = conn.execute(
            f"SELECT {sel} FROM folderLocations ORDER BY {order}"
        ).fetchall()
    except Exception as e:
        conn.close()
        return {"status": "error", "error": f"Impossible de lire les dossiers : {e}"}
    finally:
        conn.close()

    folders = []
    for row in rows:
        entry = {
            "id":  row["id"],
            "nom": row["name"] or "(sans nom)",
            "uri": _folder_uri(row, profile),
        }
        folders.append(entry)

    return {
        "status": "success",
        "nombre": len(folders),
        "dossiers": folders,
    }


@tool(
    name="tb_list_mails",
    description=(
        "Liste les N derniers mails d'un dossier Thunderbird. "
        "Retourne : sujet, expéditeur, date, statut (lu/non-lu), présence de PJ. "
        "Accepte des noms courants en français ou anglais : "
        "'inbox'/'boite de reception', 'sent'/'envoyés'/'envoyes', "
        "'drafts'/'brouillons', 'trash'/'corbeille', 'archives'. "
        "Pour filtrer par date, utiliser les paramètres 'aujourd_hui', 'depuis', 'jusqu_a'. "
        "Aucun appel préalable à d'autres outils n'est nécessaire."
    ),
    parameters={
        "type": "object",
        "properties": {
            "dossier": {
                "type": "string",
                "description": (
                    "Nom du dossier. Accepte les alias courants : "
                    "'sent'/'envoyés' pour les envoyés, 'inbox' pour la boîte de réception, "
                    "'drafts'/'brouillons', 'trash'/'corbeille'. Défaut : 'inbox'."
                ),
            },
            "limite": {
                "type": "integer",
                "description": "Nombre maximum de mails à retourner (défaut: 20, max: 100).",
            },
            "non_lus_seulement": {
                "type": "boolean",
                "description": "Si true, retourne uniquement les mails non lus.",
            },
            "aujourd_hui": {
                "type": "boolean",
                "description": "Si true, retourne uniquement les mails du jour.",
            },
            "depuis": {
                "type": "string",
                "description": "Date de début au format YYYY-MM-DD (optionnel).",
            },
            "jusqu_a": {
                "type": "string",
                "description": "Date de fin au format YYYY-MM-DD (optionnel).",
            },
        },
        "required": [],
    },
)
def tb_list_mails(
    dossier: str = "inbox",
    limite: int = 20,
    non_lus_seulement: bool = False,
    aujourd_hui: bool = False,
    depuis: Optional[str] = None,
    jusqu_a: Optional[str] = None,
) -> dict:
    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result
    limite = min(max(1, limite), 100)

    # Aliases de dossiers courants (fr + en)
    _FOLDER_ALIASES = {
        "envoyés": ["sent", "envoyes", "envoyés", "sent messages", "sent mail"],
        "inbox":   ["inbox", "boite de reception", "boîte de réception", "reception"],
        "drafts":  ["drafts", "brouillons", "brouillon"],
        "trash":   ["trash", "corbeille", "deleted", "deleted messages", "poubelle"],
        "archives": ["archives", "archive"],
        "spam":    ["spam", "junk", "indésirables"],
    }

    def _normalize(name: str) -> str:
        """Retourne le nom canonique ou l'original si non reconnu."""
        n = name.lower().strip()
        for canonical, aliases in _FOLDER_ALIASES.items():
            if n in aliases or n == canonical:
                return canonical
        return n

    dossier_norm = _normalize(dossier)

    try:
        conn = _open_gloda(profile)
    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}

    try:
        sel = _select_folder_cols(conn)
        has_uri = "uri" in _folder_columns(conn)
        folders = conn.execute(f"SELECT {sel} FROM folderLocations").fetchall()

        folder_id = None
        folder_name_found = dossier
        for f in folders:
            name = (f["name"] or "").lower().strip()
            uri  = (f["uri"] if has_uri else "") or ""
            uri  = uri.lower()
            # Correspondance directe ou via aliases
            for alias in _FOLDER_ALIASES.get(dossier_norm, [dossier_norm]):
                if name == alias or uri.endswith("/" + alias) or uri.endswith("/" + alias.replace(" ", "%20")):
                    folder_id = f["id"]
                    folder_name_found = f["name"]
                    break
            if folder_id:
                break

        if folder_id is None:
            # Fallback : correspondance partielle sur le nom
            for f in folders:
                if dossier_norm in (f["name"] or "").lower():
                    folder_id = f["id"]
                    folder_name_found = f["name"]
                    break

        if folder_id is None:
            available = sorted({f["name"] for f in folders if f["name"]})
            conn.close()
            return {
                "status": "error",
                "error": (
                    f"Dossier '{dossier}' introuvable. "
                    f"Dossiers disponibles : {', '.join(available)}"
                ),
            }

        conditions = ["folderID = ?"]
        params: list = [folder_id]

        if non_lus_seulement:
            conditions.append("(flags & 1) = 0")

        if aujourd_hui:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end   = today_start.replace(hour=23, minute=59, second=59)
            conditions.append("date >= ?")
            conditions.append("date <= ?")
            params.append(int(today_start.timestamp() * 1_000_000))
            params.append(int(today_end.timestamp()   * 1_000_000))
        else:
            if depuis:
                try:
                    conditions.append("date >= ?")
                    params.append(_dt_to_ts(depuis + " 00:00"))
                except ValueError as e:
                    conn.close()
                    return {"status": "error", "error": str(e)}
            if jusqu_a:
                try:
                    conditions.append("date <= ?")
                    params.append(_dt_to_ts(jusqu_a + " 23:59"))
                except ValueError as e:
                    conn.close()
                    return {"status": "error", "error": str(e)}

        where = " AND ".join(conditions)
        rows = conn.execute(
            f"""SELECT id, messageKey, subject, author, recipients, date, flags, hasAttachments
                FROM messages
                WHERE {where}
                ORDER BY date DESC
                LIMIT ?""",
            params + [limite],
        ).fetchall()

        mails = []
        for r in rows:
            flags = r["flags"] or 0
            mails.append({
                "id": r["id"],
                "sujet": r["subject"] or "(sans sujet)",
                "expediteur": r["author"] or "",
                "destinataires": r["recipients"] or "",
                "date": _ts_to_dt(r["date"]),
                "lu": bool(flags & 1),
                "important": bool(flags & 4),
                "piece_jointe": bool(r["hasAttachments"]),
            })

    except Exception as e:
        return {"status": "error", "error": f"Erreur lecture mails : {e}"}
    finally:
        conn.close()

    return {
        "status": "success",
        "dossier": folder_name_found,
        "nombre": len(mails),
        "mails": mails,
    }


@tool(
    name="tb_search_mails",
    description=(
        "Recherche des mails dans Thunderbird selon plusieurs critères combinables. "
        "À utiliser quand on cherche un mail précis par contenu, expéditeur ou sujet, "
        "tous dossiers confondus ou dans un dossier spécifique. "
        "Pour lister les mails d'un dossier (ex: 'envoyés aujourd'hui'), "
        "préférer tb_list_mails qui est plus direct. "
        "Aucun appel préalable à d'autres outils n'est nécessaire. "
        "Accepte les mêmes alias de dossiers que tb_list_mails "
        "('sent'/'envoyés', 'inbox', 'drafts'/'brouillons', 'trash'/'corbeille')."
    ),
    parameters={
        "type": "object",
        "properties": {
            "texte": {
                "type": "string",
                "description": "Texte à rechercher dans le sujet et le corps (recherche plein texte).",
            },
            "expediteur": {
                "type": "string",
                "description": "Filtre sur l'adresse ou le nom de l'expéditeur.",
            },
            "sujet": {
                "type": "string",
                "description": "Filtre sur le sujet (recherche par sous-chaîne).",
            },
            "depuis": {
                "type": "string",
                "description": "Date de début au format YYYY-MM-DD.",
            },
            "jusqu_a": {
                "type": "string",
                "description": "Date de fin au format YYYY-MM-DD.",
            },
            "dossier": {
                "type": "string",
                "description": "Restreindre la recherche à un dossier spécifique.",
            },
            "non_lus_seulement": {
                "type": "boolean",
                "description": "Rechercher uniquement dans les mails non lus.",
            },
            "limite": {
                "type": "integer",
                "description": "Nombre maximum de résultats (défaut: 30, max: 200).",
            },
        },
        "required": [],
    },
)
def tb_search_mails(
    texte: Optional[str] = None,
    expediteur: Optional[str] = None,
    sujet: Optional[str] = None,
    depuis: Optional[str] = None,
    jusqu_a: Optional[str] = None,
    dossier: Optional[str] = None,
    non_lus_seulement: bool = False,
    limite: int = 30,
) -> dict:
    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result
    limite = min(max(1, limite), 200)

    if not any([texte, expediteur, sujet, depuis, jusqu_a, dossier, non_lus_seulement]):
        return {"status": "error", "error": "Au moins un critère de recherche est requis."}

    try:
        conn = _open_gloda(profile)
    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}

    try:
        conditions, params = [], []

        if expediteur:
            conditions.append("m.author LIKE ?")
            params.append(f"%{expediteur}%")

        if sujet:
            conditions.append("m.subject LIKE ?")
            params.append(f"%{sujet}%")

        if non_lus_seulement:
            conditions.append("(m.flags & 1) = 0")

        if depuis:
            try:
                ts = _dt_to_ts(depuis + " 00:00")
                conditions.append("m.date >= ?")
                params.append(ts)
            except ValueError as e:
                conn.close()
                return {"status": "error", "error": str(e)}

        if jusqu_a:
            try:
                ts = _dt_to_ts(jusqu_a + " 23:59")
                conditions.append("m.date <= ?")
                params.append(ts)
            except ValueError as e:
                conn.close()
                return {"status": "error", "error": str(e)}

        if dossier:
            has_uri = "uri" in _folder_columns(conn)
            sel = _select_folder_cols(conn)
            folders = conn.execute(f"SELECT {sel} FROM folderLocations").fetchall()
            folder_id = None
            for f in folders:
                name = (f["name"] or "").lower()
                uri  = ((f["uri"] if has_uri else "") or "").lower()
                if name == dossier.lower() or uri.endswith("/" + dossier.lower()):
                    folder_id = f["id"]
                    break
            if folder_id:
                conditions.append("m.folderID = ?")
                params.append(folder_id)

        # Recherche FTS dans le corps si texte fourni
        if texte:
            try:
                fts_rows = conn.execute(
                    "SELECT docid FROM messagesText WHERE messagesText MATCH ?",
                    (texte,)
                ).fetchall()
                fts_ids = [r["docid"] for r in fts_rows]
                # Combiner avec recherche dans le sujet
                subj_rows = conn.execute(
                    "SELECT id FROM messages WHERE subject LIKE ?",
                    (f"%{texte}%",)
                ).fetchall()
                subj_ids = [r["id"] for r in subj_rows]
                all_ids = list(set(fts_ids) | set(subj_ids))
                if not all_ids:
                    conn.close()
                    return {"status": "success", "nombre": 0, "resultats": [], "criteres": {"texte": texte}}
                placeholders = ",".join("?" * len(all_ids))
                conditions.append(f"m.id IN ({placeholders})")
                params.extend(all_ids)
            except sqlite3.OperationalError:
                # FTS non disponible, fallback sur sujet uniquement
                conditions.append("m.subject LIKE ?")
                params.append(f"%{texte}%")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        rows = conn.execute(
            f"""SELECT m.id, m.subject, m.author, m.recipients, m.date,
                       m.flags, m.hasAttachments, fl.name AS folder_name
                FROM messages m
                LEFT JOIN folderLocations fl ON m.folderID = fl.id
                WHERE {where_clause}
                ORDER BY m.date DESC
                LIMIT ?""",
            params + [limite],
        ).fetchall()

        resultats = []
        for r in rows:
            flags = r["flags"] or 0
            resultats.append({
                "id": r["id"],
                "sujet": r["subject"] or "(sans sujet)",
                "expediteur": r["author"] or "",
                "destinataires": r["recipients"] or "",
                "date": _ts_to_dt(r["date"]),
                "dossier": r["folder_name"] or "?",
                "lu": bool(flags & 1),
                "important": bool(flags & 4),
                "piece_jointe": bool(r["hasAttachments"]),
            })

    except Exception as e:
        return {"status": "error", "error": f"Erreur recherche : {e}"}
    finally:
        conn.close()

    criteres = {k: v for k, v in {
        "texte": texte, "expediteur": expediteur, "sujet": sujet,
        "depuis": depuis, "jusqu_a": jusqu_a, "dossier": dossier,
    }.items() if v}

    return {
        "status": "success",
        "nombre": len(resultats),
        "criteres": criteres,
        "resultats": resultats,
    }


@tool(
    name="tb_read_mail",
    description=(
        "Lit le contenu complet d'un mail Thunderbird : en-têtes, corps texte, "
        "liste des pièces jointes. "
        "Utiliser l'id retourné par tb_list_mails ou tb_search_mails."
    ),
    parameters={
        "type": "object",
        "properties": {
            "mail_id": {
                "type": "integer",
                "description": "ID du mail (champ 'id' retourné par tb_list_mails/tb_search_mails).",
            },
            "inclure_html": {
                "type": "boolean",
                "description": "Si true, inclure aussi le corps HTML brut (défaut: false).",
            },
        },
        "required": ["mail_id"],
    },
)
def tb_read_mail(mail_id: int, inclure_html: bool = False) -> dict:
    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result

    try:
        conn = _open_gloda(profile)
    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}

    try:
        has_uri = "uri" in _folder_columns(conn)
        fl_uri_col = "fl.uri AS folder_uri," if has_uri else ""
        row = conn.execute(
            f"""SELECT m.id, m.messageKey, m.subject, m.author, m.recipients,
                      m.date, m.flags, m.hasAttachments,
                      fl.id AS folder_id, {fl_uri_col} fl.name AS folder_name
               FROM messages m
               LEFT JOIN folderLocations fl ON m.folderID = fl.id
               WHERE m.id = ?""",
            (mail_id,)
        ).fetchone()
    except Exception as e:
        conn.close()
        return {"status": "error", "error": f"Erreur lecture index : {e}"}
    finally:
        conn.close()

    if not row:
        return {"status": "error", "error": f"Mail id={mail_id} introuvable."}

    flags = row["flags"] or 0
    result_dict = {
        "status": "success",
        "id": row["id"],
        "sujet": row["subject"] or "(sans sujet)",
        "expediteur": row["author"] or "",
        "destinataires": row["recipients"] or "",
        "date": _ts_to_dt(row["date"]),
        "dossier": row["folder_name"] or "?",
        "lu": bool(flags & 1),
        "important": bool(flags & 4),
    }

    # Résoudre l'URI du dossier (depuis la colonne ou par reconstruction)
    try:
        folder_uri = row["folder_uri"] or ""
    except IndexError:
        folder_uri = ""

    # Lire le contenu depuis le fichier mbox
    mbox_path = _find_mbox(profile, folder_uri)
    if mbox_path:
        try:
            msg_key = row["messageKey"]
            msg = None

            # Méthode 1 : lecture directe par byte offset (messageKey = byte offset pour mbox local).
            # mailbox.mbox.get(n) utilise un index ordinal Python ≠ byte offset Gloda → bug corrigé.
            if msg_key is not None:
                msg = _read_mbox_at_offset(mbox_path, msg_key)

            # Fallback : parcourir la mbox et matcher par sujet + expéditeur.
            # Utilisé pour les dossiers IMAP (messageKey = UID, pas un byte offset)
            # ou si l'offset pointe vers une position non-valide.
            if msg is None:
                mbox = mailbox.mbox(str(mbox_path), create=False)
                for key in mbox.keys():
                    candidate = mbox.get(key)
                    if candidate:
                        subj = _decode_header(candidate.get("Subject", ""))
                        frm  = _decode_header(candidate.get("From", ""))
                        # Matcher sujet + expéditeur pour éviter les faux positifs
                        if (subj == (row["subject"] or "")
                                and (not row["author"]
                                     or row["author"] in frm
                                     or frm in (row["author"] or ""))):
                            msg = candidate
                            break
                mbox.close()

            if msg:
                # Headers complémentaires
                result_dict["cc"] = _decode_header(msg.get("Cc", ""))
                result_dict["reply_to"] = _decode_header(msg.get("Reply-To", ""))
                result_dict["message_id"] = msg.get("Message-ID", "")

                text_body, html_body = _extract_body(msg)
                # Nettoyer le corps texte
                result_dict["corps"] = text_body.strip()[:8000]  # limiter à 8 ko

                if inclure_html and html_body:
                    result_dict["corps_html"] = html_body[:16000]

                result_dict["pieces_jointes"] = _list_attachments(msg)
                mbox.close()
            else:
                result_dict["corps"] = "(Corps non disponible dans le fichier mbox)"
                result_dict["pieces_jointes"] = []
        except Exception as e:
            result_dict["corps"] = f"(Erreur lecture mbox : {e})"
            result_dict["pieces_jointes"] = []
    else:
        result_dict["corps"] = (
            "(Fichier mbox introuvable. Le message n'est peut-être pas en cache local.)"
        )
        result_dict["pieces_jointes"] = []

    return result_dict


# ══════════════════════════════════════════════════════════════════════════════
# OUTILS — Mails / Écriture
# ══════════════════════════════════════════════════════════════════════════════

@tool(
    name="tb_mark_mail",
    description=(
        "Marque un mail Thunderbird (lu, non-lu, important/étoilé, supprimé). "
        "⚠️ Thunderbird doit être fermé avant d'utiliser cet outil."
    ),
    parameters={
        "type": "object",
        "properties": {
            "mail_id": {
                "type": "integer",
                "description": "ID du mail (champ 'id' de tb_list_mails/tb_search_mails).",
            },
            "action": {
                "type": "string",
                "enum": ["lu", "non_lu", "important", "non_important", "supprime"],
                "description": (
                    "Action à effectuer : "
                    "'lu' = marquer comme lu, "
                    "'non_lu' = marquer comme non lu, "
                    "'important' = étoiler le message, "
                    "'non_important' = retirer l'étoile, "
                    "'supprime' = marquer pour suppression."
                ),
            },
        },
        "required": ["mail_id", "action"],
    },
)
def tb_mark_mail(mail_id: int, action: str) -> dict:
    closed, msg = _check_tb_closed()
    if not closed:
        return {"status": "error", "error": msg}

    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result

    # Les flags sont dans global-messages-db mais aussi dans les fichiers .msf
    # On met à jour Gloda (la prochaine ouverture TB synchronisera)
    db_path = profile / "global-messages-db.sqlite"
    try:
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT flags FROM messages WHERE id = ?", (mail_id,)).fetchone()
        if not row:
            conn.close()
            return {"status": "error", "error": f"Mail id={mail_id} introuvable."}

        flags = row[0] or 0
        FLAG_READ    = 1
        FLAG_FLAGGED = 4
        FLAG_DELETED = 8

        if action == "lu":
            flags |= FLAG_READ
        elif action == "non_lu":
            flags &= ~FLAG_READ
        elif action == "important":
            flags |= FLAG_FLAGGED
        elif action == "non_important":
            flags &= ~FLAG_FLAGGED
        elif action == "supprime":
            flags |= FLAG_DELETED
        else:
            conn.close()
            return {"status": "error", "error": f"Action inconnue : '{action}'"}

        conn.execute("UPDATE messages SET flags = ? WHERE id = ?", (flags, mail_id))
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "mail_id": mail_id,
            "action": action,
            "message": f"Mail {mail_id} marqué '{action}' avec succès.",
        }
    except Exception as e:
        return {"status": "error", "error": f"Erreur mise à jour flags : {e}"}


@tool(
    name="tb_move_mail",
    description=(
        "Déplace un mail d'un dossier vers un autre dans Thunderbird. "
        "⚠️ Thunderbird doit être fermé avant d'utiliser cet outil. "
        "Fonctionne sur les mails stockés localement (mbox)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "mail_id": {
                "type": "integer",
                "description": "ID du mail à déplacer.",
            },
            "dossier_destination": {
                "type": "string",
                "description": "Nom du dossier de destination (ex: 'Archives', 'Trash').",
            },
        },
        "required": ["mail_id", "dossier_destination"],
    },
)
def tb_move_mail(mail_id: int, dossier_destination: str) -> dict:
    closed, msg = _check_tb_closed()
    if not closed:
        return {"status": "error", "error": msg}

    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result

    try:
        conn = _open_gloda(profile)
        has_uri = "uri" in _folder_columns(conn)
        fl_uri_col = "fl.uri AS src_uri," if has_uri else ""

        # Récupérer le mail source
        row = conn.execute(
            f"""SELECT m.id, m.messageKey, m.subject, m.folderID,
                      {fl_uri_col} fl.name AS src_name
               FROM messages m
               JOIN folderLocations fl ON m.folderID = fl.id
               WHERE m.id = ?""",
            (mail_id,)
        ).fetchone()

        if not row:
            conn.close()
            return {"status": "error", "error": f"Mail id={mail_id} introuvable."}

        try:
            src_uri = row["src_uri"] or ""
        except IndexError:
            src_uri = ""

        # Résoudre le dossier destination
        sel = _select_folder_cols(conn)
        folders = conn.execute(f"SELECT {sel} FROM folderLocations").fetchall()
        dest_folder = None
        for f in folders:
            if (f["name"] or "").lower() == dossier_destination.lower():
                dest_folder = f
                break

        if not dest_folder:
            conn.close()
            return {
                "status": "error",
                "error": f"Dossier '{dossier_destination}' introuvable. "
                         "Utilisez tb_list_folders pour voir les dossiers disponibles.",
            }

        conn.close()

        # Localiser les fichiers mbox source et destination
        src_mbox_path  = _find_mbox(profile, src_uri)
        dest_mbox_path = _find_mbox(profile, _folder_uri(dest_folder, profile))

        if not src_mbox_path:
            return {"status": "error", "error": f"Fichier mbox source introuvable pour '{row['src_name']}'."}
        if not dest_mbox_path:
            return {"status": "error", "error": f"Fichier mbox destination introuvable pour '{dossier_destination}'."}

        # Lire le mail depuis la mbox source
        # Garde : éviter de déplacer vers le même dossier
        if (row["src_name"] or "").lower() == dossier_destination.lower():
            return {
                "status": "error",
                "error": f"Le mail est déjà dans le dossier '{dossier_destination}'.",
            }

        # Trouver le message dans la mbox source
        # Méthode 1 : lecture par byte offset (messageKey Thunderbird local)
        msg_to_move = _read_mbox_at_offset(src_mbox_path, row["messageKey"])
        msg_key_to_delete = None

        if msg_to_move is None:
            # Fallback : parcourir par sujet + expéditeur (cas IMAP)
            src_mbox_scan = mailbox.mbox(str(src_mbox_path), create=False)
            for key in src_mbox_scan.keys():
                candidate = src_mbox_scan.get(key)
                if candidate:
                    subj = _decode_header(candidate.get("Subject", ""))
                    frm  = _decode_header(candidate.get("From", ""))
                    if (subj == (row["subject"] or "")
                            and (not row["src_name"]
                                 or row["author"] in frm
                                 or frm in (row["author"] or ""))):
                        msg_to_move = candidate
                        msg_key_to_delete = key
                        break
            src_mbox_scan.close()
        else:
            # Pour la suppression, retrouver la clé ordinale correspondant à l'offset
            src_mbox_scan = mailbox.mbox(str(src_mbox_path), create=False)
            target_subj = _decode_header(msg_to_move.get("Subject", ""))
            for key in src_mbox_scan.keys():
                c = src_mbox_scan.get(key)
                if c and _decode_header(c.get("Subject", "")) == target_subj:
                    msg_key_to_delete = key
                    break
            src_mbox_scan.close()

        if not msg_to_move:
            return {"status": "error", "error": "Message introuvable dans le fichier mbox source."}

        # Écrire dans la mbox destination
        dest_mbox = mailbox.mbox(str(dest_mbox_path))
        dest_mbox.lock()
        try:
            dest_mbox.add(msg_to_move)
            dest_mbox.flush()
        finally:
            dest_mbox.unlock()
            dest_mbox.close()

        # Supprimer de la mbox source
        src_mbox.lock()
        try:
            src_mbox.remove(msg_key_to_delete)
            src_mbox.flush()
        finally:
            src_mbox.unlock()
            src_mbox.close()

        # Mettre à jour Gloda
        gloda = sqlite3.connect(str(profile / "global-messages-db.sqlite"))
        gloda.execute(
            "UPDATE messages SET folderID = ? WHERE id = ?",
            (dest_folder["id"], mail_id)
        )
        gloda.commit()
        gloda.close()

        return {
            "status": "success",
            "mail_id": mail_id,
            "sujet": row["subject"] or "(sans sujet)",
            "source": row["src_name"],
            "destination": dossier_destination,
            "message": f"Mail déplacé de '{row['src_name']}' vers '{dossier_destination}'.",
        }

    except Exception as e:
        return {"status": "error", "error": f"Erreur déplacement : {e}"}


@tool(
    name="tb_create_draft",
    description=(
        "Crée un brouillon ou prépare une réponse dans Thunderbird. "
        "Le message est enregistré dans le dossier Drafts (Brouillons) "
        "sous forme de fichier .eml prêt à être ouvert et envoyé. "
        "⚠️ Thunderbird doit être fermé avant d'utiliser cet outil."
    ),
    parameters={
        "type": "object",
        "properties": {
            "destinataire": {
                "type": "string",
                "description": "Adresse email du destinataire (ex: 'nom@domaine.fr').",
            },
            "sujet": {
                "type": "string",
                "description": "Sujet du message.",
            },
            "corps": {
                "type": "string",
                "description": "Corps du message en texte brut.",
            },
            "cc": {
                "type": "string",
                "description": "Adresses CC séparées par des virgules (optionnel).",
            },
            "en_reponse_a": {
                "type": "integer",
                "description": (
                    "ID du mail auquel répondre. Si fourni, le sujet sera préfixé "
                    "de 'Re:' et les en-têtes de réponse seront ajoutés."
                ),
            },
        },
        "required": ["destinataire", "sujet", "corps"],
    },
)
def tb_create_draft(
    destinataire: str,
    sujet: str,
    corps: str,
    cc: Optional[str] = None,
    en_reponse_a: Optional[int] = None,
) -> dict:
    closed, msg = _check_tb_closed()
    if not closed:
        return {"status": "error", "error": msg}

    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result

    try:
        # Construire le message MIME (MIMEText direct, pas MIMEMultipart avec 1 seule partie)
        message = MIMEText("", "plain", "utf-8")  # corps rempli plus bas
        message["To"]      = destinataire
        message["Subject"] = sujet
        message["Date"]    = email.utils.formatdate(localtime=True)
        message["X-Mozilla-Draft-Info"] = "internal/draft; vcard=0; receipt=0; DSN=0; uuencode=0"

        if cc:
            message["Cc"] = cc

        # Récupérer les infos du mail original si réponse
        if en_reponse_a:
            try:
                conn = _open_gloda(profile)
                orig = conn.execute(
                    "SELECT subject, author, messageKey FROM messages WHERE id = ?",
                    (en_reponse_a,)
                ).fetchone()
                conn.close()
                if orig:
                    orig_subj = orig["subject"] or ""
                    if not sujet.lower().startswith("re:"):
                        message.replace_header("Subject", f"Re: {orig_subj}")
                    message["In-Reply-To"] = f"<{orig['messageKey']}>"
                    # Ajouter le corps de la réponse avec citation
                    corps_complet = corps + f"\n\n--- Message original ---\nDe : {orig['author']}\nObjet : {orig_subj}\n"
                else:
                    corps_complet = corps
            except Exception:
                corps_complet = corps
        else:
            corps_complet = corps

        message.set_payload(corps_complet, charset="utf-8")

        # Trouver le dossier Drafts
        drafts_path = None
        for mail_root in (profile / "Mail", profile / "ImapMail"):
            if not mail_root.exists():
                continue
            for srv_dir in mail_root.iterdir():
                if not srv_dir.is_dir():
                    continue
                for name in ("Drafts", "Brouillons", "Draft"):
                    candidate = srv_dir / name
                    if candidate.exists():
                        drafts_path = candidate
                        break
                if drafts_path:
                    break
            if drafts_path:
                break

        if drafts_path is None:
            # Créer dans Mail/Local Folders/Drafts
            local_mail = profile / "Mail" / "Local Folders"
            local_mail.mkdir(parents=True, exist_ok=True)
            drafts_path = local_mail / "Drafts"
            drafts_path.touch(exist_ok=True)

        # Ajouter dans la mbox Drafts
        draft_mbox = mailbox.mbox(str(drafts_path))
        draft_mbox.lock()
        try:
            draft_mbox.add(mailbox.mboxMessage(message))
            draft_mbox.flush()
        finally:
            draft_mbox.unlock()
            draft_mbox.close()

        return {
            "status": "success",
            "message": "Brouillon créé avec succès.",
            "destinataire": destinataire,
            "sujet": message["Subject"],
            "dossier": str(drafts_path),
            "instruction": "Ouvrez Thunderbird et allez dans Brouillons pour finaliser et envoyer le message.",
        }

    except Exception as e:
        return {"status": "error", "error": f"Erreur création brouillon : {e}"}


# ══════════════════════════════════════════════════════════════════════════════
# OUTILS — Agenda / Lecture
# ══════════════════════════════════════════════════════════════════════════════

@tool(
    name="tb_agenda_upcoming",
    description=(
        "Retourne les événements de l'agenda Thunderbird (Lightning/Calendar) "
        "pour les N prochains jours. Inclut : titre, date/heure, lieu, description, "
        "participants, récurrence."
    ),
    parameters={
        "type": "object",
        "properties": {
            "jours": {
                "type": "integer",
                "description": "Nombre de jours à partir d'aujourd'hui (défaut: 7, max: 365).",
            },
            "inclure_passes": {
                "type": "boolean",
                "description": "Si true, inclut aussi les événements du jour passé (défaut: false).",
            },
        },
        "required": [],
    },
)
def tb_agenda_upcoming(jours: int = 7, inclure_passes: bool = False) -> dict:
    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result
    jours = min(max(1, jours), 365)

    try:
        conn = _open_calendar(profile, readonly=True)
    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}

    try:
        now = datetime.now(tz=timezone.utc)
        if inclure_passes:
            start_dt = now.replace(hour=0, minute=0, second=0)
        else:
            start_dt = now
        end_dt = now + timedelta(days=jours)

        start_ts = int(start_dt.timestamp() * 1_000_000)
        end_ts   = int(end_dt.timestamp()   * 1_000_000)

        rows = conn.execute(
            """SELECT id, cal_id, title, event_start, event_end,
                      event_start_tz, location, description, status
               FROM cal_events
               WHERE event_end >= ? AND event_start <= ?
               ORDER BY event_start ASC""",
            (start_ts, end_ts)
        ).fetchall()

        events = []
        for r in rows:
            # Récupérer les participants
            attendees = conn.execute(
                """SELECT common_name, attendee_id, role, status
                   FROM cal_attendees WHERE item_id = ?""",
                (r["id"],)
            ).fetchall()

            participants = [
                f"{a['common_name'] or a['attendee_id']} ({a['role'] or 'REQ'} / {a['status'] or '?'})"
                for a in attendees
            ]

            # Récupérer les catégories et alarmes depuis cal_properties
            props = conn.execute(
                "SELECT key, value FROM cal_properties WHERE item_id = ?",
                (r["id"],)
            ).fetchall()
            categories = [p["value"] for p in props if p["key"] == "CATEGORIES"]

            events.append({
                "id": r["id"],
                "titre": r["title"] or "(sans titre)",
                "debut": _ts_to_dt(r["event_start"]),
                "fin": _ts_to_dt(r["event_end"]),
                "lieu": r["location"] or "",
                "description": (r["description"] or "")[:300],
                "statut": r["status"] or "",
                "participants": participants,
                "categories": categories,
            })

    except Exception as e:
        conn.close()
        return {"status": "error", "error": f"Erreur lecture agenda : {e}"}
    finally:
        conn.close()

    return {
        "status": "success",
        "periode": f"Aujourd'hui + {jours} jours",
        "nombre": len(events),
        "evenements": events,
    }


@tool(
    name="tb_agenda_search",
    description=(
        "Recherche des événements dans l'agenda Thunderbird selon plusieurs critères. "
        "Cherche dans : titre, lieu, description, participants."
    ),
    parameters={
        "type": "object",
        "properties": {
            "texte": {
                "type": "string",
                "description": "Texte à rechercher dans le titre, lieu et description.",
            },
            "participant": {
                "type": "string",
                "description": "Nom ou email d'un participant.",
            },
            "depuis": {
                "type": "string",
                "description": "Date de début au format YYYY-MM-DD.",
            },
            "jusqu_a": {
                "type": "string",
                "description": "Date de fin au format YYYY-MM-DD.",
            },
            "inclure_todos": {
                "type": "boolean",
                "description": "Si true, inclut aussi les tâches (todos) dans les résultats.",
            },
            "limite": {
                "type": "integer",
                "description": "Nombre max de résultats (défaut: 50).",
            },
        },
        "required": [],
    },
)
def tb_agenda_search(
    texte: Optional[str] = None,
    participant: Optional[str] = None,
    depuis: Optional[str] = None,
    jusqu_a: Optional[str] = None,
    inclure_todos: bool = False,
    limite: int = 50,
) -> dict:
    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result
    limite = min(max(1, limite), 200)

    if not any([texte, participant, depuis, jusqu_a]):
        return {"status": "error", "error": "Au moins un critère de recherche est requis."}

    try:
        conn = _open_calendar(profile, readonly=True)
    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}

    try:
        conditions, params = [], []

        if texte:
            conditions.append("(title LIKE ? OR location LIKE ? OR description LIKE ?)")
            params.extend([f"%{texte}%", f"%{texte}%", f"%{texte}%"])

        if depuis:
            ts = _dt_to_ts(depuis + " 00:00")
            conditions.append("event_end >= ?")
            params.append(ts)

        if jusqu_a:
            ts = _dt_to_ts(jusqu_a + " 23:59")
            conditions.append("event_start <= ?")
            params.append(ts)

        where = " AND ".join(conditions) if conditions else "1=1"

        rows = conn.execute(
            f"""SELECT id, title, event_start, event_end, location, description, status
                FROM cal_events WHERE {where} ORDER BY event_start DESC LIMIT ?""",
            params + [limite]
        ).fetchall()

        results = []
        for r in rows:
            # Filtrer par participant si demandé
            if participant:
                att = conn.execute(
                    """SELECT attendee_id, common_name FROM cal_attendees
                       WHERE item_id = ? AND (attendee_id LIKE ? OR common_name LIKE ?)""",
                    (r["id"], f"%{participant}%", f"%{participant}%")
                ).fetchone()
                if not att:
                    continue

            results.append({
                "id": r["id"],
                "titre": r["title"] or "(sans titre)",
                "debut": _ts_to_dt(r["event_start"]),
                "fin": _ts_to_dt(r["event_end"]),
                "lieu": r["location"] or "",
                "description": (r["description"] or "")[:200],
                "statut": r["status"] or "",
                "type": "evenement",
            })

        # Todos si demandé
        if inclure_todos and not participant:
            todo_conditions, todo_params = [], []
            if texte:
                todo_conditions.append("(title LIKE ? OR description LIKE ?)")
                todo_params.extend([f"%{texte}%", f"%{texte}%"])
            todo_where = " AND ".join(todo_conditions) if todo_conditions else "1=1"
            todos = conn.execute(
                f"""SELECT id, title, todo_due, priority, status, description
                    FROM cal_todos WHERE {todo_where} ORDER BY todo_due DESC LIMIT 20""",
                todo_params
            ).fetchall()
            for t in todos:
                results.append({
                    "id": t["id"],
                    "titre": t["title"] or "(sans titre)",
                    "echeance": _ts_to_dt(t["todo_due"]),
                    "priorite": t["priority"],
                    "statut": t["status"] or "",
                    "description": (t["description"] or "")[:200],
                    "type": "todo",
                })

    except Exception as e:
        conn.close()
        return {"status": "error", "error": f"Erreur recherche agenda : {e}"}
    finally:
        conn.close()

    return {
        "status": "success",
        "nombre": len(results),
        "resultats": results,
    }


@tool(
    name="tb_todo_list",
    description=(
        "Liste les tâches (todos) de l'agenda Thunderbird avec leur statut, "
        "priorité et date d'échéance."
    ),
    parameters={
        "type": "object",
        "properties": {
            "statut": {
                "type": "string",
                "enum": ["tous", "en_cours", "termine", "en_attente"],
                "description": "Filtrer par statut (défaut: 'en_cours').",
            },
            "limite": {
                "type": "integer",
                "description": "Nombre max de tâches (défaut: 50).",
            },
        },
        "required": [],
    },
)
def tb_todo_list(statut: str = "en_cours", limite: int = 50) -> dict:
    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result
    limite = min(max(1, limite), 200)

    try:
        conn = _open_calendar(profile, readonly=True)
    except FileNotFoundError as e:
        return {"status": "error", "error": str(e)}

    try:
        # Statuts iCalendar : NEEDS-ACTION, IN-PROCESS, COMPLETED, CANCELLED
        status_map = {
            "en_cours":  ("NEEDS-ACTION", "IN-PROCESS"),
            "termine":   ("COMPLETED",),
            "en_attente": ("NEEDS-ACTION",),
            "tous":      None,
        }
        filter_statuts = status_map.get(statut, None)

        if filter_statuts:
            placeholders = ",".join("?" * len(filter_statuts))
            # Inclure explicitement les todos sans statut (NULL) si on filtre "en_cours"
            include_null = statut == "en_cours"
            null_clause = " OR status IS NULL" if include_null else ""
            rows = conn.execute(
                f"""SELECT id, title, todo_due, todo_completed, priority,
                           status, description
                    FROM cal_todos
                    WHERE (status IN ({placeholders}){null_clause})
                    ORDER BY todo_due ASC NULLS LAST, priority ASC
                    LIMIT ?""",
                list(filter_statuts) + [limite]
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT id, title, todo_due, todo_completed, priority,
                          status, description
                   FROM cal_todos
                   ORDER BY todo_due ASC NULLS LAST, priority ASC
                   LIMIT ?""",
                (limite,)
            ).fetchall()

        todos = []
        for r in rows:
            prio_label = {1: "🔴 Haute", 5: "🟡 Moyenne", 9: "🟢 Basse"}.get(
                r["priority"], f"P{r['priority']}" if r["priority"] else "—"
            )
            todos.append({
                "id": r["id"],
                "titre": r["title"] or "(sans titre)",
                "echeance": _ts_to_dt(r["todo_due"]),
                "terminee_le": _ts_to_dt(r["todo_completed"]),
                "priorite": prio_label,
                "statut": r["status"] or "NEEDS-ACTION",
                "description": (r["description"] or "")[:200],
            })

    except Exception as e:
        conn.close()
        return {"status": "error", "error": f"Erreur lecture todos : {e}"}
    finally:
        conn.close()

    return {
        "status": "success",
        "filtre_statut": statut,
        "nombre": len(todos),
        "taches": todos,
    }


# ══════════════════════════════════════════════════════════════════════════════
# OUTILS — Agenda / Écriture
# ══════════════════════════════════════════════════════════════════════════════

@tool(
    name="tb_agenda_create",
    description=(
        "Crée un nouvel événement dans l'agenda local Thunderbird. "
        "⚠️ Thunderbird doit être fermé avant d'utiliser cet outil."
    ),
    parameters={
        "type": "object",
        "properties": {
            "titre": {
                "type": "string",
                "description": "Titre de l'événement.",
            },
            "debut": {
                "type": "string",
                "description": "Date et heure de début au format YYYY-MM-DD HH:MM.",
            },
            "fin": {
                "type": "string",
                "description": "Date et heure de fin au format YYYY-MM-DD HH:MM.",
            },
            "lieu": {
                "type": "string",
                "description": "Lieu de l'événement (optionnel).",
            },
            "description": {
                "type": "string",
                "description": "Description ou notes de l'événement (optionnel).",
            },
            "participants": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Liste d'adresses email des participants (optionnel).",
            },
        },
        "required": ["titre", "debut", "fin"],
    },
)
def tb_agenda_create(
    titre: str,
    debut: str,
    fin: str,
    lieu: Optional[str] = None,
    description: Optional[str] = None,
    participants: Optional[list] = None,
) -> dict:
    closed, msg = _check_tb_closed()
    if not closed:
        return {"status": "error", "error": msg}

    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result

    try:
        ts_debut = _dt_to_ts(debut)
        ts_fin   = _dt_to_ts(fin)
    except ValueError as e:
        return {"status": "error", "error": str(e)}

    if ts_fin <= ts_debut:
        return {"status": "error", "error": "La date de fin doit être postérieure à la date de début."}

    try:
        conn = _open_calendar(profile, readonly=False)

        event_id  = str(uuid.uuid4())
        now_ts    = int(datetime.now().timestamp() * 1_000_000)

        # Résoudre le vrai cal_id depuis la table cal_calendars.
        # "local-calendar" est la valeur par défaut depuis TB 91, mais les versions
        # antérieures utilisent un UUID. On lit la table pour être robuste.
        try:
            cal_row = conn.execute(
                "SELECT id FROM cal_calendars WHERE type='storage' AND enabled=1 ORDER BY rowid LIMIT 1"
            ).fetchone()
            cal_id = cal_row["id"] if cal_row else "local-calendar"
        except sqlite3.OperationalError:
            # cal_calendars peut ne pas exister sur très anciennes versions
            cal_id = "local-calendar"

        conn.execute(
            """INSERT INTO cal_events
               (id, cal_id, title, event_start, event_end, event_start_tz, event_end_tz,
                location, description, status, flags, last_modified, created, stamp)
               VALUES (?, ?, ?, ?, ?, 'floating', 'floating', ?, ?, 'CONFIRMED', 0, ?, ?, ?)""",
            (event_id, cal_id, titre, ts_debut, ts_fin,
             lieu or "", description or "", now_ts, now_ts, now_ts)
        )

        # Ajouter les participants
        if participants:
            for addr in participants:
                att_id = f"mailto:{addr}"
                name   = addr.split("@")[0]
                conn.execute(
                    """INSERT INTO cal_attendees
                       (item_id, attendee_id, common_name, role, status, is_organizer, rsvp)
                       VALUES (?, ?, ?, 'REQ-PARTICIPANT', 'NEEDS-ACTION', 0, 1)""",
                    (event_id, att_id, name)
                )

        conn.commit()
        conn.close()

        return {
            "status": "success",
            "id": event_id,
            "titre": titre,
            "debut": debut,
            "fin": fin,
            "lieu": lieu or "",
            "participants": participants or [],
            "message": f"Événement '{titre}' créé avec succès dans l'agenda local.",
        }

    except Exception as e:
        return {"status": "error", "error": f"Erreur création événement : {e}"}


@tool(
    name="tb_agenda_update",
    description=(
        "Modifie un événement existant dans l'agenda Thunderbird. "
        "Seuls les champs fournis sont mis à jour. "
        "⚠️ Thunderbird doit être fermé avant d'utiliser cet outil. "
        "Utiliser tb_agenda_search pour obtenir l'ID de l'événement."
    ),
    parameters={
        "type": "object",
        "properties": {
            "event_id": {
                "type": "string",
                "description": "ID de l'événement (champ 'id' de tb_agenda_upcoming/tb_agenda_search).",
            },
            "titre": {
                "type": "string",
                "description": "Nouveau titre (optionnel).",
            },
            "debut": {
                "type": "string",
                "description": "Nouvelle date de début YYYY-MM-DD HH:MM (optionnel).",
            },
            "fin": {
                "type": "string",
                "description": "Nouvelle date de fin YYYY-MM-DD HH:MM (optionnel).",
            },
            "lieu": {
                "type": "string",
                "description": "Nouveau lieu (optionnel).",
            },
            "description": {
                "type": "string",
                "description": "Nouvelle description (optionnel).",
            },
            "statut": {
                "type": "string",
                "enum": ["CONFIRMED", "TENTATIVE", "CANCELLED"],
                "description": "Nouveau statut (optionnel).",
            },
        },
        "required": ["event_id"],
    },
)
def tb_agenda_update(
    event_id: str,
    titre: Optional[str] = None,
    debut: Optional[str] = None,
    fin: Optional[str] = None,
    lieu: Optional[str] = None,
    description: Optional[str] = None,
    statut: Optional[str] = None,
) -> dict:
    closed, msg = _check_tb_closed()
    if not closed:
        return {"status": "error", "error": msg}

    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result

    if not any([titre, debut, fin, lieu, description, statut]):
        return {"status": "error", "error": "Au moins un champ à modifier est requis."}

    try:
        conn = _open_calendar(profile, readonly=False)

        # Vérifier que l'événement existe
        existing = conn.execute(
            "SELECT id, title FROM cal_events WHERE id = ?", (event_id,)
        ).fetchone()
        if not existing:
            conn.close()
            return {"status": "error", "error": f"Événement '{event_id}' introuvable."}

        # Construire la requête UPDATE dynamiquement
        updates, params = [], []
        if titre:
            updates.append("title = ?"); params.append(titre)
        if debut:
            try:
                updates.append("event_start = ?"); params.append(_dt_to_ts(debut))
            except ValueError as e:
                conn.close(); return {"status": "error", "error": str(e)}
        if fin:
            try:
                updates.append("event_end = ?"); params.append(_dt_to_ts(fin))
            except ValueError as e:
                conn.close(); return {"status": "error", "error": str(e)}
        if lieu is not None:
            updates.append("location = ?"); params.append(lieu)
        if description is not None:
            updates.append("description = ?"); params.append(description)
        if statut:
            updates.append("status = ?"); params.append(statut)

        now_ts = int(datetime.now().timestamp() * 1_000_000)
        updates.append("last_modified = ?"); params.append(now_ts)

        conn.execute(
            f"UPDATE cal_events SET {', '.join(updates)} WHERE id = ?",
            params + [event_id]
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "event_id": event_id,
            "titre_original": existing["title"],
            "champs_modifies": [k for k, v in {
                "titre": titre, "debut": debut, "fin": fin,
                "lieu": lieu, "description": description, "statut": statut,
            }.items() if v is not None and v != ""],
        }

    except Exception as e:
        return {"status": "error", "error": f"Erreur modification événement : {e}"}


@tool(
    name="tb_agenda_delete",
    description=(
        "Supprime un événement ou une tâche de l'agenda Thunderbird. "
        "⚠️ Cette opération est irréversible. "
        "⚠️ Thunderbird doit être fermé avant d'utiliser cet outil."
    ),
    parameters={
        "type": "object",
        "properties": {
            "item_id": {
                "type": "string",
                "description": "ID de l'événement ou de la tâche à supprimer.",
            },
            "type": {
                "type": "string",
                "enum": ["evenement", "todo"],
                "description": "Type d'élément à supprimer (défaut: 'evenement').",
            },
            "confirmer": {
                "type": "boolean",
                "description": "Doit être true pour confirmer la suppression.",
            },
        },
        "required": ["item_id", "confirmer"],
    },
)
def tb_agenda_delete(item_id: str, confirmer: bool, type: str = "evenement") -> dict:
    if not confirmer:
        return {
            "status": "cancelled",
            "message": "Suppression annulée. Passez confirmer=true pour confirmer.",
        }

    closed, msg = _check_tb_closed()
    if not closed:
        return {"status": "error", "error": msg}

    ok, result = _find_tb_profile()
    if not ok:
        return {"status": "error", "error": result}
    profile = result

    try:
        conn = _open_calendar(profile, readonly=False)

        if type == "todo":
            table = "cal_todos"
        else:
            table = "cal_events"

        # Récupérer le titre avant suppression
        existing = conn.execute(
            f"SELECT id, title FROM {table} WHERE id = ?", (item_id,)
        ).fetchone()
        if not existing:
            conn.close()
            return {"status": "error", "error": f"Élément '{item_id}' introuvable dans {table}."}

        titre = existing["title"] or "(sans titre)"

        # Supprimer l'élément et ses données associées
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        conn.execute("DELETE FROM cal_attendees WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM cal_recurrence WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM cal_properties WHERE item_id = ?", (item_id,))
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "item_id": item_id,
            "titre": titre,
            "type": type,
            "message": f"'{titre}' supprimé de l'agenda.",
        }

    except Exception as e:
        return {"status": "error", "error": f"Erreur suppression : {e}"}
