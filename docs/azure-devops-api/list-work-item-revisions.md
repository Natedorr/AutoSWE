# List Work Item Revisions

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/revisions

---

## List Work Item Revisions

```
GET /{organization}/{project}/_apis/wit/workitems/{id}/revs?api-version=7.1
```

Retrieve the revision history of a work item. Every field change creates a new revision, providing a complete audit trail.

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
  "count": 5,
  "value": [
    {
      "id": 1,
      "fields": {
        "System.Id": 123,
        "System.Title": "Fix login bug",
        "System.State": "New",
        "System.WorkItemType": "Bug"
      },
      "fieldsAdded": {},
      "fieldsRemoved": {},
      "fieldsChanged": {},
      "createdBy": {
        "displayName": "John Doe",
        "id": "user-guid-here",
        "uniqueName": "john.doe@example.com"
      },
      "createdDate": "2024-01-15T10:30:00Z"
    },
    {
      "id": 2,
      "fields": {
        "System.Id": 123,
        "System.Title": "Fix login bug",
        "System.State": "Active",
        "System.AssignedTo": {
          "displayName": "Jane Smith",
          "id": "another-guid"
        }
      },
      "fieldsAdded": {
        "System.AssignedTo": {
          "displayName": "Jane Smith",
          "id": "another-guid"
        }
      },
      "fieldsRemoved": {},
      "fieldsChanged": {
        "System.State": {
          "oldValue": "New",
          "newValue": "Active"
        }
      },
      "createdBy": {
        "displayName": "John Doe",
        "id": "user-guid-here"
      },
      "createdDate": "2024-01-15T11:00:00Z"
    },
    {
      "id": 3,
      "fields": {
        "System.Id": 123,
        "System.Title": "Fix login bug — critical path",
        "System.State": "Active",
        "System.Tags": "bug; security"
      },
      "fieldsAdded": {
        "System.Tags": "bug; security"
      },
      "fieldsRemoved": {},
      "fieldsChanged": {
        "System.Title": {
          "oldValue": "Fix login bug",
          "newValue": "Fix login bug — critical path"
        }
      },
      "createdBy": {
        "displayName": "Jane Smith",
        "id": "another-guid"
      },
      "createdDate": "2024-01-16T14:20:00Z"
    }
  ]
}
```

### Key Response Fields

| Field | Description |
|---|---|
| `count` | Total number of revisions |
| `value` | Array of revision objects |
| `value[].id` | Revision number (sequential, starts at 1) |
| `value[].fields` | Complete field snapshot at this revision |
| `value[].fieldsAdded` | Fields that were added in this revision |
| `value[].fieldsRemoved` | Fields that were removed in this revision |
| `value[].fieldsChanged` | Fields that changed, with `oldValue` and `newValue` |
| `value[].createdBy` | Who made this change |
| `value[].createdDate` | When this revision was created (ISO 8601) |

### Code Examples

#### List All Revisions

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123/revs?api-version=7.1"
```

#### Get a Specific Revision

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1&revision=2"
```

#### List Revisions with Python

```python
import requests
from datetime import datetime

def get_revisions(org, project, work_item_id, pat):
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}/revs"
    response = requests.get(
        url,
        auth=("", pat),
        params={"api-version": "7.1"}
    )
    response.raise_for_status()
    return response.json()

def print_revision_history(revisions):
    for rev in revisions.get("value", []):
        dt = datetime.fromisoformat(rev["createdDate"].replace("Z", "+00:00"))
        author = rev["createdBy"]["displayName"]
        print(f"Revision {rev['id']} — {dt.strftime('%Y-%m-%d %H:%M')} by {author}")
        
        # Show changes
        changed = rev.get("fieldsChanged", {})
        for field, change in changed.items():
            print(f"  {field}: {change['oldValue']} → {change['newValue']}")
        
        added = rev.get("fieldsAdded", {})
        for field, value in added.items():
            print(f"  {field}: added → {value}")
        
        removed = rev.get("fieldsRemoved", {})
        for field, value in removed.items():
            print(f"  {field}: {value} → removed")
        
        print()

# Usage
revisions = get_revisions("myorg", "myproject", 123, "YOUR_PAT")
print_revision_history(revisions)
```

#### List Revisions with JavaScript

```javascript
const axios = require('axios');

async function getRevisions(org, project, workItemId, pat) {
  const url = `https://dev.azure.com/${org}/${project}/_apis/wit/workitems/${workItemId}/revs`;
  const response = await axios.get(url, {
    params: { 'api-version': '7.1' },
    auth: { username: '', password: pat },
  });
  
  const revisions = response.data.value || [];
  revisions.forEach(rev => {
    console.log(`Revision ${rev.id} — ${rev.createdDate} by ${rev.createdBy.displayName}`);
    
    const changed = rev.fieldsChanged || {};
    Object.entries(changed).forEach(([field, change]) => {
      console.log(`  ${field}: ${change.oldValue} → ${change.newValue}`);
    });
    
    console.log();
  });
  
  return response.data;
}

// Usage
getRevisions('myorg', 'myproject', 123, process.env.ADO_PAT);
```

### HTTP Response Status Codes

- **200** — OK, revisions retrieved
- **400** — Bad Request (invalid parameters)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item read scope)
- **404** — Not Found (work item doesn't exist)

### Common Pitfalls

1. **Every change is a revision** — Even small changes (like adding a tag) create a new revision. High-activity work items can have many revisions.
2. **`fields` is the full snapshot** — Each revision contains the complete field state, not just the delta. Use `fieldsChanged` for diffs.
3. **Revisions are sequential** — Start at 1 and increment. The current revision number is in the work item's `rev` field.
4. **`asOf` parameter** — You can get a work item at a point in time using the `asOf` query param on the get work item endpoint.
5. **Revisions include comments** — Adding comments also creates revisions, so revision count may be higher than field changes alone.
