# Create a pull request

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull%20requests/create%20pull%20request

## Create a pull request

```
POST /{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests?api-version=7.1
```

Creates a new pull request in the specified repository. The source branch must already exist and contain commits not yet merged into the target branch.

**Note:** Azure DevOps returns **200 OK** (not 201 Created) for successful pull request creation.

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

#### Body parameters

* **`sourceRefName`** (string) (required)
  Source branch name. **Must include the `refs/heads/` prefix.** Example: `refs/heads/feature-login`.

* **`targetRefName`** (string) (required)
  Target branch name. **Must include the `refs/heads/` prefix.** Example: `refs/heads/main`.

* **`title`** (string)
  Title of the pull request.

* **`description`** (string)
  Markdown description of the pull request.

* **`reviewers`** (array)
  List of reviewers to assign. Each reviewer requires an identity GUID, not a display name:
  * `identity`: object — Identity of the reviewer:
    * `id`: required, string — GUID of the user. Look up via the contributors endpoint.
  * `isRequired`: boolean — Whether the reviewer is required.

* **`workItemRefs`** (array)
  Work items to link to this pull request (similar to linking issues):
  * `id`: required, integer — Work item ID.

* **`isDraft`** (boolean)
  Whether this is a draft pull request.
  Default: `false`

* **`transitionWorkItems`** (boolean)
  Whether to transition linked work items automatically.
  Default: `true`

* **`autoCompleteSet`** (boolean)
  Whether to enable auto-complete when policies are met.
  Default: `false`

### HTTP response status codes

* **200** - OK — Pull request created successfully. Returns the created pull request object.

* **401** - Unauthorized — Invalid or missing PAT.

* **403** - Forbidden — PAT lacks required scope or project access.

* **404** - Not Found — Repository or project not found.

* **409** - Conflict — Source branch doesn't exist, or a pull request with these source/target refs already exists.

### Response schema (Status: 200)

Returns the created pull request object (same schema as Get pull request):

* `pullRequestId`: required, integer
* `status`: required, string — Will be `active`.
* `title`: string
* `description`: string
* `sourceRefName`: required, string
* `targetRefName`: required, string
* `createdBy`: required, object
* `creationDate`: required, string, format: date-time
* `mergeStatus`: required, string
* `reviewers`: array
* `isDraft`: boolean
* `repository`: object
* `url`: string

### Code examples

#### Example: Create a basic pull request

**Request:**

```bash
curl -L \
  -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "sourceRefName": "refs/heads/feature-login-fix",
    "targetRefName": "refs/heads/main",
    "title": "Fix login bug",
    "description": "Resolves the SSO login issue reported in ticket #1234"
  }'
```

#### Example: Create PR with reviewers and work item links

**Request:**

```bash
curl -L \
  -X POST \
  "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':YOUR_PAT' | base64)" \
  -H "Content-Type: application/json" \
  -d '{
    "sourceRefName": "refs/heads/feature-login-fix",
    "targetRefName": "refs/heads/main",
    "title": "Fix login bug",
    "description": "Resolves the SSO login issue",
    "reviewers": [
      {
        "identity": {
          "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901"
        },
        "isRequired": true
      },
      {
        "identity": {
          "id": "c3d4e5f6-a7b8-9012-cdef-123456789012"
        },
        "isRequired": false
      }
    ],
    "workItemRefs": [
      {
        "id": 1234
      }
    ],
    "isDraft": false
  }'
```

**Response (Status: 200):**

```json
{
  "pullRequestId": 42,
  "status": "active",
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
  "mergeStatus": "notSet",
  "isDraft": false,
  "reviewers": [
    {
      "vote": 0,
      "identity": {
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "displayName": "John Coder",
        "emailAddress": "john@example.com"
      },
      "isRequired": true,
      "hasDeclaredAuthorization": true
    }
  ],
  "repository": {
    "id": "repo-guid-here",
    "name": "my-repo"
  },
  "url": "https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/42"
}
```

### Important Notes

* **Branch names MUST include `refs/heads/` prefix** — Omitting the prefix will cause a 409 Conflict error.
* **Reviewers require identity GUIDs** — You cannot use display names. Use the contributors endpoint (`GET /{org}/{project}/_apis/git/repositories/{repositoryId}/contributors?api-version=7.1`) to look up user GUIDs.
* **`workItemRefs` links PRs to work items** — This is the Azure DevOps equivalent of linking GitHub issues to a pull request.
* **Auto-complete** — Set `autoCompleteSet` to `true` to allow the PR to auto-complete when all policies pass.
* **Draft PRs** — Set `isDraft` to `true` for work-in-progress PRs that shouldn't trigger policy checks or notifications.
