# List pull requests

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull%20requests/get%20pull%20requests

## List pull requests

```
GET /{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests?api-version=7.1
```

Returns a list of pull requests for a given repository. Supports filtering by status, creator, source/target branches, and pagination.

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

* **`searchCriteria.status`** (string)
  Filter pull requests by status.
  Can be one of: `active`, `abandoned`, `all`

* **`searchCriteria.creatorId`** (string)
  Filter pull requests by the identity ID of the creator.

* **`searchCriteria.sourceRefName`** (string)
  Filter pull requests by source branch name. Must include the `refs/heads/` prefix. Example: `refs/heads/feature-branch`.

* **`searchCriteria.targetRefName`** (string)
  Filter pull requests by target branch name. Must include the `refs/heads/` prefix. Example: `refs/heads/main`.

* **`searchCriteria.createdBy`** (string)
  Filter pull requests by the identity (display name or email) of the creator.

* **`$top`** (integer)
  Maximum number of results to return per page.
  Default: `100`
  Maximum: `200`

* **`continuationToken`** (string)
  Token for retrieving the next page of results. Use the `continuationToken` value from a previous response.

* **`includeLinks`** (boolean)
  If true, the response includes HTML and API links.
  Default: `false`

* **`includeProperties`** (boolean)
  If true, the response includes extended properties.
  Default: `false`

* **`includeReviewers`** (boolean)
  If true, the response includes the list of reviewers for each pull request.
  Default: `false`

* **`includeCommits`** (boolean)
  If true, the response includes the list of commits for each pull request.
  Default: `false`

### HTTP response status codes

* **200** - OK — Returns a paged result with `count` and `value` array of pull request objects.

* **401** - Unauthorized — Invalid or missing PAT.

* **403** - Forbidden — PAT lacks required scope or project access.

* **404** - Not Found — Organization, project, or repository not found.

### Response schema (Status: 200)

* `count`: required, integer — Number of pull requests in the `value` array.
* `value`: required, array of pull request objects:
  * `pullRequestId`: required, integer — Unique identifier of the pull request.
  * `codePushId`: integer — Code push ID associated with the pull request.
  * `status`: required, string — Current status of the pull request. Can be: `active`, `abandoned`, `completed`.
  * `createdBy`: required, object — Identity information about the creator:
    * `id`: required, string — GUID of the creator.
    * `displayName`: required, string — Display name of the creator.
    * `uniqueName`: string — Unique name (email) of the creator.
  * `creationDate`: required, string, format: date-time — When the pull request was created.
  * `sourceRefName`: required, string — Source branch name (e.g. `refs/heads/feature-branch`).
  * `targetRefName`: required, string — Target branch name (e.g. `refs/heads/main`).
  * `mergeStatus`: required, string — Merge status. Can be: `notSet`, `unknown`, `batched`, `succeeded`, `failed`, `conflicts`, `blockedByPolicy`, `blockedByCrossProvider`, `indeterminate`, `candidate`, `succeededWithConflicts`, `succeededWithSemanticsMismatch`, `noAutoMerge`, `notMergeable`.
  * `lastMergeSourceCommit`: object — Last source commit merged:
    * `commitId`: required, string — SHA of the commit.
  * `reviewers`: array — List of reviewer objects (when `includeReviewers=true`):
    * `vote`: integer — Review vote: `-10` (reset), `0` (none), `5` (approve with wishes), `10` (approve).
    * `identity`: object — Reviewer identity info (id, displayName, emailAddress).
    * `isRequired`: boolean — Whether this reviewer is required.
  * `commitsToReview`: array — Commits in this pull request (when `includeCommits=true`):
    * `commitId`: required, string — SHA of the commit.
    * `commentCount`: integer — Number of comments on this commit.
  * `repository`: object — Repository information:
    * `id`: required, string — Repository ID (GUID).
    * `name`: required, string — Repository name.
  * `url`: string — REST API URL for this pull request.
  * `_links`: object — HTML and API links (when `includeLinks=true`).

### Code examples

#### Example: List all open pull requests

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests?searchCriteria.status=active&api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

#### Example: List open PRs from a specific source branch

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests?searchCriteria.status=active&searchCriteria.sourceRefName=refs/heads/feature-login&$top=50&includeReviewers=true&api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

#### Example: Paginate through results

**Request:**

```bash
curl -L \
  -X GET \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests?searchCriteria.status=all&\$top=200&continuationToken=PREVIOUS_TOKEN&includeLinks=true&api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)"
```

**Response (Status: 200):**

```json
{
  "count": 2,
  "value": [
    {
      "pullRequestId": 42,
      "codePushId": 101,
      "status": "active",
      "createdBy": {
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "displayName": "Jane Developer",
        "uniqueName": "jane@example.com"
      },
      "creationDate": "2025-01-15T10:30:00.000Z",
      "sourceRefName": "refs/heads/feature-login",
      "targetRefName": "refs/heads/main",
      "mergeStatus": "succeeded",
      "lastMergeSourceCommit": {
        "commitId": "d7f4a1b2c3e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9"
      },
      "repository": {
        "id": "repo-guid-here",
        "name": "my-repo"
      }
    },
    {
      "pullRequestId": 43,
      "status": "abandoned",
      "createdBy": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "displayName": "John Coder",
        "uniqueName": "john@example.com"
      },
      "creationDate": "2025-01-14T08:00:00.000Z",
      "sourceRefName": "refs/heads/hotfix-typo",
      "targetRefName": "refs/heads/main",
      "mergeStatus": "failed",
      "repository": {
        "id": "repo-guid-here",
        "name": "my-repo"
      }
    }
  ]
}
```
