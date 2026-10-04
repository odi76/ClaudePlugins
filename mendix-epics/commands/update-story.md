---
description: Update an Epics story from a JSON object, after previewing the changes
argument-hint: <STORY-ID> <JSON object or path to a .json file>
---

Update Mendix Epics story $1 from this JSON (inline, or a path to a file):

$ARGUMENTS

The tool takes the JSON with `--from-json`:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" update-story <ID> --from-json <file> --dry-run
```

- Writable keys: `title`, `description`, `storyType` (Bug, Feature), `storyPoints`,
  `storyLevel` (Active, NextSprint, InRefinement, Backlog) and `status` (an
  exact status name of this app). `storyStatus` is accepted as well.
- The output of `/mendix-epics:get-story` can be edited and fed back as it is:
  its read-only keys are skipped, a `storyId` that does not match `<ID>` is
  refused, and only the fields that really differ from the live story are sent.
- `descriptionPlain` and `descriptionHTML` are read-only; a new description goes
  in a `description` key.

Steps - the API has no story delete or history, so a wrong write cannot be
undone automatically:

1. If the JSON was given inline, save it as UTF-8 to a temporary file outside the
   project and pass that path. If no story ID or no JSON was given, ask for it.
2. Run with `--dry-run`. The tool lists every change as `field: old -> new` and
   prints the request. Show the user the changes in plain language.
3. Send it without `--dry-run` only after an explicit go-ahead, then show the
   result with `/mendix-epics:get-story <ID>`.

If the tool reports that the story already matches the JSON, say so and stop.
