#!/usr/bin/env python3
"""SessionStart hook: apply the plugin's userConfig values to epics.py's stores.

Claude Code exports every userConfig option to hook processes as
CLAUDE_PLUGIN_OPTION_<KEY>. This hook copies them to where epics.py already
looks, so the skill works without a manual `set-pat` / `set-app`:

  epics_pat -> the platform's default PAT file (DPAPI-encrypted on Windows,
               a 0600 file elsewhere) - the same place `set-pat` writes
  app_id    -> ~/.mendix/epics.json under app_name, made the default app

Rules:
  * Never print, log or pass the token on a command line.
  * Write only when a value changed, so an unchanged session costs nothing.
  * An empty option leaves the existing store untouched (never deletes).
  * Never fail the session: every error goes to stderr and the exit code is 0.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import epics  # noqa: E402  (same directory, stdlib only)


def opt(key: str) -> str:
    return (os.environ.get(f"CLAUDE_PLUGIN_OPTION_{key}") or "").strip()


def apply_pat(messages: list[str]) -> None:
    secret = opt("EPICS_PAT")
    if not secret:
        return
    target = epics.default_pat_file()
    try:
        current = epics.read_pat_file(target)
    except epics.EpicsError:
        current = None          # unreadable (e.g. other Windows user): overwrite
    if current == secret:
        return
    if target.suffix.lower() == ".xml":
        epics.write_securestring_clixml(target, secret)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch(mode=0o600, exist_ok=True)
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        target.write_text(secret + "\n", encoding="utf-8")
    messages.append(f"PAT from the plugin settings stored in {target}")


def apply_app(messages: list[str]) -> None:
    app_id = opt("APP_ID")
    if not app_id:
        return
    if not re.fullmatch(epics.UUID_RE, app_id):
        print(f"mendix-epics: plugin setting app_id '{app_id}' is not a UUID; ignored.",
              file=sys.stderr)
        return
    name = opt("APP_NAME") or "default"
    config = epics.load_config()
    apps = config.setdefault("apps", {})
    if apps.get(name) == app_id and config.get("defaultApp") == name:
        return
    apps[name] = app_id
    config["defaultApp"] = name
    epics.save_config(config)
    messages.append(f"default app '{name}' ({app_id}) set from the plugin settings")


def main() -> int:
    messages: list[str] = []
    for step in (apply_pat, apply_app):
        try:
            step(messages)
        except Exception as exc:  # the hook must never break a session
            print(f"mendix-epics: {step.__name__} failed: {exc}", file=sys.stderr)
    if messages:
        # SessionStart stdout is added to Claude's context - no secrets here.
        print("mendix-epics: " + "; ".join(messages) + ".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
