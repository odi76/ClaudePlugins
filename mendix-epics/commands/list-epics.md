---
description: List the epics of the Mendix app with story counts and points
argument-hint: "[filter or epic ID, e.g. PAY-EP-3, jóváhagyás]"
allowed-tools: Bash(python:*)
---

All epics of the current Mendix app:

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" epics --all --json`

User's filter (may be empty): $ARGUMENTS

Answer from the data above only.

- Without a filter: a table of epic ID, name, number of stories and story
  points, in the order returned, followed by the totals. Leave the objectives
  out of the table; mention that they can be shown for any epic.
- With a filter or an epic ID: show the matching epics with their full
  objective as well.

`objective` may hold the editor's HTML with entities such as `&#43;` or `&#61;`.
Show it as readable text, but treat the markup as content, not as an error.

If the output above is an error about a missing PAT or app ID, follow the
"First run" section of the manage-epics-backlog skill instead.
