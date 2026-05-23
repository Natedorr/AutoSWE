# Create Work Item

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work%20items/create

---

## Create Work Item

```
POST /{organization}/{project}/_apis/wit/workitems/{type}?api-version=7.1
```

Create a new work item in the specified project. The `{type}` parameter determines the work item type (Bug, User Story, Task, Feature, etc.).

**CRITICAL:** This endpoint uses **RFC 6902 JSON Patch format**, NOT a regular JSON body. The request body is an array of patch operations.

### Parameters

#### Path Parameters

- **`organization`** (string) (required)
  Your Azure DevOps organization name.

- **`project`** (string) (required)
  The project name or ID. URL-encode special characters.

- **`type`** (string) (required)
  The work item type. Common types: `Bug`, `User Story`, `Task`, `Feature`, `Epic`, `Issue`. URL-encode spaces (e.g., `User%20Story`).

#### Query Parameters

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`bypassRules`** (boolean) (optional)
  Set to `true` to bypass validation rules. Use cautiously — can create invalid work items.

- **`bypassPolicy`** (boolean) (optional)
  Set to `true` to bypass policy checks. Use cautiously.

#### Headers

| Header | Value |
|---|---|
| `Authorization` | `Basic base64(:YOUR_PAT)` |
| `Content-Type` | `application/json-patch+json` |

**⚠️ `Content-Type` must be `application/json-patch+json`. Using `application/json` will cause errors.**

### Request Body — JSON Patch Array

```json
[
  {
    "op": "add",
    "path": "/fields/System.Title",
    "value": "Fix login bug"
  },
  {
    "op": "add",
    "path": "/fields/System.Description",
    "value": "Users cannot log in with SSO. This affects all SSO-enabled accounts."
  },
  {
    "op": "add",
    "path": "/fields/System.Tags",
    "value": "bug; security"
  }
]
```

### Key Fields

| Field Path | Type | Required | Description |
|---|---|---|---|
| `/fields/System.Title` | string | Usually | Title of the work item |
| `/fields/System.Description` | string | No | Description/body (supports HTML in some configurations) |
| `/fields/System.State` | string | No | Initial state: `New`, `Active`, `Resolved`, `Closed` |
| `/fields/System.AssignedTo` | string | No | Assignee email or display name |
| `/fields/System.Tags` | string | No | Semicolon-separated: `"tag1; tag2"` |
| `/fields/System.IterationPath` | string | No | Sprint/iteration path |
| `/fields/System.AreaPath` | string | No | Area path |
| `/fields/System.Priority` | integer | No | Priority number (1–4, lower = higher priority) |
| `/fields/System.IterationId` | integer | No | Iteration ID (alternative to IterationPath) |
| `/fields/Microsoft.VSTS.Scheduling.StoryPoints` | number | No | Story points |
| `/fields/System.HierarchyParent` | integer | No | Parent work item ID (creates parent-child relationship) |

### Code Examples

#### Create a Bug

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/Bug?api-version=7.1" \
  -d '[
    {
      "op": "add",
      "path": "/fields/System.Title",
      "value": "Fix login bug"
    },
    {
      "op": "add",
      "path": "/fields/System.Description",
      "value": "Users cannot log in with SSO"
    },
    {
      "op": "add",
      "path": "/fields/System.Tags",
      "value": "bug; security"
    },
    {
      "op": "add",
      "path": "/fields/System.AssignedTo",
      "value": "john.doe@example.com"
    },
    {
      "op": "add",
      "path": "/fields/System.Priority",
      "value": 1
    }
  ]'
```

#### Create a User Story

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/User%20Story?api-version=7.1" \
  -d '[
    {
      "op": "add",
      "path": "/fields/System.Title",
      "value": "Add user profile page"
    },
    {
      "op": "add",
      "path": "/fields/System.Description",
      "value": "As a user, I want to view my profile so I can see my information."
    },
    {
      "op": "add",
      "path": "/fields/Microsoft.VSTS.Scheduling.StoryPoints",
      "value": 3
    },
    {
      "op": "add",
      "path": "/fields/System.IterationPath",
      "value": "MyProject/Sprint 5"
    }
  ]'
```

#### Create a Child Work Item (Linked to Parent)

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/Task?api-version=7.1" \
  -d '[
    {
      "op": "add",
      "path": "/fields/System.Title",
      "value": "Implement backend API for profile"
    },
    {
      "op": "add",
      "path": "/fields/System.HierarchyParent",
      "value": 123
    }
  ]'
```

### Response

Returns **200** (not 201) with the created work item:

```json
{
  "id": 456,
  "rev": 1,
  "fields": {
    "System.Id": 456,
    "System.Rev": 1,
    "System.Title": "Fix login bug",
    "System.Description": "Users cannot log in with SSO",
    "System.State": "New",
    "System.WorkItemType": "Bug",
    "System.AssignedTo": {
      "displayName": "John Doe",
      "id": "user-guid-here"
    },
    "System.Tags": "bug; security",
    "System.CreatedBy": {
      "displayName": "API User",
      "id": "api-user-guid"
    },
    "System.CreatedDate": "2024-01-15T10:30:00Z",
    "System.ChangedDate": "2024-01-15T10:30:00Z"
  },
  "relations": [],
  "_links": {
    "self": {
      "href": "https://dev.azure.com/myorg/{project-guid}/_apis/wit/workItems/456"
    },
    "workItemUpdates": {
      "href": "https://dev.azure.com/myorg/{project-guid}/_apis/wit/workItems/456/updates"
    }
  }
}
```

### HTTP Response Status Codes

- **200** — OK, work item created successfully (note: POST returns 200, not 201)
- **400** — Bad Request (invalid field, invalid JSON Patch format, or validation error)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item write scope)
- **404** — Not Found (project or work item type doesn't exist)
- **409** — Conflict (policy violation or validation rule conflict)

### Code Examples — Python

```python
import requests

def create_work_item(org, project, work_item_type, fields, pat):
    """
    Create a work item.
    
    :param org: Azure DevOps organization name
    :param project: Project name
    :param work_item_type: Work item type (e.g., 'Bug', 'Task')
    :param fields: Dict of field ref names to values
    :param pat: Personal Access Token
    :return: Created work item dict
    """
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_type}"
    
    # Convert dict to JSON Patch format
    patches = [
        {"op": "add", "path": f"/fields/{field}", "value": value}
        for field, value in fields.items()
    ]
    
    response = requests.post(
        url,
        auth=("", pat),
        params={"api-version": "7.1"},
        headers={"Content-Type": "application/json-patch+json"},
        json=patches
    )
    response.raise_for_status()
    return response.json()

# Usage
result = create_work_item(
    "myorg",
    "myproject",
    "Bug",
    {
        "System.Title": "Fix login bug",
        "System.Description": "Users cannot log in with SSO",
        "System.Tags": "bug; security",
        "System.AssignedTo": "john.doe@example.com",
    },
    "YOUR_PAT"
)
print(f"Created work item #{result['id']}")
```

### Code Examples — JavaScript/Node.js

```javascript
const axios = require('axios');

async function createWorkItem(org, project, type, fields, pat) {
  const url = `https://dev.azure.com/${org}/${project}/_apis/wit/workitems/${type}`;
  
  // Convert fields to JSON Patch format
  const patches = Object.entries(fields).map(([field, value]) => ({
    op: 'add',
    path: `/fields/${field}`,
    value,
  }));

  const response = await axios.post(url, patches, {
    params: { 'api-version': '7.1' },
    auth: { username: '', password: pat },
    headers: { 'Content-Type': 'application/json-patch+json' },
  });
  
  return response.data;
}

// Usage
const result = await createWorkItem('myorg', 'myproject', 'Bug', {
  'System.Title': 'Fix login bug',
  'System.Description': 'Users cannot log in with SSO',
  'System.Tags': 'bug; security',
}, process.env.ADO_PAT);

console.log(`Created work item #${result.id}`);
```

### Common Pitfalls

1. **JSON Patch format** — The body MUST be a JSON Patch array, NOT a plain JSON object. Each operation is `{"op": "add", "path": "/fields/...", "value": "..."}`.
2. **Content-Type header** — Must be `application/json-patch+json`, NOT `application/json`. This is the #1 cause of errors.
3. **POST returns 200** — Creating work items returns HTTP 200, not 201. Don't treat 200 as an error.
4. **Work item type in URL** — The type is part of the path: `/_apis/wit/workitems/Bug`, not a query parameter.
5. **Tags format** — Tags are semicolon-separated strings: `"bug; security"`, NOT a JSON array.
6. **AssignedTo format** — Use email address OR display name. Not a user ID.
7. **Field paths** — Always start with `/fields/` followed by the field reference name (e.g., `/fields/System.Title`).
8. **URL-encode the type** — "User Story" must be `User%20Story` in the URL.
