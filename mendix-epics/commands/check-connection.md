---
description: Check the Epics connection - token, app ID and statuses
allowed-tools: Bash(python:*)
---

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" check`

Report whether the connection works, which app is used and where that app ID
came from, and the app's statuses.

If it failed, run `diagnose` and explain the result using
`references/troubleshooting.md` of the manage-epics-backlog skill. Never ask
for the token in chat and never print it.
