# List Commits

> Grounding reference for Azure DevOps Git API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/commits/list

---

## List Commits

```
GET /{organization}/{project}/_apis/git/repositories/{repositoryId}/commits?api-version=7.1
```

Get a list of commits for a repository. Supports filtering by branch, path, date range, and commit search.

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

- **`searchCriteria.itemPath`** (string) (optional)
  Restrict results to commits that affected this path.

- **`searchCriteria.version`** (string) (optional)
  Name of the branch, tag, or commit SHA to search from.

- **`searchCriteria.versionOptions`** (string) (optional)
  Additional modifiers. Values: `none`, `excludeHiddenItems`, `followRenames`, `skipRenames`.
  Default: `none`

- **`searchCriteria.versionType`** (string) (optional)
  Type of version. Values: `branch`, `tag`, `commit`, `changeset`.
  Default: `branch`

- **`searchCriteria.includeParents`** (boolean) (optional)
  If true, includes the parent commits.
  Default: `false`

- **`searchCriteria.includeLinks`** (boolean) (optional)
  If true, includes links in the response.
  Default: `false`

- **`searchCriteria.includeStats`** (boolean) (optional)
  If true, includes insert/delete statistics per commit.
  Default: `false`

- **`searchCriteria.includeWorkItems`** (boolean) (optional)
  If true, references to related work items from the commit message.
  Default: `false`

- **`searchCriteria.searchText`** (string) (optional)
  Search for commits containing this text in commit messages.

- **`searchCriteria.author`** (string) (optional)
  Filter by author (email or display name).

- **`searchCriteria.fromDate`** (string, date-time) (optional)
  Get commits made after this date.

- **`searchCriteria.toDate`** (string, date-time) (optional)
  Get commits made before this date.

- **`$top`** (integer) (optional)
  Maximum number of commits to return.
  Default: `100`
  Maximum: `200`

- **`continuationToken`** (string) (optional)
  Token for retrieving the next page of results.

### HTTP response status codes

- **200** — OK. Returns a paged result with `count` and `value` array of commit objects.
- **401** — Unauthorized. Invalid or missing PAT.
- **403** — Forbidden. PAT lacks required scope or repo access.
- **404** — Not Found. Organization, project, or repository not found.

### Response schema (Status: 200)

- `count`: required, integer — Number of commits in the `value` array.
- `value`: required, array of GitCommit objects:
  - `commitId`: required, string — SHA-1 commit ID.
  - `author`: object — Commit author:
    - `name`: string — Author's name.
    - `email`: string — Author's email.
    - `date`: string, format: date-time — When the commit was authored.
  - `committer`: object — Commit committer (same structure as author).
  - `comment`: string — Commit message.
  - `commentTruncated`: boolean — Whether the comment was truncated.
  - `url`: string — REST API URL for this commit.
  - `parents`: array — Array of parent commit SHA-1 IDs.
  - `changes`: array — Changes in this commit (when requested):
    - `changeType`: string — `add`, `edit`, `delete`, `rename`.
    - `item`: object — File path and details.
  - `stats`: object — Insert/delete stats (when `includeStats=true`):
    - `totalInsertions`: integer
    - `totalDeletions`: integer
    - `filesWithInsertions`: integer
    - `filesWithDeletions`: integer
  - `associatedWorkItems`: array — Related work items (when `includeWorkItems=true`).

### Code examples

#### Example: List latest commits on main branch

**Request:**

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/commits?searchCriteria.version=refs/heads/main&$top=10&api-version=7.1"
```

**Response (Status: 200):**

```json
{
  "count": 3,
  "value": [
    {
      "commitId": "d7f4a1b2c3e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
      "author": {
        "name": "Jane Developer",
        "email": "jane@example.com",
        "date": "2025-01-15T14:30:00.000Z"
      },
      "committer": {
        "name": "Jane Developer",
        "email": "jane@example.com",
        "date": "2025-01-15T14:30:00.000Z"
      },
      "comment": "Fix login validation bug",
      "commentTruncated": false,
      "url": "https://dev.azure.com/myorg/_apis/git/repositories/my-repo/commits/d7f4a1b2c3e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9",
      "parents": ["abc123def456789abc123def456789abc123def456"]
    },
    {
      "commitId": "abc123def456789abc123def456789abc123def456",
      "author": {
        "name": "John Coder",
        "email": "john@example.com",
        "date": "2025-01-14T10:00:00.000Z"
      },
      "committer": {
        "name": "John Coder",
        "email": "john@example.com",
        "date": "2025-01-14T10:00:00.000Z"
      },
      "comment": "Add user profile endpoint",
      "commentTruncated": false,
      "url": "https://dev.azure.com/myorg/_apis/git/repositories/my-repo/commits/abc123def456789abc123def456789abc123def456",
      "parents": ["123abc456def789abc123def456789abc123def456"]
    }
  ]
}
```

#### Example: List commits that changed a specific file

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/commits?searchCriteria.itemPath=src/index.ts&searchCriteria.version=refs/heads/main&$top=5&api-version=7.1"
```

#### Example: Search commits by author and date range

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/commits?searchCriteria.author=jane@example.com&searchCriteria.fromDate=2025-01-01T00:00:00Z&searchCriteria.toDate=2025-01-31T23:59:59Z&api-version=7.1"
```

#### Example: Get commits with stats and work item references

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/commits?searchCriteria.version=refs/heads/main&searchCriteria.includeStats=true&searchCriteria.includeWorkItems=true&$top=25&api-version=7.1"
```

### Common Pitfalls

1. **`searchCriteria.version` uses full ref name** — Use `refs/heads/main`, not just `main`. Without this parameter, results default to the repository's default branch.
2. **Max 200 per page** — `$top` is capped at 200. Use `continuationToken` for pagination beyond that.
3. **Date format** — Use ISO 8601 format for `fromDate`/`toDate`: `2025-01-15T14:30:00.000Z`.
4. **Version type defaults to branch** — If you specify a commit SHA in `version`, also set `versionType=commit`, otherwise it may not resolve correctly.
5. **Comment truncation** — Very long commit messages may be truncated. Check `commentTruncated` flag.
6. **Changes not included by default** — File changes per commit require specific inclusion. Use `includeChanges=true` if available, or get a single commit to see its changes.
