#!/usr/bin/env python3
"""Read and write a Mendix Epics backlog - stories, epics and tasks.

Talks to the Mendix Epics API (https://epics-api.mendix.com/v1). Standard
library only: no pip install, no virtualenv.

Which app
---------
Resolved in this order (first hit wins; `check` prints which one was used):

  1. --app-id <uuid>
  2. env MENDIX_APP_ID
  3. --app <name>, looked up in ~/.mendix/epics.json
  4. the default app saved in ~/.mendix/epics.json
  5. the Mendix Team Server git remote of the current directory

Save an app once with `set-app <name> <app-id>`; list them with `apps`.
The app ID is the UUID in the app's Team Server repository URL.

Authentication
--------------
A Personal Access Token with the scopes mx:epics:read and mx:epics:write,
created at https://user-settings.mendix.com/. Store it with `set-pat`:
encrypted with Windows DPAPI on Windows, otherwise a 0600 file in the home
directory. Either way it lands outside any repository, so git cannot commit
it. Lookup order (first hit wins; `pat-status` shows which, without printing
the token):

  1. env MENDIX_EPICS_PAT / MENDIX_PAT
  2. --pat-file <path>
  3. env MENDIX_EPICS_PAT_FILE
  4. ~/.mendix/epics-pat.xml    (Windows, DPAPI-encrypted)
  5. ~/.mendix/epics-pat.txt    (plain text, permissions 600)
  6. ./.secrets/epics.pat       (in-repo fallback; keep it gitignored)

Writing
-------
Every write command takes --dry-run, which prints the request instead of
sending it. A bulk `import` additionally needs --yes, and `delete-epic`
needs --force, because the Epics API has no story delete: a wrong write has
to be cleaned up by hand in the Epics UI.

Examples
--------
  epics.py set-pat
  epics.py set-app myapp 28f5337b-5959-4bdc-8158-95b2df72ba91
  epics.py check
  epics.py stories --all
  epics.py story ABC-77
  epics.py create-story --title "New story" --level Backlog --dry-run
  epics.py import backlog.json --dry-run
  epics.py export --path Epics_Backlog.md
"""

from __future__ import annotations

import argparse
import binascii
import getpass
import html as html_module
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

BASE_URL = "https://epics-api.mendix.com/v1"
WORK_DIR = Path.cwd()          # the project the user is working in, if any
HOME_DIR = Path(os.environ.get("USERPROFILE") or Path.home())
CONFIG_PATH = HOME_DIR / ".mendix" / "epics.json"
STORY_TYPES = ("Bug", "Feature")
STORY_LEVELS = ("Active", "NextSprint", "InRefinement", "Backlog")
IS_WINDOWS = os.name == "nt"


class EpicsError(Exception):
    """Anything the user should see as a plain error message, not a traceback."""


# --------------------------------------------------------------------- DPAPI

def _dpapi_available() -> bool:
    return IS_WINDOWS


def _dpapi(func_name: str, data: bytes) -> bytes:
    """Call CryptProtectData / CryptUnprotectData with no extra entropy.

    That is exactly what PowerShell's ConvertFrom-SecureString does, which is
    why the two scripts can read each other's files.
    """
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    func = getattr(crypt32, func_name)
    func.restype = wintypes.BOOL
    ok = func(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise EpicsError(
            f"{func_name} failed (Windows error {ctypes.get_last_error()}). "
            "A DPAPI-encrypted file can only be decrypted by the Windows user "
            "and machine that wrote it."
        )
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)


def read_securestring_clixml(path: Path) -> str:
    """Decrypt a SecureString written by Export-Clixml."""
    if not _dpapi_available():
        raise EpicsError(
            f"{path} is a Windows DPAPI file and can only be read on Windows. "
            "Use a plain text PAT file or the MENDIX_EPICS_PAT environment variable."
        )
    root = ET.parse(path).getroot()
    node = next((e for e in root.iter() if e.tag.rsplit("}", 1)[-1] == "SS"), None)
    if node is None or not (node.text or "").strip():
        raise EpicsError(
            f"{path} does not contain an encrypted PAT. Re-create it with: "
            "epics.py set-pat"
        )
    blob = binascii.unhexlify(node.text.strip())
    return _dpapi("CryptUnprotectData", blob).decode("utf-16-le")


def write_securestring_clixml(path: Path, secret: str) -> None:
    """Write a SecureString file PowerShell's Import-Clixml can read back."""
    if not _dpapi_available():
        raise EpicsError("Encrypted PAT storage needs Windows (DPAPI).")
    blob = _dpapi("CryptProtectData", secret.encode("utf-16-le"))
    xml = (
        '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04">\n'
        f"  <SS>{binascii.hexlify(blob).decode('ascii')}</SS>\n"
        "</Objs>\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8", newline="\r\n")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


# -------------------------------------------------------------------- config

def load_config() -> dict:
    """App IDs the user has saved. Not secret - no token ever goes in here."""
    if not CONFIG_PATH.is_file():
        return {}
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EpicsError(f"Could not read {CONFIG_PATH}: {exc}") from None
    return data if isinstance(data, dict) else {}


def save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")


# ---------------------------------------------------------------- credentials

def default_pat_file() -> Path:
    """Where set-pat stores the token on this platform."""
    return HOME_DIR / ".mendix" / ("epics-pat.xml" if IS_WINDOWS else "epics-pat.txt")


def pat_file_candidates(pat_file: str | None) -> list[Path]:
    out: list[Path] = []
    if pat_file:
        out.append(Path(pat_file))
    if os.environ.get("MENDIX_EPICS_PAT_FILE"):
        out.append(Path(os.environ["MENDIX_EPICS_PAT_FILE"]))
    out.append(HOME_DIR / ".mendix" / "epics-pat.xml")
    out.append(HOME_DIR / ".mendix" / "epics-pat.txt")
    out.append(WORK_DIR / ".secrets" / "epics.pat")
    return out


def warn_if_not_gitignored(path: Path) -> None:
    """A PAT file inside a repo must be ignored by git, or it can be committed."""
    try:
        resolved = path.resolve()
        resolved.relative_to(WORK_DIR)
    except (ValueError, OSError):
        return
    try:
        rc = subprocess.run(
            ["git", "-C", str(WORK_DIR), "check-ignore", "-q", "--", str(resolved)],
            capture_output=True,
        ).returncode
    except OSError:
        return
    if rc != 0:
        print(
            f"WARNING: {path} is inside a git repository and is NOT ignored. "
            f"Add it to .gitignore or move it to {default_pat_file()}",
            file=sys.stderr,
        )


def read_pat_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    warn_if_not_gitignored(path)
    if path.suffix.lower() == ".xml":
        return read_securestring_clixml(path)
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if "=" in text:
            key, _, value = text.partition("=")
            if key.strip().replace("_", "").isalnum():
                text = value.strip()
        return text.strip("\"'")
    return None


def get_token_source(pat_file: str | None) -> tuple[str, str] | None:
    """Return (token, where-it-came-from) or None."""
    for name in ("MENDIX_EPICS_PAT", "MENDIX_PAT"):
        value = os.environ.get(name)
        if value:
            return value, f"env:{name}"
    for candidate in pat_file_candidates(pat_file):
        value = read_pat_file(candidate)
        if value:
            return value, str(candidate)
    return None


def get_token(args) -> str:
    found = get_token_source(args.pat_file)
    if found:
        return found[0]
    raise EpicsError(
        "No PAT found. Create one at https://user-settings.mendix.com/ with the "
        "scopes mx:epics:read and mx:epics:write, then either:\n"
        "  epics.py set-pat      (stores it encrypted, outside the repo)\n"
        "  set MENDIX_EPICS_PAT=<token>         (current session only)"
    )


UUID_RE = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


def app_id_from_git() -> str | None:
    """A Mendix Team Server remote carries the app ID in its URL."""
    try:
        remote = subprocess.run(
            ["git", "-C", str(WORK_DIR), "remote", "get-url", "origin"],
            capture_output=True, text=True,
        ).stdout.strip()
    except OSError:
        return None
    if "mendix.com" not in remote:
        return None
    match = re.search(UUID_RE, remote)
    return match.group(0) if match else None


def resolve_app_id_source(args) -> tuple[str, str]:
    """Return (app id, where it came from). Order: flag, env, named app, default, git."""
    if getattr(args, "app_id", None):
        return args.app_id, "--app-id"
    if os.environ.get("MENDIX_APP_ID"):
        return os.environ["MENDIX_APP_ID"], "env:MENDIX_APP_ID"

    config = load_config()
    apps = config.get("apps") or {}
    name = getattr(args, "app", None)
    if name:
        if name not in apps:
            known = ", ".join(sorted(apps)) or "(none saved yet)"
            raise EpicsError(f"No app named '{name}' is saved. Known: {known}. "
                             f"Save one with: epics.py set-app {name} <app-id>")
        return apps[name], f"{CONFIG_PATH} ({name})"
    default_name = config.get("defaultApp")
    if default_name and default_name in apps:
        return apps[default_name], f"{CONFIG_PATH} ({default_name}, default)"

    from_git = app_id_from_git()
    if from_git:
        return from_git, "git remote of the current directory"

    raise EpicsError(
        "Could not determine which Mendix app to use. Either:\n"
        "  epics.py set-app <name> <app-id>   (saves it for next time)\n"
        "  epics.py <command> --app-id <app-id>\n"
        "  set MENDIX_APP_ID=<app-id>\n"
        "The app ID is the UUID in the app's Team Server repository URL, and is "
        "shown in the Mendix Developer Portal under the app's General settings."
    )


def resolve_app_id(args) -> str:
    return resolve_app_id_source(args)[0]


# ------------------------------------------------------------------- transport

def call(args, method: str, route: str, body=None, token: str | None = None):
    url = BASE_URL + route
    data = None
    headers = {
        "Authorization": "MxToken " + (token if token is not None else get_token(args)),
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace").strip()
        message = f"Epics API {method} {route} failed (HTTP {exc.code})"
        if detail:
            message += f": {detail}"
        if exc.code == 401:
            message += "\n  -> the PAT is missing, expired, or lacks the mx:epics:* scopes."
        if exc.code == 404:
            message += "\n  -> wrong app ID, or the app does not use Epics / you have no access."
        raise EpicsError(message) from None
    except urllib.error.URLError as exc:
        raise EpicsError(f"Could not reach {url}: {exc.reason}") from None
    if not raw.strip():
        return None
    return json.loads(raw.decode("utf-8"))


def get_paged(args, route: str, collection: str, total_field: str) -> list[dict]:
    app = resolve_app_id(args)
    limit = getattr(args, "limit", 100)
    offset = getattr(args, "offset", 0)
    out: list[dict] = []
    while True:
        page = call(args, "GET", f"/projects/{app}/{route}?limit={limit}&offset={offset}")
        if not page:
            break
        items = page.get(collection) or []
        out.extend(items)
        total = int(page.get(total_field) or 0)
        offset += limit
        if not getattr(args, "all", False) or not items or len(out) >= total:
            break
    return out


def write_call(args, method: str, route: str, body=None):
    """Single funnel for every mutating call, so --dry-run always works."""
    if args.dry_run:
        print("DRY RUN - nothing was sent.")
        print(f"{method} {BASE_URL}{route}")
        if body is not None:
            print(json.dumps(body, ensure_ascii=False, indent=2))
        return None
    return call(args, method, route, body)


# ---------------------------------------------------------------- presentation

def show(args, rows, columns: list[str]) -> None:
    rows = list(rows or [])
    if args.json or not columns:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("(none)")
        return
    def cell(row, key):
        value = row.get(key)
        return "" if value is None else str(value).replace("\n", " ")
    widths = {c: max(len(c), max(len(cell(r, c)) for r in rows)) for c in columns}
    print("  ".join(c.ljust(widths[c]) for c in columns))
    print("  ".join("-" * widths[c] for c in columns))
    for row in rows:
        print("  ".join(cell(row, c).ljust(widths[c]) for c in columns))


def story_body(args, for_patch: bool) -> dict:
    body: dict = {}
    if args.title:
        body["title"] = args.title
    if args.description:
        body["description"] = args.description
    if args.type:
        body["storyType"] = args.type
    if args.points is not None:
        body["storyPoints"] = args.points
    if args.level:
        body["storyLevel"] = args.level
    status = getattr(args, "status", None)
    if status:
        if for_patch:
            body["storyStatus"] = status
        else:
            print("WARNING: the Epics API cannot set a status on create; "
                  "use update-story afterwards.", file=sys.stderr)
    return body


# -------------------------------------------------------------------- commands

def cmd_set_pat(args) -> None:
    target = Path(args.pat_file) if args.pat_file else default_pat_file()
    encrypted = target.suffix.lower() == ".xml"
    if encrypted and not IS_WINDOWS:
        raise EpicsError("Encrypted (.xml) storage needs Windows. Use a .txt path instead.")

    if sys.stdin.isatty():
        secret = getpass.getpass("Paste the Mendix PAT (input hidden): ").strip()
    else:
        secret = sys.stdin.readline().strip()
    if not secret:
        raise EpicsError("No token was entered.")

    if encrypted:
        write_securestring_clixml(target, secret)
        print(f"Stored encrypted PAT in {target}")
        print("Only your Windows user on this machine can decrypt it.")
    else:
        # No DPAPI outside Windows: fall back to a file only the user can read.
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(mode=0o600, exist_ok=True)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        target.write_text(secret + "\n", encoding="utf-8")
        print(f"Stored PAT in {target} (readable by your user only, permissions 600)")
        print("It is NOT encrypted - this platform has no DPAPI equivalent.")
    print("The file lives in your home directory, outside any repository, so git "
          "cannot commit it.")
    print("Verify with: epics.py check")


def cmd_pat_status(args) -> None:
    found = get_token_source(args.pat_file)
    if not found:
        print("No PAT found.")
        print("Looked at: env:MENDIX_EPICS_PAT, env:MENDIX_PAT, then these files:")
        for candidate in pat_file_candidates(args.pat_file):
            print("  " + str(candidate))
        return
    token, source = found
    print(f"Source : {source}")
    print(f"Token  : {len(token)} chars, ends with ...{token[-4:] if len(token) >= 4 else ''}")


def cmd_apps(args) -> None:
    config = load_config()
    apps = config.get("apps") or {}
    if not apps:
        print(f"No apps saved yet in {CONFIG_PATH}.")
        print("Save one with: epics.py set-app <name> <app-id>")
        return
    default_name = config.get("defaultApp")
    rows = [{"name": n + (" (default)" if n == default_name else ""), "appId": a}
            for n, a in sorted(apps.items())]
    show(args, rows, ["name", "appId"])


def cmd_set_app(args) -> None:
    if not re.fullmatch(UUID_RE, args.app_id_value):
        raise EpicsError(f"'{args.app_id_value}' is not a UUID. The app ID looks like "
                         "28f5337b-5959-4bdc-8158-95b2df72ba91.")
    config = load_config()
    apps = config.setdefault("apps", {})
    apps[args.name] = args.app_id_value
    if args.default or not config.get("defaultApp"):
        config["defaultApp"] = args.name
    save_config(config)
    print(f"Saved app '{args.name}' in {CONFIG_PATH}"
          + (" (now the default)" if config["defaultApp"] == args.name else ""))
    print("Check it with: epics.py check")


def cmd_check(args) -> None:
    app, source = resolve_app_id_source(args)
    print(f"App ID : {app}")
    print(f"         from {source}")
    result = call(args, "GET", f"/projects/{app}/statuses")
    statuses = sorted(result.get("statuses") or [], key=lambda s: s.get("sortId", 0))
    print("Auth   : OK")
    print("Statuses: " + ", ".join(s["name"] for s in statuses))


def cmd_diagnose(args) -> None:
    """Narrow down a 401/404 without ever revealing the token."""
    found = get_token_source(args.pat_file)
    if not found:
        raise EpicsError("No PAT found - run: epics.py set-pat")
    token, source = found
    has_whitespace = bool(re.search(r"\s", token))
    has_non_ascii = bool(re.search(r"[^\x21-\x7E]", token))
    print(f"Source           : {source}")
    print(f"Length           : {len(token)}")
    print(f"Whitespace in it : {has_whitespace}")
    print(f"Non-ASCII in it  : {has_non_ascii}")
    print(f"Looks truncated  : {len(token) < 40}")
    print()

    app = resolve_app_id(args)
    print(f"App ID from git remote: {app}")
    probes = [
        ("epics / this app", f"/projects/{app}/statuses", token, "MxToken"),
        ("epics / random app id", "/projects/00000000-0000-4000-8000-000000000000/statuses", token, "MxToken"),
        ("epics / no token", f"/projects/{app}/statuses", "not-a-token", "MxToken"),
        ("epics / Bearer instead", f"/projects/{app}/statuses", token, "Bearer"),
    ]
    for label, route, value, scheme in probes:
        request = urllib.request.Request(
            BASE_URL + route,
            headers={"Authorization": f"{scheme} {value}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request) as response:
                print(f"{label:<24} HTTP {response.status}")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace").strip()
            print(f"{label:<24} HTTP {exc.code} {body}")
        except urllib.error.URLError as exc:
            print(f"{label:<24} unreachable: {exc.reason}")
    print()
    print("Reading: same 401 for this app AND a random app id means the token itself is")
    print("rejected (wrong/expired token, or created without the mx:epics:* scopes).")
    print("A 404 on the random app id but 401 here would point at the app ID instead.")


def cmd_statuses(args) -> None:
    app = resolve_app_id(args)
    result = call(args, "GET", f"/projects/{app}/statuses")
    show(args, sorted(result.get("statuses") or [], key=lambda s: s.get("sortId", 0)),
         ["sortId", "name"])


def cmd_labels(args) -> None:
    show(args, get_paged(args, "labels", "labels", "totalLabels"), ["name", "uuid"])


def cmd_stories(args) -> None:
    stories = get_paged(args, "stories", "stories", "totalStories")
    # stderr, so `stories --json > file` stays valid JSON
    print(f"{len(stories)} stories", file=sys.stderr)
    show(args, stories, ["storyId", "storyLevel", "status", "storyType", "storyPoints", "title"])


def html_to_text(markup: str) -> str:
    """Rough plain-text rendering of the editor's HTML, for reading only.

    descriptionHTML is the raw field the Epics editor stores, so it carries
    entities like &#39; and &#34;. It is never rewritten in place - that would
    corrupt the markup - only rendered for display when descriptionPlain is
    missing.
    """
    text = re.sub(r"(?i)<br\s*/?>", "\n", markup)
    text = re.sub(r"(?i)</(p|div|h[1-6]|ul|ol|tr)>", "\n\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "- ", text)
    text = re.sub(r"(?i)</li>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_module.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def cmd_story(args) -> None:
    app = resolve_app_id(args)
    story = call(args, "GET", f"/projects/{app}/stories/{args.id}")
    if args.json:
        print(json.dumps(story, ensure_ascii=False, indent=2))
        return
    def field(key):
        value = story.get(key)
        return "" if value is None else value

    print(f"{field('storyId')}  {field('title')}")
    print(f"{field('storyLevel')} / {field('status')} / {field('storyType')}"
          f" / {field('storyPoints')} pt / tasks: {field('numberOfTasks')}")
    print(f"uuid: {field('uuid')}")
    body = story.get("descriptionPlain") or html_to_text(story.get("descriptionHTML") or "")
    if body.strip():
        print()
        print(body.strip())


def cmd_create_story(args) -> None:
    app = resolve_app_id(args)
    result = write_call(args, "POST", f"/projects/{app}/stories", [story_body(args, False)])
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_update_story(args) -> None:
    app = resolve_app_id(args)
    body = story_body(args, True)
    if not body:
        raise EpicsError("Nothing to update. Pass at least one of --title --description "
                         "--type --points --level --status")
    write_call(args, "PATCH", f"/projects/{app}/stories/{args.id}", body)
    if not args.dry_run:
        print(f"Updated {args.id}")


def cmd_tasks(args) -> None:
    app = resolve_app_id(args)
    result = call(args, "GET", f"/projects/{app}/stories/{args.id}/tasks")
    show(args, sorted(result.get("tasks") or [], key=lambda t: t.get("sortId", 0)),
         ["sortId", "isDone", "title"])


def cmd_create_task(args) -> None:
    app = resolve_app_id(args)
    body = [{"title": args.title, "isDone": bool(args.done)}]
    result = write_call(args, "POST", f"/projects/{app}/stories/{args.id}/tasks", body)
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_epics(args) -> None:
    show(args, get_paged(args, "epics", "epics", "totalEpics"),
         ["epicId", "name", "numberOfStories", "numberOfStoryPoints", "objective"])


def _epic_body(args) -> dict:
    body: dict = {}
    if getattr(args, "name", None):
        body["name"] = args.name
    if args.objective:
        body["objective"] = args.objective
    if args.labels:
        body["labels"] = args.labels
    if args.assignee_id:
        body["assigneeId"] = args.assignee_id
    return body


def cmd_create_epic(args) -> None:
    app = resolve_app_id(args)
    result = write_call(args, "POST", f"/projects/{app}/epics", _epic_body(args))
    if result:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_update_epic(args) -> None:
    app = resolve_app_id(args)
    body = _epic_body(args)
    if not body:
        raise EpicsError("Nothing to update. Pass at least one of --name --objective "
                         "--labels --assignee-id")
    write_call(args, "PATCH", f"/projects/{app}/epics/{args.uuid}", body)
    if not args.dry_run:
        print(f"Updated epic {args.uuid}")


def cmd_delete_epic(args) -> None:
    if not args.force and not args.dry_run:
        raise EpicsError(f"Refusing to delete epic {args.uuid} without --force "
                         "(deleting an epic cannot be undone).")
    app = resolve_app_id(args)
    write_call(args, "DELETE", f"/projects/{app}/epics/{args.uuid}")
    if not args.dry_run:
        print(f"Deleted epic {args.uuid}")


def cmd_import(args) -> None:
    """Bulk create from a JSON file: an array of
    {title, description, storyType, storyPoints, storyLevel}.
    """
    source = Path(args.file)
    if not source.is_file():
        raise EpicsError(f"File not found: {source}")
    items = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = [items]

    payload = []
    for item in items:
        if not item.get("title"):
            raise EpicsError("Every item needs a title.")
        entry = {"title": item["title"]}
        for key in ("description", "storyType", "storyLevel"):
            if item.get(key):
                entry[key] = item[key]
        if item.get("storyPoints") is not None:
            entry["storyPoints"] = int(item["storyPoints"])
        if "storyLevel" not in entry and args.level:
            entry["storyLevel"] = args.level
        payload.append(entry)

    print(f"{len(payload)} stories to create", file=sys.stderr)
    if not args.dry_run and not args.yes:
        raise EpicsError(
            "Refusing to send a bulk import without --yes. Review it first with "
            "--dry-run, then re-run with --yes. (The Epics API has no story "
            "delete, so a wrong import has to be cleaned up by hand.)"
        )
    app = resolve_app_id(args)
    result = write_call(args, "POST", f"/projects/{app}/stories", payload)
    if result:
        # 200 = all created, 207 = partial; both return an items[] array
        for item in result.get("items") or []:
            if item.get("story"):
                print("created " + item["story"].get("storyId", "?"))
            elif item.get("code"):
                print(f"WARNING: {item['code']}: {item.get('detail')}", file=sys.stderr)


def cmd_export(args) -> None:
    """Snapshot the whole backlog into a Markdown file, grouped by story level."""
    args.all = True
    stories = get_paged(args, "stories", "stories", "totalStories")
    target = Path(args.path) if args.path else WORK_DIR / "Epics_Backlog.md"
    target.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Epics backlog",
        "",
        "Generated by the mendix-epics plugin on "
        + datetime.now().strftime("%Y-%m-%d %H:%M")
        + " - do not edit by hand.",
        "",
        f"App ID: {resolve_app_id(args)} | Stories: {len(stories)}",
        "",
    ]
    for level in STORY_LEVELS:
        group = sorted([s for s in stories if s.get("storyLevel") == level],
                       key=lambda s: s.get("sortId", 0))
        if not group:
            continue
        lines += [f"## {level} ({len(group)})", "",
                  "| ID | Title | Type | Points | Status | Tasks |",
                  "|----|-------|------|--------|--------|-------|"]
        for story in group:
            title = str(story.get("title", "")).replace("|", "\\|").replace("\n", " ")
            lines.append(
                f"| {story.get('storyId', '')} | {title} | {story.get('storyType', '')} "
                f"| {story.get('storyPoints', '')} | {story.get('status', '')} "
                f"| {story.get('numberOfTasks', '')} |"
            )
        lines.append("")

    lines += ["## Descriptions", ""]
    for story in sorted(stories, key=lambda s: (str(s.get("storyLevel")), s.get("sortId", 0))):
        lines += [f"### {story.get('storyId')} - {story.get('title')}", "",
                  f"*{story.get('storyLevel')} / {story.get('status')} / "
                  f"{story.get('storyType')} / {story.get('storyPoints')} pt*", ""]
        if story.get("descriptionPlain"):
            lines += [story["descriptionPlain"], ""]

    target.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"Wrote {target} ({len(stories)} stories)")


# ------------------------------------------------------------------------ cli

def build_parser() -> argparse.ArgumentParser:
    # The global options are attached to every subcommand as well, so both
    # `epics.py --dry-run create-story …` and `epics.py create-story … --dry-run`
    # work. SUPPRESS keeps a subparser from overwriting a value given earlier.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--app-id", default=argparse.SUPPRESS,
                        help="app UUID, overriding every other source")
    common.add_argument("--app", default=argparse.SUPPRESS,
                        help="name of a saved app (see `apps` / `set-app`)")
    common.add_argument("--pat-file", default=argparse.SUPPRESS,
                        help="path to a PAT file (default: see module docstring)")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="raw JSON output")
    common.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS,
                        help="print writes instead of sending")

    parser = argparse.ArgumentParser(
        prog="epics.py",
        description="Read and write a Mendix Epics backlog.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Every write command accepts --dry-run: it prints the request "
               "instead of sending it. Start with: set-pat, then set-app, then check.",
        parents=[common],
    )
    # No set_defaults() for the shared options: `parents` copies a parser's
    # defaults into every subparser, and the subparser then overwrites a value
    # given before the subcommand - which silently turned a --dry-run into a
    # real write. The defaults are applied in normalize_globals() instead.
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, func, help_text):
        p = sub.add_parser(name, help=help_text, parents=[common])
        p.set_defaults(func=func)
        return p

    def add_paging(p):
        p.add_argument("--all", action="store_true", help="walk every page")
        p.add_argument("--limit", type=int, default=100, choices=range(1, 101), metavar="1-100")
        p.add_argument("--offset", type=int, default=0)
        return p

    def add_story_fields(p, with_status: bool):
        p.add_argument("--title")
        p.add_argument("--description")
        p.add_argument("--type", choices=STORY_TYPES)
        p.add_argument("--points", type=int)
        p.add_argument("--level", choices=STORY_LEVELS)
        if with_status:
            p.add_argument("--status", help="exact status name; see `check`")
        return p

    add("set-pat", cmd_set_pat, "store a PAT safely, outside any repository")
    add("apps", cmd_apps, "list the saved apps")
    p = add("set-app", cmd_set_app, "save an app ID under a name")
    p.add_argument("name", help="short name you will use with --app")
    p.add_argument("app_id_value", metavar="app-id", help="the app's UUID")
    p.add_argument("--default", action="store_true", help="make this the default app")
    add("pat-status", cmd_pat_status, "show where the token comes from (never prints it)")
    add("check", cmd_check, "auth + app ID smoke test")
    add("diagnose", cmd_diagnose, "narrow down a 401/404")
    add("statuses", cmd_statuses, "list the app's story statuses")
    add_paging(add("labels", cmd_labels, "list labels"))
    add_paging(add("stories", cmd_stories, "list stories"))

    p = add("story", cmd_story, "show one story")
    p.add_argument("id", help="readable story ID, e.g. BSZ-77")

    add_story_fields(add("create-story", cmd_create_story, "create a story"), True)
    p = add_story_fields(add("update-story", cmd_update_story, "patch a story"), True)
    p.add_argument("id", help="readable story ID, e.g. BSZ-77")

    p = add("tasks", cmd_tasks, "list the tasks of a story")
    p.add_argument("id")
    p = add("create-task", cmd_create_task, "add a task to a story")
    p.add_argument("id")
    p.add_argument("--title", required=True)
    p.add_argument("--done", action="store_true")

    add_paging(add("epics", cmd_epics, "list epics"))
    p = add("create-epic", cmd_create_epic, "create an epic")
    p.add_argument("--name", required=True)
    p.add_argument("--objective")
    p.add_argument("--labels", nargs="*")
    p.add_argument("--assignee-id")
    p = add("update-epic", cmd_update_epic, "patch an epic")
    p.add_argument("uuid")
    p.add_argument("--name")
    p.add_argument("--objective")
    p.add_argument("--labels", nargs="*")
    p.add_argument("--assignee-id")
    p = add("delete-epic", cmd_delete_epic, "delete an epic (needs --force)")
    p.add_argument("uuid")
    p.add_argument("--force", action="store_true")

    p = add("import", cmd_import, "bulk-create stories from a JSON file")
    p.add_argument("file")
    p.add_argument("--level", choices=STORY_LEVELS, help="fallback level for items without one")
    p.add_argument("--yes", action="store_true",
                   help="required to actually send the import (review with --dry-run first)")

    p = add("export", cmd_export, "write the whole backlog to Markdown")
    p.add_argument("--path", help="default: doc/02_Backlog/Epics_Backlog.md")

    return parser


def configure_stdio() -> None:
    """Print UTF-8 when stdout is redirected.

    On Windows a piped stdout defaults to the locale code page, which mangles
    the Hungarian status names and story titles coming back from the API. A
    real console handles Unicode itself, so it is left alone.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            if not stream.isatty():
                stream.reconfigure(encoding="utf-8")
        except (AttributeError, OSError, ValueError):
            pass


def normalize_globals(args, argv: list[str]) -> None:
    """Apply the shared options' defaults and make --dry-run impossible to lose.

    The argv sweep is deliberate belt-and-braces: whatever argparse does with
    option ordering, a --dry-run anywhere on the command line must never turn
    into a real write.
    """
    for dest, default in (("app_id", None), ("app", None), ("pat_file", None),
                          ("json", False), ("dry_run", False)):
        if not hasattr(args, dest):
            setattr(args, dest, default)
    if "--dry-run" in argv:
        args.dry_run = True


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    normalize_globals(args, argv)
    try:
        args.func(args)
    except EpicsError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
