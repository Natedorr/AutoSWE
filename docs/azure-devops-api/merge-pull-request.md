# Complete (merge) a pull request

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull%20requests/complete%20a%20pullrequest

## Complete a pull request

```
POST /{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}/complete?api-version=7.1
```

Completes (merges) a pull request into the target branch. This is the recommended approach over setting `status: completed` via PATCH, as it provides control over merge strategy, source branch cleanup, and the merge commit message.

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
  Integer ID of the pull request to complete.

#### Body parameters

* **`mergeStrategy`** (string)
  Strategy for merging the pull request.
  Can be one of:
  * `noFastForward` — Creates a merge commit. Preserves individual commits.
  * `squash` — Squashes all commits into a single commit.
  * `rebase` — Rebases the source commits onto the target branch.
  * `rebaseSemantic` — Rebases with semantic commit messages.

  Default: `noFastForward` (or whatever the repository policy specifies)

* **`deleteSourceBranch`** (boolean)
  Whether to delete the source branch after merging.
  Default: `false`

* **`mergeCommitMessage`** (string)
  Custom commit message for the merge. If omitted, uses a default message based on the PR title.

* **`completedBy`** (object)
  Identity of the user completing the merge. If not specified, uses the authenticated user:
  * `id`: required, string — GUID of the user completing the merge.

* **`keepExistingFiles`** (boolean)
  Whether to keep existing files during merge. Used for specific merge scenarios.
  Default: `false`

### HTTP response status codes

* **200** - OK — Pull request completed successfully. Returns the updated pull request object with `status: completed`.

* **401** - Unauthorized — Invalid or missing PAT.

* **403** - Forbidden — PAT lacks required scope, or merge blocked by policy.

* **404** - Not Found — Pull request, repository, project, or organization not found.

* **409** - Conflict — Merge blocked due to conflicts, policy failures, or the PR is not in the `active` state.

### Response schema (Status: 200)

Returns the updated pull request object:

* `pullRequestId`: required, integer
* `status`: required, string — Will be `completed`.
* `title`: string
* `description`: string
* `sourceRefName`: required, string
* `targetRefName`: required, string
* `createdBy`: required, object
* `creationDate`: required, string, format: date-time
* `closedBy`: required, object — Who completed the merge.
* `closedDate`: required, string, format: date-time — When the merge was completed.
* `mergeStatus`: required, string — Should be `succeeded`.
* `mergeId`: string, format: uuid — GUID of the merge commit.
* `mergedBy`: required, object — Identity of who merged.
* `mergedDate`: required, string, format: date-time — When merged.
* `reviewers`: array
* `repository`: object
* `url`: string

### Code examples

#### Example: Merge with squash

**Request:**

```bash
curl -L \
  -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/complete?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "mergeStrategy": "squash",
    "deleteSourceBranch": true,
    "mergeCommitMessage": "Merged PR #42: Fix login bug"
  }'
```

#### Example: Merge with merge commit (no-fast-forward)

**Request:**

```bash
curl -L \
  -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/complete?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "mergeStrategy": "noFastForward",
    "deleteSourceBranch": true,
    "mergeCommitMessage": "Merge pull request #42: Fix login bug"
  }'
```

#### Example: Merge with rebase

**Request:**

```bash
curl -L \
  -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42/complete?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "mergeStrategy": "rebase",
    "deleteSourceBranch": false
  }'
```

#### Alternative approach: Update PR status to completed (less control)

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

> **Note:** This alternative approach works but does not allow you to specify merge strategy, delete source branch, or set a custom merge message. Use the `/complete` endpoint above instead when you need these options.

**Response (Status: 200):**

```json
{
  "pullRequestId": 42,
  "status": "completed",
  "title": "Fix login bug",
  "description": "Resolves the SSO login issue",
  "sourceRefName": "refs/heads/feature-login-fix",
  "targetRefName": "refs/heads/main",
  "createdBy": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "displayName": "Jane Developer",
    "emailAddress": "jane@example.com"
  },
  "creationDate": "2025-01-15T10:30:00.000Z",
  "closedBy": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "displayName": "Jane Developer",
    "emailAddress": "jane@example.com"
  },
  "closedDate": "2025-01-16T14:00:00.000Z",
  "mergeStatus": "succeeded",
  "mergeId": "f6a7b8c9-d0e1-2345-fa67-890123456789",
  "mergedBy": {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "displayName": "Jane Developer",
    "emailAddress": "jane@example.com"
  },
  "mergedDate": "2025-01-16T14:00:00.000Z",
  "repository": {
    "id": "repo-guid-here",
    "name": "my-repo",
    "project": {
      "id": "project-guid",
      "name": "my-project"
    }
  },
  "url": "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42"
}
```

### Important Notes

* **Prerequisites for merging:**
  * All required reviewers must have approved (vote >= 5 or 10)
  * All build/validation policies must pass
  * The PR must be in `active` status
  * No unresolved code conflicts (`mergeStatus` should be `succeeded`, `batched`, or `candidate`)

* **Merge strategies explained:**
  * `noFastForward` — Creates a merge commit preserving history. Best for teams that want a full audit trail.
  * `squash` — Combines all commits into one. Clean history, but loses individual commit granularity.
  * `rebase` — Rewrites source commits on top of target. Linear history, but rewrites commit SHAs.
  * `rebaseSemantic` — Same as rebase but attempts to generate semantic commit messages.

* **`deleteSourceBranch`** — Set to `true` to automatically delete the source branch after merge. The source branch still exists if set to `false`.

* **Policy enforcement** — If branch policies require specific merge strategies, the `mergeStrategy` parameter may be ignored or cause a 409 conflict.

* **Conflict resolution** — If `mergeStatus` is `conflicts`, you must resolve conflicts before completing the PR. This typically involves merging the target branch into the source branch and pushing the resolution.
