---
description: Bulk-create Epics stories from a JSON file, a spec or meeting notes, after your approval
argument-hint: <.json file, or the text / file to turn into stories>
---

Import stories into Mendix Epics from: $ARGUMENTS

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" import <file.json> [--level Backlog] --dry-run
```

The file is a JSON array; `title` is the only required key:

```json
[{"title": "…", "description": "…", "storyType": "Feature", "storyPoints": 3, "storyLevel": "Backlog"}]
```

`storyType` is `Bug` or `Feature`; `storyLevel` is `Active`, `NextSprint`,
`InRefinement` or `Backlog`; `--level` fills it in for items without one.
Status cannot be set on import.

**The API has no story delete** - a wrong import has to be archived story by
story in the Epics UI. So:

1. If the input is not already such a JSON file (a specification, meeting notes,
   a list), draft the stories: one per deliverable outcome, acceptance criteria
   in the description, `Backlog` unless the user says otherwise, following the
   naming of the existing stories (check with `stories --all`). Save the JSON as
   UTF-8 to a temporary file outside the project.
2. Run with `--dry-run`. The tool checks every item and lists all problems at
   once; fix them and run again. Show the user the stories as a plain table
   (title, type, points, level), and point out every warning about a title that
   already exists or repeats in the file.
3. Send it with `--yes` instead of `--dry-run`, only after an explicit go-ahead.
   More than 50 stories go in several requests automatically.
4. Report the created story IDs. If some failed, import only the failed ones
   again - re-running the whole file would duplicate the rest.
