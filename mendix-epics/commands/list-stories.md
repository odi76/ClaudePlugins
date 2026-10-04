---
description: Show the Mendix Epics backlog, optionally filtered
argument-hint: "[filter, e.g. open bugs, NextSprint, approval]"
allowed-tools: Bash(python:*)
---

The whole backlog of the current Mendix app:

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" stories --all --json`

User's filter (may be empty): $ARGUMENTS

Answer from the data above only. Without a filter, give a short overview per
story level (Active, NextSprint, InRefinement, Backlog): how many stories, how
many points, and the notable ones. With a filter, list the matching stories as a
table of ID, title, level, status and points. Status names are per-app free text
and may not be in English - match them as they appear.

If the output above is an error about a missing PAT or app ID, follow the
"First run" section of the manage-epics-backlog skill instead.
