---
description: Update an Epics epic from a JSON object, after previewing the changes
argument-hint: <EPIC-ID or epic link> <JSON object or path to a .json file>
---

Update Mendix Epics epic $1 from this JSON (inline, or a path to a file):

$ARGUMENTS

The tool takes the JSON with `--from-json`:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" update-epic "<epic>" --from-json <file> --dry-run
```

- Writable keys: `name`, `objective`, `labels` (a list of strings) and
  `assigneeId`.
- The output of `/mendix-epics:get-epic` can be edited and fed back as it is:
  its read-only keys are skipped, an `epicId` that does not match the epic is
  refused, and `name` / `objective` are only sent when they differ from the
  live epic.
- `labels` and `assigneeId` are not returned by the API, so they cannot be
  compared and are sent as given. Tell the user that the labels sent will
  likely replace the epic's current labels, which cannot be read here.
- `<epic>` is the epic's readable ID (`PAY-EP-3`) when its UUID is already
  known, otherwise the epic's link from the Epics UI. If the tool reports that
  the UUID is not known, ask the user for that link.

Steps - the API keeps no history, so a wrong write cannot be undone
automatically:

1. If the JSON was given inline, save it as UTF-8 to a temporary file outside the
   project and pass that path. If no epic or no JSON was given, ask for it.
2. Run with `--dry-run`. The tool lists every change as `field: old -> new` and
   prints the request. Show the user the changes in plain language.
3. Send it without `--dry-run` only after an explicit go-ahead, then show the
   result with `/mendix-epics:get-epic <epic>`.

If the tool reports that the epic already matches the JSON, say so and stop.
