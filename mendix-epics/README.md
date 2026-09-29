# Mendix Epics

Read and write a Mendix Epics backlog from Claude: list and search stories, export
the backlog, create and update stories, tasks and epics — through the official
[Mendix Epics API](https://docs.mendix.com/apidocs-mxsdk/apidocs/epics-api/).

Works with any Mendix app that uses Epics, and with several apps side by side.

## Requirements

- **Python 3.9 or newer** on the machine. Nothing to install beyond that — the
  bundled tool uses only the standard library.
- **A Mendix Personal Access Token** with the scopes `mx:epics:read` and
  `mx:epics:write`, created at <https://user-settings.mendix.com/>. Every person
  uses their own; nothing is shared.

## Setup, once per person

### Through the plugin settings (recommended)

When the plugin is enabled, Claude asks for three optional settings (they can be
changed later in `/config`):

| Setting | What it is |
|---|---|
| Mendix App ID | The app's UUID. Saved as the default app. |
| App short name | The name it is saved under (default: `default`), for `--app`. |
| Mendix Personal Access Token | Masked, kept in the platform's secure credential store. |

At the start of every session a small hook copies them to where the tool looks —
the token to the same encrypted (Windows) or owner-only (macOS/Linux) file that
`set-pat` writes, the app into `~/.mendix/epics.json`. Nothing is written when
nothing changed, and the token is never printed.

### Manually

Ask Claude to set up the Epics backlog connection, or run it directly:

```bash
python <plugin>/scripts/epics.py set-pat
```

Paste the token at the prompt — it is not echoed and does not end up in shell
history. On Windows it is stored DPAPI-encrypted (only your Windows user on that
machine can read it back); on macOS and Linux in a file only your user can read.
Either way it lands in your home directory, outside any repository.

Then name the app you work with:

```bash
python <plugin>/scripts/epics.py set-app myapp 28f5337b-5959-4bdc-8158-95b2df72ba91
python <plugin>/scripts/epics.py check
```

The app ID is the UUID in the app's Team Server repository URL, also shown in the
Mendix Developer Portal under the app's general settings. Inside a cloned Mendix
repository the tool finds it on its own. Add more apps with further `set-app`
calls and pick one per command with `--app <name>`.

`check` should print the app, the account status and the app's story statuses.

## What you can ask Claude

- "What is in the backlog?" / "Which stories are still open?"
- "Show me story ABC-77."
- "Export the backlog to a Markdown file."
- "Create a story for the approval flow, 5 points, in the backlog."
- "Turn these meeting notes into backlog items."
- "Why does the Epics API say 401?"

## Safety

The Epics API cannot delete a story, so mistakes have to be cleaned up by hand in
the Epics UI. The plugin is built accordingly:

- Every write can be previewed with `--dry-run`, and Claude is instructed to show
  you what it would send before sending it.
- A bulk import refuses to run without an explicit `--yes`.
- Deleting an epic refuses to run without `--force`.
- The token is never printed, never passed on a command line, and never asked for
  in chat.

## What the API does not offer

No story deletion, no assignee or sprint on a story, no writing labels, no
comments or attachments. Those stay in the Epics UI. Epics themselves do support
an assignee and labels.

## Contents

- A skill that teaches Claude the whole workflow, with reference material on the
  API and on troubleshooting.
- `scripts/epics.py` — the command-line tool the skill drives. Run it with
  `--help` to use it directly.
- `scripts/apply_plugin_config.py` and `hooks/hooks.json` — the SessionStart hook
  that applies the plugin settings.
