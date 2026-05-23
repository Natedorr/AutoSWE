# List Work Item Comments

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/comments/get%20comments

---

## List Work Item Comments

```
GET /{organization}/{project}/_apis/wit/workitems/{id}/comments?api-version=7.1
```

Retrieve all comments on a work item. Returns comment text, author information, and timestamps.

### Parameters

#### Path Parameters

- **`organization`** (string) (required)
  Your Azure DevOps organization name.

- **`project`** (string) (required)
  The project name or ID. URL-encode special characters.

- **`id`** (integer) (required)
  The work item ID.

#### Query Parameters

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

#### Headers

- **`Authorization`** (string)
  Basic authentication with PAT. Format: `Basic base64(:YOUR_PAT)`

### Response

```json
{
  "comments": [
    {
      "id": 1,
      "text": "This is the first comment. **Markdown** is *supported*.",
      "html": "<p>This is the first comment. <strong>Markdown</strong> is <em>supported</em>.</p>",
      "createdBy": {
        "displayName": "John Doe",
        "id": "user-guid-here",
        "uniqueName": "john.doe@example.com"
      },
      "createdDate": "2024-01-15T10:30:00Z",
      "changedDate": "2024-01-15T10:30:00Z"
    },
    {
      "id": 2,
      "text": "Updated the fix. Can you verify?",
      "html": "<p>Updated the fix. Can you verify?</p>",
      "createdBy": {
        "displayName": "Jane Smith",
        "id": "another-guid",
        "uniqueName": "jane.smith@example.com"
      },
      "createdDate": "2024-01-16T14:20:00Z",
      "changedDate": "2024-01-16T14:20:00Z"
    }
  ],
  "totalCount": 2
}
```

### Key Response Fields

| Field | Description |
|---|---|
| `comments` | Array of comment objects |
| `comments[].id` | Comment ID |
| `comments[].text` | Raw comment text (markdown) |
| `comments[].html` | Rendered HTML version of the comment |
| `comments[].createdBy` | Author object with displayName, id, uniqueName |
| `comments[].createdDate` | ISO 8601 creation timestamp |
| `comments[].changedDate` | ISO 8601 last modification timestamp |
| `totalCount` | Total number of comments |

### Code Examples

#### List All Comments

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123/comments?api-version=7.1"
```

#### List Comments with Python

```python
import requests

def get_comments(org, project, work_item_id, pat):
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}/comments"
    response = requests.get(
        url,
        auth=("", pat),
        params={"api-version": "7.1"}
    )
    response.raise_for_status()
    data = response.json()
    for comment in data.get("comments", []):
        print(f"[{comment['createdDate']}] {comment['createdBy']['displayName']}:")
        print(f"  {comment['text']}")
        print()
    return data

# Usage
get_comments("myorg", "myproject", 123, "YOUR_PAT")
```

#### List Comments with JavaScript

```javascript
const axios = require('axios');

async function getComments(org, project, workItemId, pat) {
  const url = `https://dev.azure.com/${org}/${project}/_apis/wit/workitems/${workItemId}/comments`;
  const response = await axios.get(url, {
    params: { 'api-version': '7.1' },
    auth: { username: '', password: pat },
  });
  
  const comments = response.data.comments || [];
  comments.forEach(c => {
    console.log(`[${c.createdDate}] ${c.createdBy.displayName}:`);
    console.log(`  ${c.text}`);
    console.log();
  });
  
  return response.data;
}

// Usage
getComments('myorg', 'myproject', 123, process.env.ADO_PAT);
```

### HTTP Response Status Codes

- **200** — OK, comments retrieved
- **400** — Bad Request (invalid parameters)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item read scope)
- **404** — Not Found (work item doesn't exist)

### Common Pitfalls

1. **Comments may be empty** — If a work item has no comments, `comments` returns an empty array and `totalCount` is 0.
2. **Text vs HTML** — The `text` field is markdown, the `html` field is rendered. Use `text` for API manipulation, `html` for display.
3. **Comments are chronological** — Comments are returned in order of creation (oldest first).
4. **No pagination** — This endpoint returns all comments in a single response. No continuation tokens.
