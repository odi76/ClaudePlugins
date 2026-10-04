---
description: Show one Epics story with its description and tasks
argument-hint: <STORY-ID>
allowed-tools: Bash(python:*)
---

Story $1:

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" story $1`

Its tasks:

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" tasks $1`

Summarize the story for the user: what it is for, its level, status, type and
points, then the tasks with which are done and which are open. If the
description contains acceptance criteria, list them.

If no story ID was given, ask for one. If the API answered 404, the ID is wrong
or belongs to another app - say so and suggest `/mendix-epics:list-stories`.
