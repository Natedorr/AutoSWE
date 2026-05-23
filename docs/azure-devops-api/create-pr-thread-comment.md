# Create a pull request thread (comment)

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/comments/create%20thread

## Create a pull request thread

```
POST /{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}/threads?api-version=7.1
```

Creates a new comment thread on a pull request. Supports both general PR-level comments and code-specific comments (tied to a file path and line range).

### Parameters

#### Headers

* **`Authorization`** (string) (required)
  Basic authentication with a Personal Access Token (PAT). Format: `Basic base64(:YOUR_PAT)`. The username is empty — just a colon followed by your PAT, then base64-encoded.

* **`Content-Type`** (string) (required)
  Set to `application/json`.

#### Path and query parameters

* **`org`** (string) (required)
  Name of your Azure DevOps organization.

* **`project`** (string) (required)
  Project ID or project name.

* **`repositoryId`** (string) (required)
  Repository ID or name.

* **`pullRequestId`** (integer) (required)
  Integer ID of the pull request.

#### Body parameters

* **`comments`** (array) (required)
  Array of comments to create in this thread. For a new thread, this is typically a single comment:
  * `content`: required, string — Markdown text of the comment.

* **`status`** (string)
  Thread status. For new threads:
  Can be one of: `active`, `closed`
  Default: `active`

* **`threadContext`** (object)
  Context for code-specific comments. Omit this for general PR-level comments:
  * `filePath`: required, string — Path to the file in the repository (e.g. `/src/file.ts`).
  * `rightFileStart`: required, object — Start position in the target branch file:
    * `line`: required, integer — 1-based line number.
    * `offset`: required, integer — Character offset within the line (1-based).
  * `rightFileEnd`: required, object — End position in the target branch file:
    * `line`: required, integer — 1-based line number.
    * `offset`: required, integer — Character offset within the line (1-based).
  * `rightFileEndRegion`: object — End region for multi-line selections:
    * `line`: integer — 1-based line number.
    * `offset`: integer — Character offset.
  * `rightFileStartRegion`: object — Start region for multi-line selections:
    * `line`: integer — 1-based line number.
    * `offset`: integer — Character offset.

### HTTP response status codes

* **200** - OK — Thread created successfully. Returns the created thread object.

* **401** - Unauthorized — Invalid or missing PAT.

* **403** - Forbidden — PAT lacks required scope or project access.

* **404** - Not Found — Pull request, repository, project, or organization not found.

### Response schema (Status: 200)

Returns the created thread object:

* `id`: required, integer — Thread ID.
* `status`: required, string — `active` or `closed`.
* `publishedDate`: required, string, format: date-time
* `changedDate`: required, string, format: date-time
* `structureId`: string or null — File/line reference for code comments.
* `threadContext`: object — Thread context (for code comments).
* `comments`: required, array — The comments in this thread:
  * `id`: required, integer — Comment ID.
  * `parentCommentId`: integer or null
  * `content`: object:
    * `raw`: string — Raw markdown.
    * `markdown`: string — Processed markdown.
  * `commentType`: string — `general` or `code`.
  * `publishedBy`: object — User who posted.
  * `publishedDate`: string, format: date-time
  * `isDeleted`: boolean
  * `isResolved`: boolean

### Code examples

#### Example: Create a general PR-level comment

**Request:**

```bash
curl -L \
  -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/threads?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "comments": [
      {
        "content": "This looks great! 👍 Ready to merge."
      }
    ]
  }'
```

#### Example: Create a code-specific comment on a file/line

**Request:**

```bash
curl -L \
  -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/threads?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active",
    "comments": [
      {
        "content": "This variable name is misleading — consider renaming to `sessionToken`."
      }
    ],
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
    }
  }'
```

#### Example: Create a comment on a range of lines

**Request:**

```bash
curl -L \
  -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/threads?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active",
    "comments": [
      {
        "content": "These error handling blocks could be simplified with a helper function."
      }
    ],
    "threadContext": {
      "filePath": "/src/auth/middleware.ts",
      "rightFileStart": {
        "line": 15,
        "offset": 1
      },
      "rightFileEnd": {
        "line": 32,
        "offset": 3
      }
    }
  }'
```

**Response (Status: 200):**

```json
{
  "id": 3,
  "status": "active",
  "publishedDate": "2025-01-15T15:00:00.000Z",
  "changedDate": "2025-01-15T15:00:00.000Z",
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
      "id": 5,
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
      "publishedDate": "2025-01-15T15:00:00.000Z",
      "isDeleted": false,
      "isResolved": false
    }
  ]
}
```

### Important Notes

* **`rightFile` = target branch** — Line numbers in `threadContext` refer to the target branch file (the file as it exists in the target branch), not the source branch.
* **1-based line numbers** — Line numbers start at 1, not 0.
* **1-based character offsets** — Character offsets within a line start at 1.
* **Omit `threadContext` for general comments** — To create a PR-level comment that appears in the conversation tab, simply don't include `threadContext`.
* **Replies use a different endpoint** — To reply to an existing comment, use the "Update thread" endpoint (`PATCH`) with the existing thread ID, adding a new comment with `parentCommentId` set to the original comment's ID.
