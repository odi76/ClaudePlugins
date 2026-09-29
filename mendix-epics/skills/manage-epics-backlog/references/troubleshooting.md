# Troubleshooting

## Reading `diagnose`

`diagnose` prints the token's length, whether it contains whitespace or non-ASCII
characters, and whether it looks truncated — never the token itself. Then it calls
the same endpoint four ways:

| Result pattern | Diagnosis |
|---|---|
| this app 401, random app id 401, deliberately bogus token 401 | The gateway rejects the token before it ever reaches the app. The token is wrong, expired, or was created without the `mx:epics:*` scopes. Storing the same token again will not help — a new PAT is needed. |
| this app 401, random app id 404 | The token works; the app ID is wrong. |
| 404 everywhere with a token that works elsewhere | Wrong app ID, the app does not use Epics, or this account has no access to it. |
| this app 200 | Nothing wrong with auth; the failure is in the specific request. |

A PAT that authenticates against other Mendix APIs but 401s here is a scope
problem, not a bad token. Scopes cannot be added to an existing PAT — create a new
one with `mx:epics:read` and `mx:epics:write` ticked.

## "Could not determine which Mendix app to use"

Nothing is configured and the current directory is not a cloned Mendix repository.
Run `set-app <name> <app-id>`, or pass `--app-id` for a one-off. The app ID is the
UUID in the app's Team Server repository URL and is shown in the Developer Portal
under the app's general settings.

Saved apps live in `~/.mendix/epics.json` (on Windows `%USERPROFILE%\.mendix\epics.json`).
It holds app IDs only — never a token.

## Plugin settings did not take effect

The plugin's settings (app ID, app name, PAT) are applied by a SessionStart hook,
`scripts/apply_plugin_config.py`, at the start of each session. It writes only
when a value changed and never deletes anything, so clearing a setting leaves the
last stored value in place — use `set-pat` / `set-app` to replace it.

- `pat-status` shows the PAT file as the source once the hook has run.
- `apps` shows the configured app as the default.
- If neither changed, the hook did not run in this environment (hooks from a
  plugin may not run on every surface), Python is not on the hook's `PATH`, or
  the setting is empty. Start a new session after changing a setting; fall back
  to `set-pat` / `set-app` if it still has no effect.
- An `app_id` that is not a UUID is ignored with a message on stderr.
- `MENDIX_EPICS_PAT` / `MENDIX_PAT` and `MENDIX_APP_ID` in the environment still
  take precedence over anything the hook stored.

## Credential storage per platform

| Platform | `set-pat` writes | Protection |
|---|---|---|
| Windows | `~/.mendix/epics-pat.xml` | DPAPI-encrypted: only this Windows user, on this machine, can decrypt it. Copying the file elsewhere makes it useless. |
| macOS / Linux | `~/.mendix/epics-pat.txt` | Plain text with permissions 600 — readable by this user only, but **not** encrypted. |

Both live in the home directory, outside any repository, so git cannot commit
them. A PAT file placed inside a git repository triggers a warning unless git
ignores it.

The Windows file is interchangeable with PowerShell's `Export-Clixml` /
`Import-Clixml` SecureString format, so a token stored by one tool is readable by
the other.

`pat-status` shows which source is being used, with only the token's length and
last four characters.

## Output and encoding

- Progress lines go to stderr, so `stories --all --json > file.json` produces
  valid JSON.
- On Windows a redirected stdout would fall back to the locale code page and
  mangle non-ASCII text; the tool switches redirected streams to UTF-8.
- `story` prints a readable view by default and the raw response with `--json`.
  HTML entities in `descriptionHTML` are content, not a defect — see the skill.

## Traps to preserve when editing the tool

- The shared options (`--dry-run`, `--json`, `--app`, `--app-id`, `--pat-file`)
  use `default=argparse.SUPPRESS`, with the defaults applied afterwards in
  `normalize_globals()`. Putting `set_defaults()` back on the parent parser makes
  a subcommand overwrite a value parsed before it — which once turned a
  `--dry-run` into a real write. The argv sweep that forces `dry_run` on whenever
  `--dry-run` appears anywhere is the safety net for exactly that.
- The DPAPI helpers use no extra entropy and UTF-16LE plaintext; changing either
  breaks interoperability with PowerShell's SecureString files.
- Request bodies are sent as UTF-8 bytes and responses decoded as UTF-8 by hand,
  because the API does not always declare a charset.
