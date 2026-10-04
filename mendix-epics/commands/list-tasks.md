---
description: List the tasks of one Epics story, or of every story in the app
argument-hint: "[STORY-ID] [open]"
allowed-tools: Bash(python:*)
---

Request (may be empty): $ARGUMENTS

Run one of these with the tool:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" tasks <STORY-ID>
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" tasks [--open]
```

- With a story ID: that story's tasks in board order.
- Without one: every task of the app, grouped by story. The API has no
  app-wide task list, so the tool asks each story that has tasks - fine for a
  normal backlog, but say so if it is slow.
- `--open` (only without a story ID) leaves out the tasks already done. Use it
  when the user asks for open, pending or unfinished tasks.

Show the result as a list per story with a done / open mark per task, and a
count of open and done tasks at the end. If there are no tasks, say so plainly.
A 404 for a story ID means the ID is wrong or belongs to another app - suggest
`/mendix-epics:list-stories`.
