# Update a pull request

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull%20requests/update%20pull%20request

## Update a pull request

```
PATCH /{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}?api-version=7.1
```

Updates an existing pull request. You can modify the title, description, status, draft state, reviewers, and other properties. Only the fields you want to change need to be included in the request body.

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
  Integer ID of the pull request to update.

#### Body parameters

Include any of the following fields to update:

* **`title`** (string)
  New title for the pull request.

* **`description`** (string)
  New markdown description.

* **`status`** (string)
  New status for the pull request.
  Can be one of: `active`, `abandoned`, `completed`

* **`isDraft`** (boolean)
  Set to `true` to convert to draft, `false` to mark as ready for review.

* **`reviewers`** (array)
  Update the reviewer list:
  * `identity`: object:
    * `id`: required, string — GUID of the reviewer.
  * `isRequired`: boolean — Whether the reviewer is required.
  * `vote`: integer — Vote value: `-10` (reset), `0` (none), `5` (approve with wishes), `10` (approve).

* **`sourceRefName`** (string)
  New source branch (must include `refs/heads/` prefix).

* **`targetRefName`** (string)
  New target branch (must include `refs/heads/` prefix).

* **`transitionWorkItems`** (boolean)
  Whether to transition linked work items.

* **`autoCompleteSet`** (boolean)
  Whether to enable auto-complete when policies pass.

### HTTP response status codes

* **200** - OK — Pull request updated successfully. Returns the updated pull request object.

* **401** - Unauthorized — Invalid or missing PAT.

* **403** - Forbidden — PAT lacks required scope or project access.

* **404** - Not Found — Pull request, repository, project, or organization not found.

* **409** - Conflict — Invalid state transition or branch not found.

### Response schema (Status: 200)

Returns the updated pull request object (same schema as Get pull request):

* `pullRequestId`: required, integer
* `status`: required, string — Updated status.
* `title`: string
* `description`: string
* `sourceRefName`: required, string
* `targetRefName`: required, string
* `createdBy`: required, object
* `creationDate`: required, string, format: date-time
* `closedBy`: object — Present if status changed to `abandoned` or `completed`.
* `closedDate`: string, format: date-time — Present if status changed to `abandoned` or `completed`.
* `mergeStatus`: required, string
* `reviewers`: array
* `isDraft`: boolean
* `repository`: object
* `url`: string

### Code examples

#### Example: Update PR title and description

**Request:**

```bash
curl -L \
  -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Fix login bug - Updated",
    "description": "Updated description with more details about the fix"
  }'
```

#### Example: Abandon a pull request

**Request:**

```bash
curl -L \
  -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "abandoned"
  }'
```

#### Example: Mark PR as ready for review (un-draft)

**Request:**

```bash
curl -L \
  -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "isDraft": false
  }'
```

#### Example: Add reviewers to an existing PR

**Request:**

```bash
curl -L \
  -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "reviewers": [
      {
        "identity": {
          "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        },
        "isRequired": true
      },
      {
        "identity": {
          "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
        },
        "isRequired": false
      }
    ]
  }'
```

#### Example: Complete (merge) a pull request

**Request:**

```bash
curl -L \
  -X PATCH \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed"
  }'
```

**Response (Status: 200):**

```json
{
  "pullRequestId": 42,
  "status": "completed",
  "title": "Fix login bug",
  "sourceRefName": "refs/heads/feature-login-fix",
  "targetRefName": "refs/heads/main",
  "createdBy": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "displayName": "Jane Developer",
    "emailAddress": "jane@example.com"
  },
  "closedBy": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "displayName": "Jane Developer",
    "emailAddress": "jane@example.com"
  },
  "closedDate": "2025-01-16T14:00:00.000Z",
  "mergeStatus": "succeeded",
  "mergedBy": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "displayName": "Jane Developer",
    "emailAddress": "jane@example.com"
  },
  "mergedDate": "2025-01-16T14:00:00.000Z",
  "repository": {
    "id": "repo-guid-here",
    "name": "my-repo"
  }
}
```

### Important Notes

* **Status transitions** — A PR can transition from `active` to either `abandoned` or `completed`. You cannot re-open an abandoned or completed PR.
* **`completed` vs. `/complete` endpoint** — Setting `status: completed` via PATCH works, but the dedicated `/complete` endpoint (see `merge-pull-request.md`) is recommended because it allows you to specify merge strategy, delete source branch, and custom merge commit message.
* **Reviewers are replaced, not added** — Sending a `reviewers` array replaces the entire reviewer list. To add a reviewer, first GET the current reviewers, then PATCH with the combined list.
* **Branch names require `refs/heads/` prefix** — Same as create. Omitting it causes a 409.
