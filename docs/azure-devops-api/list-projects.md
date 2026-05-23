# List Projects

> Grounding reference for Azure DevOps Core API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/core/projects/list

---

## List Projects

```
GET /{organization}/_apis/projects?api-version=7.1
```

Get all projects in the organization that the authenticated user has access to.

### Parameters

#### Headers

- **`Authorization`** (string) (required)
  Basic authentication with a Personal Access Token (PAT). Format: `Basic base64(:YOUR_PAT)`.

#### Path and query parameters

- **`organization`** (string) (required)
  Name of your Azure DevOps organization.

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`$top`** (integer) (optional)
  Maximum number of projects to return.

- **`$skip`** (integer) (optional)
  Number of projects to skip.

- **`continuationToken`** (integer) (optional)
  Pointer indicating how many projects have already been fetched.

- **`stateFilter`** (string) (optional)
  Filter projects by state. Default: `wellFormed`.
  Values: `wellFormed`, `newPending`, `newInProgress`, `newAborted`, `deletePending`, `deleteInProgress`, `deleteAborted`, `notAuthorized`

- **`getDefaultTeamImageUrl`** (boolean) (optional)
  If true, includes the default team image URL.

### HTTP response status codes

- **200** — OK. Returns a paged result with `count` and `value` array of project objects.
- **401** — Unauthorized. Invalid or missing PAT.
- **403** — Forbidden. PAT lacks required scope.
- **404** — Not Found. Organization not found.

### Response schema (Status: 200)

- `count`: required, integer — Number of projects in the `value` array.
- `value`: required, array of TeamProjectReference objects:
  - `id`: required, string — Project GUID. Use this in other API calls.
  - `name`: required, string — Project name.
  - `description`: string — Project description.
  - `url`: string — REST API URL for this project.
  - `state`: required, string — Project state (e.g., `wellFormed`, `newPending`).
  - `revision`: integer — Project revision number.
  - `visibility`: string — Project visibility (`private`, `public`).
  - `lastUpdateTime`: string, format: date-time — When the project was last updated.
  - `defaultTeamImageUrl`: string — URL of the default team image (when requested).

### Code examples

#### Example: List all projects in an organization

**Request:**

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/_apis/projects?api-version=7.1"
```

**Response (Status: 200):**

```json
{
  "count": 3,
  "value": [
    {
      "id": "eb6e4656-77fc-42a1-9181-4c6d8e9da5d1",
      "name": "myproject-1",
      "description": "Main product project",
      "url": "https://dev.azure.com/myorg/_apis/projects/eb6e4656-77fc-42a1-9181-4c6d8e9da5d1",
      "state": "wellFormed",
      "revision": 411518573
    },
    {
      "id": "6ce954b1-ce1f-45d1-b94d-e6bf2464ba2c",
      "name": "myproject-2",
      "description": "Secondary project",
      "url": "https://dev.azure.com/myorg/_apis/projects/6ce954b1-ce1f-45d1-b94d-e6bf2464ba2c",
      "state": "wellFormed",
      "revision": 293012730
    },
    {
      "id": "281f9a5b-af0d-49b4-a1df-fe6f5e5f84d0",
      "name": "myproject-3",
      "url": "https://dev.azure.com/myorg/_apis/projects/281f9a5b-af0d-49b4-a1df-fe6f5e5f84d0",
      "state": "wellFormed",
      "revision": 100
    }
  ]
}
```

#### Example: List only active (well-formed) projects

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/_apis/projects?stateFilter=wellFormed&api-version=7.1"
```

#### Example: List projects including those being deleted

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/_apis/projects?stateFilter=wellFormed,deletePending&api-version=7.1"
```

### Common Pitfalls

1. **Project GUIDs are needed for most endpoints** — While many endpoints accept project names, the GUID is more reliable. Store the mapping.
2. **URL-encode project names** — If your project name has spaces or special characters, URL-encode them (e.g., `My%20Project`).
3. **Default filter hides deleting projects** — The default `stateFilter=wellFormed` excludes projects being created or deleted. Use a broader filter if needed.
4. **Access control** — You only see projects you have access to. Projects you can't see won't appear in the list, even with a valid PAT.
5. **No organization name needed in path for some endpoints** — Some endpoints use the collection-level URL format. This one requires the organization.
