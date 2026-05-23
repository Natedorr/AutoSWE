# List pull request threads (comments)

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/comments/get%20threads

## List pull request threads

```
GET /{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}/threads?api-version=7.1
```

Azure DevOps uses a **threads model** for PR comments. Each thread contains one or more comments. Threads can be general PR-level comments (not tied to a specific file) or code-specific comments (tied to a file path and line number). This endpoint returns all threads and their comments for a given pull request.

### Parameters

#### Headers

* **`Authorization`** (string) (required)
  Basic authentication with a Personal Access Token (PAT). Format: `Basic base64(:YOUR_PAT)`. The username is empty — just a colon followed by your PAT, then base64-encoded.

#### Path and query parameters

* **`org`** (string) (required)
  Name of your Azure DevOps organization.

* **`project`** (string) (required)
  Project ID or project name.

* **`repositoryId`** (string) (required)
  Repository ID or name.

* **`pullRequestId`** (integer) (required)
  Integer ID of the pull request.

* **`status`** (string)
  Filter threads by status.
  Can be one of: `active`, `closed`, `all`

* **`includeDeletedComments`** (boolean)
  If true, includes soft-deleted comments in the response.
  Default: `false`

### HTTP response status codes

* **200** - OK — Returns an array of thread objects.

* **401** - Unauthorized — Invalid or missing PAT.

* **403** - Forbidden — PAT lacks required scope or project access.

* **404** - Not Found — Pull request, repository, project, or organization not found.

### Response schema (Status: 200)

Array of thread objects:

* `id`: required, integer — Thread ID.
* `comments`: required, array — Comments within this thread:
  * `id`: required, integer — Comment ID.
  * `parentCommentId`: integer or null — ID of the parent comment (null for top-level comments, parent ID for replies).
  * `content`: required, object — Comment content:
    * `raw`: string — Raw markdown text.
    * `html`: string — Rendered HTML (when `includeContentHtml=true`).
    * `markdown`: string — Processed markdown.
  * `commentType`: required, string — Type of comment: `general` (PR-level), `code` (file/line-specific).
  * `publishedBy`: required, object — User who published the comment:
    * `id`: required, string — User GUID.
    * `displayName`: required, string — Display name.
    * `uniqueName`: string — Unique name (email).
  * `publishedDate`: required, string, format: date-time — When the comment was published.
  * `lastEditedDate`: string, format: date-time — When the comment was last edited.
  * `isDeleted`: boolean — Whether the comment has been soft-deleted.
  * `isResolved`: boolean — Whether the comment is marked as resolved.
* `status`: required, string — Thread status: `active`, `closed`.
* `publishedDate`: required, string, format: date-time — When the thread was first published.
* `changedDate`: required, string, format: date-time — When the thread was last changed.
* `structureId`: string or null — For code comments, this contains the file path and line information (e.g. `f:/src/file.ts:42:1-42:20`). `null` for general PR-level comments.
* `threadContext`: object — Context for code-specific threads:
  * `filePath`: string — Path to the file (e.g. `/src/file.ts`).
  * `rightFileStart`: object — Start position in the target branch:
    * `line`: integer — 1-based line number.
    * `offset`: integer — Character offset within the line.
  * `rightFileEnd`: object — End position in the target branch:
    * `line`: integer — 1-based line number.
    * `offset`: integer — Character offset within the line.
* `properties`: object — Additional properties on the thread.

### Code examples

#### Example: List all threads on a PR

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/threads?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

#### Example: List only active threads

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/threads?status=active&api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

#### Example: Include deleted comments

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/threads?status=all&includeDeletedComments=true&api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

**Response (Status: 200):**

```json
[
  {
    "id": 1,
    "status": "active",
    "publishedDate": "2025-01-15T11:00:00.000Z",
    "changedDate": "2025-01-15T14:30:00.000Z",
    "structureId": null,
    "comments": [
      {
        "id": 1,
        "parentCommentId": null,
        "content": {
          "raw": "This looks great! 👍 Ready to merge.",
          "markdown": "This looks great! 👍 Ready to merge."
        },
        "commentType": "general",
        "publishedBy": {
          "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
          "displayName": "John Coder",
          "uniqueName": "john@example.com"
        },
        "publishedDate": "2025-01-15T11:00:00.000Z",
        "isDeleted": false,
        "isResolved": false
      },
      {
        "id": 2,
        "parentCommentId": 1,
        "content": {
          "raw": "Thanks! Going to squash and merge shortly.",
          "markdown": "Thanks! Going to squash and merge shortly."
        },
        "commentType": "general",
        "publishedBy": {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "displayName": "Jane Developer",
          "uniqueName": "jane@example.com"
        },
        "publishedDate": "2025-01-15T14:30:00.000Z",
        "isDeleted": false,
        "isResolved": false
      }
    ]
  },
  {
    "id": 2,
    "status": "active",
    "publishedDate": "2025-01-15T12:00:00.000Z",
    "changedDate": "2025-01-15T12:00:00.000Z",
    "structureId": "f:/src/auth/login.ts:42:1-42:20",
    "threadContext": {
      "filePath": "/src/auth/login.ts",
      "rightFileStart": {
        "line": 42,
        "offset": 1
      },
      "rightFileEnd": {
        "line": 42,
        "offset": 20
      }
    },
    "comments": [
      {
        "id": 3,
        "parentCommentId": null,
        "content": {
          "raw": "This variable name is misleading — consider renaming to `sessionToken`.",
          "markdown": "This variable name is misleading — consider renaming to `sessionToken`."
        },
        "commentType": "code",
        "publishedBy": {
          "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
          "displayName": "John Coder",
          "uniqueName": "john@example.com"
        },
        "publishedDate": "2025-01-15T12:00:00.000Z",
        "isDeleted": false,
        "isResolved": false
      }
    ]
  }
]
```

### Important Notes

* **`structureId` is null for general comments** — If `structureId` is `null`, the thread is a PR-level comment. If it has a value starting with `f:`, it's a code-specific comment tied to a file and line.
* **Replies have `parentCommentId`** — Top-level comments have `parentCommentId: null`. Replies reference their parent's `id`.
* **`commentType: code` vs `general`** — Code comments appear inline in the file diff. General comments appear in the conversation tab.
* **Soft-deleted comments** — Deleted comments have `isDeleted: true` and are excluded unless `includeDeletedComments=true`.
