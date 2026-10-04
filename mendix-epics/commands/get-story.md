---
description: Return every field of one Epics story, with its tasks, as raw JSON
argument-hint: <STORY-ID>
allowed-tools: Bash(python:*)
---

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" story $1 --json --with-tasks`

Return the JSON above to the user exactly as it is, in one ```json code block:
no summary, no reformatting, no fields added, dropped or renamed. Keep
`descriptionHTML` as it is - its HTML entities are content, not errors.

If no story ID was given, ask for one. If the output is an error instead of
JSON, show the error and, for a 404, suggest `/mendix-epics:list-stories`.
