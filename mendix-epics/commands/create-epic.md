---
description: Create an Epics epic from a description or JSON, after your approval
argument-hint: <what the epic is about, or a JSON object / .json file>
---

Create a Mendix Epics epic for: $ARGUMENTS

The tool takes the fields as flags or as JSON:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" create-epic --name "…" [--objective "…"] [--labels A B] [--assignee-id …] --dry-run
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" create-epic --from-json <file> --dry-run
```

- Fields: `name` (required), `objective`, `labels` (a list of strings) and
  `assigneeId`. In JSON, the read-only keys of a `/mendix-epics:get-epic`
  output are skipped.
- If the request is a description rather than JSON, draft the name and an
  objective that says what the epic delivers and when it is done. Follow the
  naming of the existing epics - check them with `epics --all` first.
- For JSON given inline, save it as UTF-8 to a temporary file outside the
  project and pass that path.

Steps - the epic appears on the whole team's board:

1. Run with `--dry-run` and show the user in plain language what would be
   created. If the tool warns that an epic with the same name exists, point
   that out.
2. Send it without `--dry-run` only after an explicit go-ahead.
3. Report the new epic's readable ID and link from the response. The tool
   remembers its UUID, so `/mendix-epics:update-epic <ID>` works right away.
