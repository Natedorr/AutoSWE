# List Branches

> Grounding reference for Azure DevOps Git API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/refs/list

---

## List Branches (Refs)

```
GET /{organization}/{project}/_apis/git/repositories/{repositoryId}/refs?api-version=7.1
```

Queries a repository for its refs and returns them. Returns branches, tags, and other refs. Use the `filter` parameter to narrow results.

### Parameters

#### Headers

- **`Authorization`** (string) (required)
  Basic authentication with a Personal Access Token (PAT). Format: `Basic base64(:YOUR_PAT)`.

#### Path and query parameters

- **`organization`** (string) (required)
  Name of your Azure DevOps organization.

- **`project`** (string) (required)
  Project ID or project name.

- **`repositoryId`** (string) (required)
  Repository ID (GUID) or name.

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`filter`** (string) (optional)
  A filter to apply to the refs using **starts with** matching.
  Examples: `heads` (all branches), `heads/main` (specific branch), `heads/feature/` (all feature branches), `tags` (all tags)

- **`filterContains`** (string) (optional)
  A filter to apply to the refs using **contains** matching.

- **`$top`** (integer) (optional)
  Maximum number of refs to return.
  Default: `100` if `continuationToken` is provided, unlimited otherwise
  Maximum: `1000`

- **`continuationToken`** (string) (optional)
  Token for retrieving the next page of results.

- **`includeLinks`** (boolean) (optional)
  If true, includes reference links.
  Default: `false`

- **`includeStatuses`** (boolean) (optional)
  If true, includes up to the first 1000 commit statuses for each ref.
  Default: `false`

- **`latestStatusesOnly`** (boolean) (optional)
  If true, includes only the tip commit status for each ref. Requires `includeStatuses=true`.
  Default: `false`

- **`includeMyBranches`** (boolean) (optional)
  Returns only branches the user owns, favorites, and the default branch. Cannot be combined with `filter`.
  Default: `false`

- **`peelTags`** (boolean) (optional)
  If true, annotated tags populate the `PeeledObjectId` property.
  Default: `false`

### HTTP response status codes

- **200** — OK. Returns an array of GitRef objects.
- **401** — Unauthorized. Invalid or missing PAT.
- **403** — Forbidden. PAT lacks required scope or repo access.
- **404** — Not Found. Organization, project, or repository not found.

### Response schema (Status: 200)

Returns an array of GitRef objects (wrapped in `{ "value": [...] }`):

- `name`: required, string — Full ref name (e.g., `refs/heads/main`, `refs/tags/v1.0`).
- `objectId`: string — SHA-1 commit ID this ref points to. `null` if unborn.
- `creator`: object — User who created the ref:
  - `id`: string — User GUID.
  - `displayName`: string — User's display name.
  - `uniqueName`: string — User's email.
- `url`: string — REST API URL for this ref.
- `statuses`: array — Commit statuses (when `includeStatuses=true`).
- `peeledObjectId`: string — Underlying commit for annotated tags (when `peelTags=true`).

### Code examples

#### Example: List all branches

**Request:**

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/refs?filter=heads&api-version=7.1"
```

**Response (Status: 200):**

```json
{
  "count": 3,
  "value": [
    {
      "name": "refs/heads/main",
      "objectId": "d7f4a1b2c3e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
      "creator": {
        "displayName": "Jane Developer",
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "uniqueName": "jane@example.com"
      }
    },
    {
      "name": "refs/heads/develop",
      "objectId": "abc123def456789abc123def456789abc123def456",
      "creator": {
        "displayName": "John Coder",
        "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
        "uniqueName": "john@example.com"
      }
    },
    {
      "name": "refs/heads/feature/login",
      "objectId": "123abc456def789abc123def456789abc123def456",
      "creator": {
        "displayName": "Jane Developer",
        "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "uniqueName": "jane@example.com"
      }
    }
  ]
}
```

#### Example: List all tags

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/refs?filter=tags&api-version=7.1"
```

#### Example: List feature branches

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/refs?filter=heads/feature/&api-version=7.1"
```

#### Example: List branches with commit statuses

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/refs?filter=heads&includeStatuses=true&latestStatusesOnly=true&api-version=7.1"
```

### Common Pitfalls

1. **Filter is "starts with"** — The `filter` parameter does prefix matching, not contains. Use `filter=heads` for all branches, `filter=heads/feature` for feature branches.
2. **Ref names include full path** — Branch names are `refs/heads/main`, not just `main`. Strip `refs/heads/` prefix if you need the short name.
3. **`filter=heads` not `filter=heads/`** — Both work, but `heads` returns all branches while `heads/` is equivalent. The trailing slash is optional.
4. **Max 1000 refs per page** — `$top` is capped at 1000. Use `continuationToken` for repos with more refs.
5. **Tags vs. branches** — Use `filter=heads` for branches and `filter=tags` for git tags. Without a filter, you get everything.
6. **`includeMyBranches` conflicts with `filter`** — Cannot combine `includeMyBranches=true` with the `filter` parameter.
7. **Unborn branches** — If `objectId` is `null`, the ref exists but has no commits yet.
