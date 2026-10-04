---
description: Export the whole Epics backlog to a Markdown file
argument-hint: "[target file, default: Epics_Backlog.md]"
allowed-tools: Bash(python:*)
---

Export the Mendix Epics backlog to Markdown with the manage-epics-backlog tool:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/epics.py" export --path "<target>"
```

Target file requested by the user (may be empty): $ARGUMENTS

If no target was given, leave out `--path`; the tool then writes
`Epics_Backlog.md` in the current directory. Report the path written and the
number of stories. The file is a generated snapshot - do not edit it by hand
afterwards.
