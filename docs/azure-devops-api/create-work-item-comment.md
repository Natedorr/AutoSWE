# Create Work Item Comment

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/comments/create%20comment

---

## Create Work Item Comment

```
POST /{organization}/{project}/_apis/wit/workitems/{id}/comments?api-version=7.1
```

Add a comment to an existing work item. Supports markdown formatting.

### Parameters

#### Path Parameters

- **`organization`** (string) (required)
  Your Azure DevOps organization name.

- **`project`** (string) (required)
  The project name or ID. URL-encode special characters.

- **`id`** (integer) (required)
  The work item ID to comment on.

#### Query Parameters

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

#### Headers

| Header | Value |
|---|---|
| `Authorization` | `Basic base64(:YOUR_PAT)` |
| `Content-Type` | `application/json` |

### Request Body

```json
{
  "text": "This is a comment. **Markdown** is *supported*."
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | Yes | Comment text in markdown format |

### Code Examples

#### Create a Comment

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123/comments?api-version=7.1" \
  -d '{
    "text": "Investigated the root cause. The issue is in the authentication middleware."
  }'
```

#### Create a Comment with Markdown Formatting

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123/comments?api-version=7.1" \
  -d '{
    "text": "## Update\n\nFixed the issue in commit `abc123`.\n\n- Changed auth middleware\n- Added error logging\n- Updated tests"
  }'
```

#### Create a Comment with Python

```python
import requests

def add_comment(org, project, work_item_id, text, pat):
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}/comments"
    response = requests.post(
        url,
        auth=("", pat),
        params={"api-version": "7.1"},
        headers={"Content-Type": "application/json"},
        json={"text": text}
    )
    response.raise_for_status()
    return response.json()

# Usage
result = add_comment("myorg", "myproject", 123, "Bug fixed in PR #456.", "YOUR_PAT")
print(f"Comment created: {result['id']}")
```

#### Create a Comment with JavaScript

```javascript
const axios = require('axios');

async function addComment(org, project, workItemId, text, pat) {
  const url = `https://dev.azure.com/${org}/${project}/_apis/wit/workitems/${workItemId}/comments`;
  const response = await axios.post(url, { text }, {
    params: { 'api-version': '7.1' },
    auth: { username: '', password: pat },
    headers: { 'Content-Type': 'application/json' },
  });
  return response.data;
}

// Usage
const result = await addComment('myorg', 'myproject', 123, 'Bug fixed in PR #456.', process.env.ADO_PAT);
console.log(`Comment created: ${result.id}`);
```

### Response

Returns **200** with the created comment:

```json
{
  "id": 3,
  "text": "Investigated the root cause. The issue is in the authentication middleware.",
  "html": "<p>Investigated the root cause. The issue is in the authentication middleware.</p>",
  "createdBy": {
    "displayName": "API User",
    "id": "api-user-guid",
    "uniqueName": "api@example.com"
  },
  "createdDate": "2024-01-17T09:00:00Z",
  "changedDate": "2024-01-17T09:00:00Z"
}
```

### HTTP Response Status Codes

- **200** — OK, comment created (note: POST returns 200, not 201)
- **400** — Bad Request (empty text or invalid format)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item write scope)
- **404** — Not Found (work item doesn't exist)

### Common Pitfalls

1. **Content-Type is `application/json`** — Unlike create/update work item which use `application/json-patch+json`, comments use standard `application/json`.
2. **POST returns 200** — Creating comments returns 200, not 201.
3. **Markdown supported** — The `text` field supports markdown. It gets rendered to HTML in the UI.
4. **Simple body** — Just `{"text": "..."}`, no additional metadata needed.
5. **Notifications** — Comments trigger email notifications to watchers by default.
