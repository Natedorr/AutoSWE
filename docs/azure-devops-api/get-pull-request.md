# Get a pull request

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull%20requests/get%20pull%20request

## Get a pull request

```
GET /{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}?api-version=7.1
```

Returns a single pull request with full details. Supports including work item references, activity, commits, statuses, reviews, identity references, and utility data.

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
  Integer ID of the pull request to retrieve.

* **`include`** (string)
  Comma-separated list of additional data to include in the response.
  Can include: `workItemRefs`, `activity`, `commits`, `statuses`, `reviews`, `identityRefs`, `utilityData`

* **`includeProperties`** (boolean)
  If true, the response includes extended properties on the pull request.
  Default: `false`

* **`includeLinks`** (boolean)
  If true, the response includes HTML and API links.
  Default: `false`

### HTTP response status codes

* **200** - OK — Returns the full pull request object.

* **401** - Unauthorized — Invalid or missing PAT.

* **403** - Forbidden — PAT lacks required scope or project access.

* **404** - Not Found — Pull request, repository, project, or organization not found.

### Response schema (Status: 200)

Full pull request object:

* `pullRequestId`: required, integer — Unique identifier of the pull request.
* `status`: required, string — Current status: `active`, `abandoned`, `completed`.
* `title`: string — Title of the pull request.
* `description`: string — Markdown description of the pull request.
* `sourceRefName`: required, string — Source branch (e.g. `refs/heads/feature-branch`).
* `targetRefName`: required, string — Target branch (e.g. `refs/heads/main`).
* `createdBy`: required, object — Creator identity (id, displayName, emailAddress).
* `creationDate`: required, string, format: date-time — When the pull request was created.
* `closedBy`: object — Who closed the pull request (id, displayName, emailAddress). Present when status is `abandoned` or `completed`.
* `closedDate`: string, format: date-time — When the pull request was closed.
* `mergeStatus`: required, string — Current merge status.
* `mergeId`: string, format: uuid — GUID of the merge commit.
* `mergedBy`: object — Who merged the pull request (id, displayName, emailAddress).
* `mergedDate`: string, format: date-time — When the pull request was merged.
* `reviewers`: array — List of reviewers:
  * `vote`: integer — Review vote: `-10` (reset), `0` (none), `5` (approve with wishes), `10` (approve).
  * `identity`: object — Reviewer identity (id, displayName, emailAddress).
  * `isRequired`: boolean — Whether review is required.
  * `hasDeclaredAuthorization`: boolean — Whether reviewer has access to the repo.
* `supportedRemoteQueries`: array — Supported remote query types.
* `repository`: object — Repository info (id, name, url, project).
* `codePushId`: integer — Code push ID.
* `isDraft`: boolean — Whether this is a draft pull request.
* `workItemRefs`: array — Linked work items (when `include=workItemRefs`):
  * `id`: integer — Work item ID.
* `lastMergeSourceCommit`: object — Last merged source commit:
  * `commitId`: string — Commit SHA.
* `commits`: array — Commits in the PR (when `include=commits`):
  * `commitId`: string — Commit SHA.
  * `commentCount`: integer — Number of comments on the commit.
  * `authorDate`: string, format: date-time — When authored.
  * `committerDate`: string, format: date-time — When committed.
* `activity`: array — Review activity (when `include=activity`):
  * `revision`: integer — Revision number.
  * `changeId`: string — Change ID.
  * `comments`: array — Comments in this revision.
  * `createdDate`: string, format: date-time — When this activity was recorded.
* `statuses`: array — Build/validation statuses (when `include=statuses`):
  * `id`: integer — Status ID.
  * `status`: string — `notApplicable`, `pending`, `inProgress`, `succeeded`, `partiallySucceeded`, `failed`, `warning`.
  * `description`: string — Status description.
  * `context`: object:
    * `genre`: string — Context genre.
    * `name`: string — Context name.
* `url`: string — REST API URL for this pull request.
* `_links`: object — HTML and API links (when `includeLinks=true`).

### Code examples

#### Example: Get a single pull request

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

#### Example: Get PR with work item refs and commits

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?include=workItemRefs,commits,statuses,identityRefs&api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

#### Example: Get PR with all included data

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?include=workItemRefs,activity,commits,statuses,reviews,identityRefs,utilityData&includeLinks=true&includeProperties=true&api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

**Response (Status: 200):**

```json
{
  "pullRequestId": 42,
  "status": "active",
  "title": "Fix login bug",
  "description": "Resolves the SSO login issue reported in ticket #1234",
  "sourceRefName": "refs/heads/feature-login-fix",
  "targetRefName": "refs/heads/main",
  "createdBy": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "displayName": "Jane Developer",
    "emailAddress": "jane@example.com"
  },
  "creationDate": "2025-01-15T10:30:00.000Z",
  "mergeStatus": "succeeded",
  "mergeId": "e5f6a7b8-c9d0-1234-ef56-789012345678",
  "reviewers": [
    {
      "vote": 10,
      "identity": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "displayName": "John Coder",
        "emailAddress": "john@example.com"
      },
      "isRequired": true,
      "hasDeclaredAuthorization": true
    }
  ],
  "isDraft": false,
  "repository": {
    "id": "repo-guid-here",
    "name": "my-repo",
    "project": {
      "id": "project-guid",
      "name": "my-project"
    }
  },
  "codePushId": 101,
  "url": "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42"
}
```
