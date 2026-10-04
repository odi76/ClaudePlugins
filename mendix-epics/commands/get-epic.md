---
description: Return every field of one Epics epic as raw JSON, with its UUID when known
argument-hint: <EPIC-ID or epic link>
allowed-tools: Bash(python:*)
---

!`python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" epic "$1" --json`

Return the JSON above to the user exactly as it is, in one ```json code block:
no summary, no reformatting, no fields added, dropped or renamed. Keep
`objective` as it is - HTML and entities in it are content, not errors.

Then add one short line about `uuid`, which the tool adds because the API never
lists it:
- when it has a value: the epic can be changed with `/mendix-epics:update-epic`;
- when it is `null`: changing the epic needs its UUID once - ask the user to copy
  the epic's link from the Epics UI (it ends in `<EPIC-ID>--<uuid>`) and run
  this command again with the link; the UUID is remembered from then on.

If no epic was given, ask for one. If the output is an error instead of JSON,
show it and suggest `/mendix-epics:list-epics`.
