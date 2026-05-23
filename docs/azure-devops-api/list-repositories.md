# List Repositories

> Grounding reference for Azure DevOps Git API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/repositories/get

---

## List Repositories

```
GET /{organization}/{project}/_apis/git/repositories?api-version=7.1
```

Retrieve all Git repositories in a project. Returns repository metadata including ID (GUID), name, default branch, and remote URL.

### Parameters

#### Headers

- **`Authorization`** (string) (required)
  Basic authentication with a Personal Access Token (PAT). Format: `Basic base64(:YOUR_PAT)`.

#### Path and query parameters

- **`organization`** (string) (required)
  Name of your Azure DevOps organization.

- **`project`** (string) (required)
  Project ID or project name. URL-encode special characters.

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`$depth`** (string) (optional)
  Depth of information to return.
  Values: `none`, `full`
  Default: `none`

- **`$top`** (integer) (optional)
  Maximum number of repositories to return.
  Default: `100`

- **`continuationToken`** (string) (optional)
  Token for retrieving the next page of results.

- **`includeAllUrls`** (boolean) (optional)
  If true, all URLs (remote, web, clone) are included in the response.
  Default: `false`

- **`includeLinks`** (boolean) (optional)
  If true, the response includes reference links.
  Default: `false`

- **`includeParent`** (boolean) (optional)
  If true, includes the parent repository (for forked repos).
  Default: `false`

### HTTP response status codes

- **200** — OK. Returns a paged result with `count` and `value` array of repository objects.
- **401** — Unauthorized. Invalid or missing PAT.
- **403** — Forbidden. PAT lacks required scope or project access.
- **404** — Not Found. Organization or project not found.

### Response schema (Status: 200)

- `count`: required, integer — Number of repositories in the `value` array.
- `value`: required, array of GitRepository objects:
  - `id`: required, string — Repository ID (GUID). Use this in other API calls.
  - `name`: required, string — Repository name.
  - `url`: string — REST API URL for this repository.
  - `project`: object — Project information:
    - `id`: string — Project GUID.
    - `name`: string — Project name.
  - `defaultBranch`: string — Default branch ref name (e.g., `refs/heads/main`).
  - `remoteUrl`: string — Remote clone URL.
  - `size`: integer — Repository size in bytes.
  - `parentRepositoryUrl`: string — URL of parent repository if forked.
  - `isDisabled`: boolean — Whether the repository is disabled.
  - `_links`: object — Reference links (when `includeLinks=true`).

### Code examples

#### Example: List all repositories in a project

**Request:**

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories?api-version=7.1"
```

**Response (Status: 200):**

```json
{
  "count": 2,
  "value": [
    {
      "id": "5febef5a-833d-4e14-b9c0-14cb638f91e6",
      "name": "web-app",
      "url": "https://dev.azure.com/myorg/_apis/git/repositories/5febef5a-833d-4e14-b9c0-14cb638f91e6",
      "project": {
        "id": "6ce954b1-ce1f-45d1-b94d-e6bf2464ba2c",
        "name": "myproject"
      },
      "defaultBranch": "refs/heads/main",
      "remoteUrl": "https://dev.azure.com/myorg/myproject/_git/web-app",
      "size": 2456789
    },
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "api-service",
      "url": "https://dev.azure.com/myorg/_apis/git/repositories/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "project": {
        "id": "6ce954b1-ce1f-45d1-b94d-e6bf2464ba2c",
        "name": "myproject"
      },
      "defaultBranch": "refs/heads/main",
      "remoteUrl": "https://dev.azure.com/myorg/myproject/_git/api-service",
      "size": 1234567
    }
  ]
}
```

#### Example: Get repository by name or ID

```bash
# By repository name
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/web-app?api-version=7.1"

# By repository GUID
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/5febef5a-833d-4e14-b9c0-14cb638f91e6?api-version=7.1"
```

#### Example: List repositories across all projects in an org (project omitted)

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/_apis/git/repositories?api-version=7.1"
```

### Common Pitfalls

1. **Repository IDs are GUIDs** — Most Git API endpoints require the repository GUID, not the name. Use `list-repositories` to resolve names to GUIDs first.
2. **Name resolution works too** — You can use the repository name in most endpoints, but GUIDs are more reliable (names can change, GUIDs cannot).
3. **Default branch naming** — The `defaultBranch` is a full ref name (`refs/heads/main`), not just `main`. Strip the prefix if you need the short name.
4. **Empty projects** — A project with no repos returns `{"count": 0, "value": []}`.
5. **Organization-level listing** — Omitting the project segment returns repos across all projects in the org. Useful for cross-project lookups.
