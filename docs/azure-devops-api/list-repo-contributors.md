# List Repo Contributors

> Grounding reference for Azure DevOps Git API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/contributors/list

---

## List Repository Contributors

```
GET /{organization}/{project}/_apis/git/repositories/{repositoryId}/contributors?api-version=7.1
```

List users who have access to a repository. Returns identity objects for each contributor.

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

- **`$top`** (integer) (optional)
  Maximum number of contributors to return.
  Default: `100`

- **`continuationToken`** (string) (optional)
  Token for retrieving the next page of results.

### HTTP response status codes

- **200** — OK. Returns a paged result with `count` and `value` array of contributor objects.
- **401** — Unauthorized. Invalid or missing PAT.
- **403** — Forbidden. PAT lacks required scope or project access.
- **404** — Not Found. Organization, project, or repository not found.

### Response schema (Status: 200)

- `count`: required, integer — Number of contributors in the `value` array.
- `value`: required, array of identity objects:
  - `displayName`: string — User's display name.
  - `id`: required, string — User's identity GUID.
  - `uniqueName`: string — User's unique name (email).
  - `url`: string — REST API URL for this identity.
  - `imageUrl`: string — URL to the user's avatar image.
  - `descriptor`: string — User's identity descriptor.
  - `faces`: array — Avatar images at different sizes.
  - `_links`: object — Reference links.

### Code examples

#### Example: List all contributors to a repository

**Request:**

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/contributors?api-version=7.1"
```

**Response (Status: 200):**

```json
{
  "count": 3,
  "value": [
    {
      "displayName": "Jane Developer",
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "uniqueName": "jane@example.com",
      "url": "https://sps.prodbigpipe.cloudapp.net/3b3ae425-0079-421f-9101-bcf15d6df041/_apis/Identities/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "imageUrl": "https://dev.azure.com/myorg/_api/_common/identityImage?id=a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "descriptor": "aad.YmFjMGYyZDctNDA3ZC03OGRhLTlhMjUtNmJhZjUwMWFjY2U5"
    },
    {
      "displayName": "John Coder",
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "uniqueName": "john@example.com",
      "url": "https://sps.prodbigpipe.cloudapp.net/3b3ae425-0079-421f-9101-bcf15d6df041/_apis/Identities/b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "imageUrl": "https://dev.azure.com/myorg/_api/_common/identityImage?id=b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "descriptor": "aad.ZGNmYzIzZDgtNDA4ZC04OGRhLTlhMzYtN2NiZjYxMmJkZGY2"
    }
  ]
}
```

#### Example: Get first page of contributors

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/contributors?api-version=7.1&$top=25"
```

### Common Pitfalls

1. **Contributors vs. permissions** — This endpoint returns everyone who has been granted any access to the repo, not just active contributors. Service accounts and inherited permissions are included.
2. **Pagination** — For repos with many contributors, use `continuationToken` to get all results.
3. **Identity GUIDs** — The `id` field is an identity GUID, which may differ from the profile GUID used in the Profile API. Use the Graph API to resolve between them if needed.
4. **Scope matters** — This is scoped to a specific repository, not the project or organization.
5. **Use repository name or GUID** — You can use either the repository name or its GUID for `{repositoryId}`.
