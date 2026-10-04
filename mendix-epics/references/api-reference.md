# Mendix Epics API reference

Official docs: <https://docs.mendix.com/apidocs-mxsdk/apidocs/epics-api/>
Base URL: `https://epics-api.mendix.com/v1`
Auth header: `Authorization: MxToken <PAT>` (scopes `mx:epics:read`, `mx:epics:write`)

The bundled tool wraps all of this; the endpoints are listed so a response can be
interpreted and so it is clear what simply does not exist.

## Endpoints

| Method | Path | Tool command |
|---|---|---|
| GET | `/projects/{appId}/statuses` | `statuses`, `check` |
| GET | `/projects/{appId}/labels` | `labels` |
| GET | `/projects/{appId}/stories` | `stories` |
| POST | `/projects/{appId}/stories` | `create-story`, `import` |
| GET | `/projects/{appId}/stories/{storyId}` | `story` |
| PATCH | `/projects/{appId}/stories/{storyId}` | `update-story` |
| GET | `/projects/{appId}/stories/{storyId}/tasks` | `tasks` |
| POST | `/projects/{appId}/stories/{storyId}/tasks` | `create-task` |
| GET | `/projects/{appId}/epics` | `epics` |
| POST | `/projects/{appId}/epics` | `create-epic` |
| PATCH | `/projects/{appId}/epics/{epicUUID}` | `update-epic` |
| DELETE | `/projects/{appId}/epics/{epicUUID}` | `delete-epic` |

`{storyId}` is the readable ID (`ABC-77`), `{epicUUID}` is a UUID — which the
epic list does not return; see "Epic fields".

## Story fields

Returned by `stories` and `story`:

| Field | Notes |
|---|---|
| `uuid` | internal ID |
| `storyId` | readable ID, e.g. `ABC-77` — use this in commands |
| `sortId` | board order |
| `title` | |
| `descriptionHTML` | the editor's raw HTML, with entities like `&#39;` and `&#34;` |
| `descriptionPlain` | same text, already decoded — read this one |
| `storyPoints` | integer, 0 or more |
| `storyType` | `Bug` or `Feature` only |
| `storyLevel` | `Active`, `NextSprint`, `InRefinement` or `Backlog` |
| `status` | free text, defined per app; read it with `statuses` |
| `numberOfTasks` | |

Writable on create: `title` (required), `description`, `storyType`, `storyPoints`,
`storyLevel`. Writable on update: the same plus `storyStatus`. **Status cannot be
set at creation** — create first, then update.

`description` is sent as one string; the API stores it and returns both the HTML
and the plain form.

## Epic fields

`epicId`, `name`, `objective`, `numberOfStories`, `numberOfStoryPoints`. Create
takes `name` (required), `objective`, `labels` (array of strings) and `assigneeId`.
A created epic comes back with `epicId`, `readableEpicId` and `epicUrl`.

**`epicId` means two different things** (per the official OpenAPI spec,
<https://docs.mendix.com/openapi-spec/epics.yaml>):

| Response | `epicId` holds |
|---|---|
| `GET …/epics` (the list) | the readable ID, e.g. `PAY-EP-3` — there is no UUID field |
| `POST …/epics` (create) | the UUID; the readable ID is in `readableEpicId` |

PATCH and DELETE take the **UUID**, and no endpoint maps a readable ID to it
(there is no single-epic GET either). The UUID is also the tail of the epic's
link in the Epics UI: `https://epics.mendix.com/link/epic/PAY-EP-3--<uuid>`.

So `update-epic` and `delete-epic` accept a UUID, that link, or a readable ID
whose UUID the tool has already seen. `create-epic` and every link passed in
store the readable-ID-to-UUID pair per app under `epicUuids` in
`~/.mendix/epics.json`. For an existing epic never seen before, ask the user to
copy its link from the Epics UI.

## Tasks

A task has `title`, `isDone` and `sortId`. Create takes `title` and `isDone`.
Tasks can be listed and created — not updated or deleted through the API.

## Paging

`stories`, `epics` and `labels` take `limit` (1-100, default 20; the tool uses 100)
and `offset`. Responses carry `totalStories` / `totalEpics` / `totalLabels` plus
`links` for the neighbouring pages. The tool's `--all` walks every page; without
it only the first page is fetched.

## Import file format

An array of objects; `title` is the only required key:

```json
[
  {
    "title": "Approval flow for quotations",
    "description": "Multi-level approval on the quotation form.",
    "storyType": "Feature",
    "storyPoints": 5,
    "storyLevel": "Backlog"
  }
]
```

Save as UTF-8. `--level` supplies a fallback for items without `storyLevel`.
`import` needs `--yes` to actually send; `--dry-run` prints the request instead.

The API accepts at most **50 stories per request**; `import` splits larger files
into several requests by itself. Every item is validated before anything is
sent, and titles that already exist in the backlog or repeat in the file are
flagged.

A partially successful import returns HTTP 207: the successful items are created
and the failed ones are reported individually (`code` and `reason` per item, in
request order). It is not a transaction — re-running
the whole file after a partial failure creates duplicates of what already
succeeded.

## What the API does not support

- Deleting a story (epics can be deleted; stories cannot).
- Assigning a story to a person, or moving it into a sprint.
- Creating or attaching labels (labels can only be read; an epic can carry them).
- Comments, attachments, work log, history.
- Listing which apps the token can reach — the app ID has to come from elsewhere.

## Error responses

Body shape: `{"status": 401, "title": "Unauthorized", "detail": "..."}`.

| Code | Meaning |
|---|---|
| 400 | malformed request or an unsupported query parameter |
| 401 | the token is rejected: wrong, expired, or missing the `mx:epics:*` scopes |
| 404 | the app does not exist, does not use Epics, or the token has no access to it |
| 207 | partial success on a bulk create |
