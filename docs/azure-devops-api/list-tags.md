# List Tags

> Grounding reference for Azure DevOps Work Item Tracking API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/tags/list

---

## List Tags

```
GET /{organization}/{project}/_apis/wit/tags?api-version=7.1
```

Get all the tags defined for a project. Tags are the values that can appear in the `System.Tags` field on work items.

### Parameters

#### Headers

- **`Authorization`** (string) (required)
  Basic authentication with a Personal Access Token (PAT). Format: `Basic base64(:YOUR_PAT)`. The username is empty — just a colon followed by your PAT, then base64-encoded.

#### Path and query parameters

- **`organization`** (string) (required)
  Name of your Azure DevOps organization.

- **`project`** (string) (required)
  Project ID or project name.

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`$top`** (integer) (optional)
  Maximum number of tags to return per page.

- **`continuationToken`** (string) (optional)
  Token for retrieving the next page of results. Use the `continuationToken` value from a previous response.

### HTTP response status codes

- **200** — OK. Returns an array of tag definition objects.
- **401** — Unauthorized. Invalid or missing PAT.
- **403** — Forbidden. PAT lacks required scope or project access.
- **404** — Not Found. Organization or project not found.

### Response schema (Status: 200)

Returns an array of `WorkItemTagDefinition` objects:

- `id`: required, string (uuid) — Unique tag ID.
- `name`: required, string — Display name of the tag.
- `url`: string — REST API URL for this tag.
- `lastUpdated`: string, format: date-time — When the tag was last updated.

### Code examples

#### Example: List all tags in a project

**Request:**

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/tags?api-version=7.1"
```

**Response (Status: 200):**

```json
[
  {
    "count": 2,
    "value": [
      {
        "id": "18090594-b371-4140-99d2-fc93bcbcddec",
        "name": "my-first-tag",
        "url": "http://dev.azure.com/myorg/myproject/_apis/wit/tags/18090594-b371-4140-99d2-fc93bcbcddec?api-version=5.1-preview",
        "lastUpdated": "2022-11-01T10:56:26.433Z"
      },
      {
        "id": "e4c198b9-171d-4e99-b163-4e17e659c0a2",
        "name": "my-second-tag",
        "url": "http://dev.azure.com/myorg/myproject/_apis/wit/tags/e4c198b9-171d-4e99-b163-4e17e659c0a2?api-version=5.1-preview",
        "lastUpdated": "2022-11-01T10:56:26.433Z"
      }
    ]
  }
]
```

### Common Pitfalls

1. **Tags are freeform strings** — Users can create any tag value on the fly by setting `System.Tags`. This endpoint returns tags that have been used in the project.
2. **Response format** — The response is wrapped in an array containing a single object with `count` and `value`, not a flat array.
3. **Tag scope** — Tags are scoped to the project, not organization-wide.
4. **Case sensitivity** — Tag names are case-sensitive. "Bug" and "bug" are different tags.
