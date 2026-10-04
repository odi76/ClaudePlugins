---
description: Add one or more tasks to an Epics story, after your approval
argument-hint: <STORY-ID> <task title(s), or what the tasks should cover>
---

Add tasks to Mendix Epics story $1 for: $ARGUMENTS

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" create-task <STORY-ID> --title "…" [--title "…"] [--done] --dry-run
```

Repeat `--title` to create several tasks in one request; `--done` marks all of
them as done.

**Tasks cannot be edited or deleted through the API** - a wrong or duplicate
task has to be removed by hand in the Epics UI. So:

1. If the user gave a goal rather than exact titles, read the story first with
   `story <STORY-ID> --with-tasks` and draft short, concrete task titles that
   fit its description and do not repeat its existing tasks.
2. Run with `--dry-run` and show the titles to the user as a list. If the tool
   warns that a task with the same title already exists, point that out.
3. Send it without `--dry-run` only after an explicit go-ahead, then confirm
   with `tasks <STORY-ID>`.

If no story ID was given, ask for one. A 404 means the story ID is wrong or
belongs to another app - suggest `/mendix-epics:list-stories`.
