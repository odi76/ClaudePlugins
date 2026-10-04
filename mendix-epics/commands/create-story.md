---
description: Draft a new Epics story and create it after your approval
argument-hint: <what the story is about>
---

Create a Mendix Epics story for: $ARGUMENTS

Follow the manage-epics-backlog skill's writing rules - the API has no story
delete, so a wrong story has to be archived by hand:

1. Draft the title, a description with acceptance criteria, the type (Bug or
   Feature), the points if the user gave or implied them, and the level
   (Backlog unless the user said otherwise).
2. Run `create-story` with `--dry-run` and show the user in plain language what
   would be created.
3. Send it only after an explicit go-ahead, then confirm with `story <ID>`.

If the request describes several deliverables, propose one story each and use
`import` instead, as the skill describes.
