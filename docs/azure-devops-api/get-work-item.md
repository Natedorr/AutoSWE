# Get Work Item

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work%20items/get%20work%20item

---

## Get Work Item

```
GET /{organization}/{project}/_apis/wit/workitems/{id}?api-version=7.1
```

Retrieve a single work item by ID, including its fields, relations, and metadata.

### Parameters

#### Path Parameters

- **`organization`** (string) (required)
  Your Azure DevOps organization name.

- **`project`** (string) (required)
  The project name or ID. URL-encode special characters (e.g., spaces → `%20`).

- **`id`** (integer) (required)
  The work item ID.

#### Query Parameters

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable as of 2025.

- **`$expand`** (string) (optional)
  Expand related data. Values: `all`, `relations`, `fields`. Use `all` to include everything.

- **`$fields`** (string) (optional)
  Comma-separated list of specific fields to return. Example: `System.Title,System.State,System.Description`

- **`asOf`** (string) (optional)
  ISO 8601 datetime to get a historical snapshot of the work item. Example: `2024-01-15T10:30:00Z`

- **`revision`** (integer) (optional)
  Get a specific revision of the work item. Use with the revisions API to find revision numbers.

#### Headers

- **`Authorization`** (string)
  Basic authentication with PAT. Format: `Basic base64(:YOUR_PAT)`

### Response Structure

The response includes:

```json
{
  "id": 123,
  "rev": 5,
  "fields": {
    "System.Id": 123,
    "System.Rev": 5,
    "System.Title": "Fix login bug",
    "System.Description": "Users cannot log in with SSO",
    "System.State": "Active",
    "System.WorkItemType": "Bug",
    "System.AssignedTo": {
      "displayName": "John Doe",
      "id": "user-guid-here",
      "uniqueName": "john.doe@example.com"
    },
    "System.CreatedBy": {
      "displayName": "Jane Smith",
      "id": "another-guid",
      "uniqueName": "jane.smith@example.com"
    },
    "System.CreatedDate": "2024-01-15T10:30:00Z",
    "System.ChangedDate": "2024-01-16T14:20:00Z",
    "System.Tags": "bug; security",
    "System.IterationPath": "MyProject/Sprint 5",
    "System.AreaPath": "MyProject",
    "System.Priority": 1
  },
  "relations": [
    {
      "rel": "Child",
      "url": "https://dev.azure.com/myorg/{project-guid}/_apis/wit/workItems/456",
      "attributes": {
        "comment": "Related task"
      }
    },
    {
      "rel": "Hyperlink",
      "url": "https://github.com/example/repo/pull/123",
      "attributes": {}
    }
  ],
  "_links": {
    "self": {
      "href": "https://dev.azure.com/myorg/{project-guid}/_apis/wit/workItems/123"
    },
    "workItemUpdates": {
      "href": "https://dev.azure.com/myorg/{project-guid}/_apis/wit/workItems/123/updates"
    },
    "workItemRevisions": {
      "href": "https://dev.azure.com/myorg/{project-guid}/_apis/wit/workItems/123/revs"
    }
  }
}
```

### Key Response Fields

| Field | Description |
|---|---|
| `id` | Work item ID |
| `rev` | Current revision number (increments on every change) |
| `fields` | Object containing all work item field values |
| `relations` | Array of relationships (parent/child, hyperlinks, attachments, etc.) |
| `_links` | HATEOAS links to related endpoints |

### Code Examples

#### Get Work Item with All Fields

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1&\$expand=all"
```

#### Get Specific Fields Only

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1&\$fields=System.Title,System.State,System.AssignedTo"
```

#### Get Historical Snapshot

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1&asOf=2024-01-15T10:30:00Z"
```

#### Get Specific Revision

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1&revision=3"
```

#### Get Work Item from Project with Spaces

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/My%20Project/_apis/wit/workitems/123?api-version=7.1"
```

### HTTP Response Status Codes

- **200** — OK, work item found
- **400** — Bad Request (invalid parameters)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item read scope)
- **404** — Not Found (work item ID doesn't exist or wrong project)

### Code Examples — Python

```python
import requests

def get_work_item(org, project, work_item_id, pat, expand="all"):
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}"
    params = {"api-version": "7.1", "$expand": expand}
    response = requests.get(url, auth=("", pat), params=params)
    response.raise_for_status()
    return response.json()

# Usage
wi = get_work_item("myorg", "myproject", 123, "YOUR_PAT")
print(wi["fields"]["System.Title"])
```

### Code Examples — JavaScript/Node.js

```javascript
const axios = require('axios');

async function getWorkItem(org, project, workItemId, pat) {
  const url = `https://dev.azure.com/${org}/${project}/_apis/wit/workitems/${workItemId}`;
  const response = await axios.get(url, {
    params: { 'api-version': '7.1', '$expand': 'all' },
    auth: { username: '', password: pat },
  });
  return response.data;
}

// Usage
const wi = await getWorkItem('myorg', 'myproject', 123, process.env.ADO_PAT);
console.log(wi.fields['System.Title']);
```

### Common Pitfalls

1. **Project URL encoding** — Project names with spaces must be encoded: `My Project` → `My%20Project`.
2. **`api-version` required** — Every request needs `?api-version=7.1` or you'll get an error.
3. **Fields are a flat object** — `fields` is a key-value object, not nested. Access as `fields["System.Title"]`, not `fields.System.Title` (though both work in JS).
4. **Relations array** — Use `$expand=all` to include relations. Without it, relations may not be populated.
5. **Historical snapshots** — `asOf` gives you the work item state at a point in time. Useful for auditing.
