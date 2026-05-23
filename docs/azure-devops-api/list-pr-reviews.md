# List pull request reviewers

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/reviewers/get%20reviewers

## List pull request reviewers

```
GET /{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}/reviewers?api-version=7.1
```

Returns the list of reviewers assigned to a pull request, including their votes and required status.

Alternatively, reviewer information is included when you call the Get pull request endpoint with `include=reviews`.

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

### HTTP response status codes

* **200** - OK — Returns an array of reviewer objects.

* **401** - Unauthorized — Invalid or missing PAT.

* **403** - Forbidden — PAT lacks required scope or project access.

* **404** - Not Found — Pull request, repository, project, or organization not found.

### Response schema (Status: 200)

Array of reviewer objects:

* `vote`: required, integer — Review vote cast by the reviewer:
  * `-10` — Reset (reviewer needs to re-review after changes)
  * `0` — None (no vote yet)
  * `5` — Approve with wishes (approved but has suggestions)
  * `10` — Approve (fully approved)
* `identity`: required, object — Reviewer identity information:
  * `id`: required, string — GUID of the reviewer.
  * `displayName`: required, string — Display name of the reviewer.
  * `emailAddress`: string — Email address of the reviewer.
  * `uniqueName`: string — Unique name / account name.
  * `imageUrl`: string — URL to the reviewer's avatar image.
  * `faces`: array — Face URLs for display.
* `isRequired`: required, boolean — Whether this reviewer is required for the PR to be merged.
* `hasDeclaredAuthorization`: boolean — Whether the reviewer has been granted access to the repository.
* `isFlagged`: boolean — Whether the reviewer has flagged issues.
* `isAssigned`: boolean — Whether the reviewer has been assigned to the PR.

### Code examples

#### Example: Get reviewers for a PR

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/reviewers?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

#### Alternative: Get reviewers via Get pull request with include=reviews

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42?include=reviews&api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

**Response (Status: 200) — Dedicated reviewers endpoint:**

```json
[
  {
    "vote": 10,
    "identity": {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "displayName": "John Coder",
      "emailAddress": "john@example.com",
      "uniqueName": "john@example.com"
    },
    "isRequired": true,
    "hasDeclaredAuthorization": true,
    "isFlagged": false,
    "isAssigned": false
  },
  {
    "vote": 5,
    "identity": {
      "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "displayName": "Alice Reviewer",
      "emailAddress": "alice@example.com",
      "uniqueName": "alice@example.com"
    },
    "isRequired": true,
    "hasDeclaredAuthorization": true,
    "isFlagged": false,
    "isAssigned": false
  },
  {
    "vote": 0,
    "identity": {
      "id": "d4e5f6a7-b8c9-0123-defa-234567890123",
      "displayName": "Bob Pending",
      "emailAddress": "bob@example.com",
      "uniqueName": "bob@example.com"
    },
    "isRequired": false,
    "hasDeclaredAuthorization": true,
    "isFlagged": false,
    "isAssigned": false
  }
]
```

**Response (Status: 200) — Via Get pull request with `include=reviews`:**

```json
{
  "pullRequestId": 42,
  "status": "active",
  "title": "Fix login bug",
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
    },
    {
      "vote": 5,
      "identity": {
        "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
        "displayName": "Alice Reviewer",
        "emailAddress": "alice@example.com"
      },
      "isRequired": true,
      "hasDeclaredAuthorization": true
    }
  ],
  "sourceRefName": "refs/heads/feature-login-fix",
  "targetRefName": "refs/heads/main",
  "mergeStatus": "succeeded",
  "repository": {
    "id": "repo-guid-here",
    "name": "my-repo"
  }
}
```

### Important Notes

* **Vote values** — Understand the vote scale: `10` = approved, `5` = approve with suggestions, `0` = no vote, `-10` = reset/re-review needed.
* **Required reviewers** — PRs with `isRequired: true` reviewers typically block merge until those reviewers approve (unless branch policies allow bypassing).
* **Two ways to get reviewers** — Use the dedicated `/reviewers` endpoint for just reviewer data, or use `include=reviews` on Get pull request to get reviewers along with full PR details in a single call.
* **`hasDeclaredAuthorization`** — If false, the reviewer has been added but may not have repository access yet, which can prevent them from reviewing or voting.
