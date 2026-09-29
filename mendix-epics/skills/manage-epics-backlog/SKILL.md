---
name: manage-epics-backlog
description: "Reads and writes a Mendix Epics backlog - stories, epics and tasks - through the Mendix Epics API. Use when the user asks what is in the backlog, which stories are open or done, to look up or export stories, to create or update stories, tasks or epics, to turn a specification or meeting notes into backlog items, or when an Epics API call returns 401 or 404."
---

# Manage a Mendix Epics Backlog

A Mendix app's backlog lives in Mendix Epics, not in the app model, so no Mendix
modelling tool reaches it. Use the bundled command-line tool for every read and
write:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" <command> [options]
```

It needs Python 3.9+ and nothing else — no packages to install. Run
`python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" --help` for the full command
list, or `<command> --help` for one command.

## First run

Two things must be set up once per person. Check with `check`; it prints the app
and the available statuses when both are in place.

1. **A Personal Access Token.** Direct the user to <https://user-settings.mendix.com/>
   to create one with **both** `mx:epics:read` and `mx:epics:write` scopes, then
   have them run `set-pat` themselves and paste it at the prompt. Scopes cannot be
   added to an existing token — one created without them has to be replaced.
   Never ask for the token in chat, never put it in a command line, and never
   print it. `pat-status` shows where it comes from without revealing it.
2. **Which app.** Run `set-app <name> <app-id>` once. The app ID is the UUID in the
   app's Team Server repository URL, also shown in the Developer Portal under the
   app's general settings. Inside a cloned Mendix repository the tool finds it in
   the git remote by itself. `apps` lists what is saved; `--app <name>` picks one
   for a single call.

## Reading

| Goal | Command |
|---|---|
| Whole backlog | `stories --all` |
| One story with its description | `story <STORY-ID>` |
| Raw fields for processing | `stories --all --json` or `story <ID> --json` |
| Epics with story counts | `epics --all` |
| Tasks under a story | `tasks <STORY-ID>` |
| Statuses / labels this app uses | `statuses`, `labels` |
| Markdown snapshot into the project | `export --path <file.md>` |

Answer questions from this data rather than guessing. Statuses are per-app free
text and are often not in English, so read them with `check` or `statuses` before
filtering or setting one.

A story carries its description twice: `descriptionPlain` is ready to read, while
`descriptionHTML` is the editor's raw markup and legitimately contains HTML
entities such as `&#39;`. Read from the plain field; never present the entities as
an error or "fix" them in the HTML field — they are content. `story` already
prints a readable view.

## Writing

Writes go to a live planning board the whole team sees, and **the API has no story
delete** — a wrong story can only be archived by hand in the Epics UI. So:

1. Build the request and run the command with `--dry-run`.
2. Describe in plain language what would be created or changed — not raw JSON
   unless the user asks — and get an explicit go-ahead.
3. Run it for real, then confirm with `stories` or `story`.

Never add `--yes` or `--force` to a command being tested; test flag handling on a
read-only command instead.

| Goal | Command |
|---|---|
| One story | `create-story --title "…" [--description "…"] [--type Bug\|Feature] [--points N] [--level Backlog]` |
| Change a story | `update-story <ID> [--title …] [--description …] [--points N] [--status "…"]` |
| Several stories | write a JSON file, then `import <file>` (needs `--yes` to actually send) |
| Task under a story | `create-task <STORY-ID> --title "…"` |
| Epic | `create-epic --name "…" [--objective "…"] [--labels a b] [--assignee-id …]` |

Prefer `import` over repeated `create-story` for more than two or three items: one
request, and per-item failures are reported instead of leaving a half-finished
batch. The file format is in `references/api-reference.md`.

Turning a specification or meeting notes into stories: draft the list, show it as
a plain table for approval, then import it. Keep one story per deliverable outcome,
put acceptance criteria in the description, and set `--level Backlog` unless the
user says otherwise.

## Limits worth knowing before promising anything

- `storyType` is only `Bug` or `Feature`; `storyLevel` is only `Active`,
  `NextSprint`, `InRefinement` or `Backlog`.
- Status can only be set when updating, never at creation.
- There is no API for assigning a story to a person, putting it in a sprint,
  writing labels, adding comments, or deleting a story. Epics do support an
  assignee and labels.

If the user asks for one of these, say plainly that the API does not offer it and
point them at the Epics UI.

## When something fails

Run `diagnose`. It reports the token's shape without revealing it and probes the
API four ways, which separates a rejected token from a wrong app ID. The reading
of its output, plus the other common failures, is in
`references/troubleshooting.md`.

## Reference material

- `references/api-reference.md` — endpoints, every field and its allowed values,
  the import file format, paging, and what the API does not support.
- `references/troubleshooting.md` — 401/404 diagnosis, credential storage per
  platform, encoding, and the traps hidden in the tool.
