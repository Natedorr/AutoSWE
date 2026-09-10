# Update Work Item

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/update?view=azure-devops-rest-7.1

---

## Update Work Item

```
PATCH /{organization}/{project}/_apis/wit/workitems/{id}?api-version=7.1
```

Update one or more fields on an existing work item. Uses **RFC 6902 JSON Patch format** — same as the create endpoint.

> **Relations:** `op: add` on `/relations/-` is how you add links (hyperlinks, work-item links) — the same call powers the generic link APIs. Full mechanics (relation `rel` names, reading relations with `$expand=relations`, PR↔work-item links, and why merges don't complete work items) are covered in [workitem-pr-linking-and-builds.md](workitem-pr-linking-and-builds.md).

### Parameters

#### Path Parameters

- **`organization`** (string) (required)
  Your Azure DevOps organization name.

- **`project`** (string) (required)
  The project name or ID. URL-encode special characters.

- **`id`** (integer) (required)
  The work item ID to update.

#### Query Parameters

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`bypassRules`** (boolean) (optional)
  Set to `true` to bypass validation rules. Use cautiously.

- **`bypassPolicy`** (boolean) (optional)
  Set to `true` to bypass policy checks. Use cautiously.

- **`suppressNotifications`** (boolean) (optional)
  Set to `true` to prevent email notifications on update.

#### Headers

| Header | Value |
|---|---|
| `Authorization` | `Basic base64(:YOUR_PAT)` |
| `Content-Type` | `application/json-patch+json` |

### Request Body — JSON Patch Array

```json
[
  {
    "op": "add",
    "path": "/fields/System.Title",
    "value": "Updated title"
  },
  {
    "op": "add",
    "path": "/fields/System.State",
    "value": "Resolved"
  },
  {
    "op": "remove",
    "path": "/fields/System.AssignedTo"
  }
]
```

### JSON Patch Operations

| Operation | Description | Example |
|---|---|---|
| `add` | Set or change a field value | `{"op": "add", "path": "/fields/System.State", "value": "Resolved"}` |
| `remove` | Clear a field value | `{"op": "remove", "path": "/fields/System.AssignedTo"}` |

**Note:** Both setting a new value AND changing an existing value use `"op": "add"`. There's no separate `replace` needed for most work item fields.

**Exception — `System.Tags`:** ADO applies `op: "add"` on `System.Tags`
*additively* (it merges the value into the existing tag set rather than
replacing the field). To truly replace the tag set you must `remove` the field
first, then `add` the new value — see [Replace Tags on Work Item](replace-tags-on-work-item.md).

### Common Update Patterns

#### Change State

```bash
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
  -d '[
    {
      "op": "add",
      "path": "/fields/System.State",
      "value": "Resolved"
    }
  ]'
```

#### Replace Tags (and update title)

`add` on `System.Tags` is additive, so clear the field with `remove` first to
replace the whole tag set (issue #235):

```bash
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
  -d '[
    {
      "op": "add",
      "path": "/fields/System.Title",
      "value": "Fix login bug — critical path"
    },
    {
      "op": "remove",
      "path": "/fields/System.Tags"
    },
    {
      "op": "add",
      "path": "/fields/System.Tags",
      "value": "bug; security; critical"
    }
  ]'
```

#### Assign to User

```bash
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
  -d '[
    {
      "op": "add",
      "path": "/fields/System.AssignedTo",
      "value": "john.doe@example.com"
    }
  ]'
```

#### Unassign

```bash
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
  -d '[
    {
      "op": "remove",
      "path": "/fields/System.AssignedTo"
    }
  ]'
```

#### Close Work Item with Reason

```bash
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
  -d '[
    {
      "op": "add",
      "path": "/fields/System.State",
      "value": "Closed"
    },
    {
      "op": "add",
      "path": "/fields/ResolvedReason",
      "value": "Fixed"
    }
  ]'
```

### Response

Returns the updated work item:

```json
{
  "id": 123,
  "rev": 6,
  "fields": {
    "System.Id": 123,
    "System.Rev": 6,
    "System.Title": "Fix login bug — critical path",
    "System.State": "Resolved",
    "System.ChangedDate": "2024-01-16T14:20:00Z",
    "System.ChangedBy": {
      "displayName": "API User",
      "id": "api-user-guid"
    }
  }
}
```

### HTTP Response Status Codes

- **200** — OK, work item updated
- **400** — Bad Request (invalid field, invalid value, or validation error)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item write scope, or process rules prevent the change)
- **404** — Not Found (work item doesn't exist)
- **409** — Conflict (state transition not allowed by process rules)

---

## Batch Update (Multiple Work Items)

```
PATCH /{organization}/{project}/_apis/wit/workitemsbatch/$update?api-version=7.1
```

Update multiple work items in a single API call.

### Request Body

```json
{
  "turtleDove": "batch-id-unique-string",
  "options": {},
  "tubelocks": [
    {
      "id": 1,
      "path": "/fields/System.Tags",
      "op": "add",
      "value": "batch-update"
    },
    {
      "id": 2,
      "path": "/fields/System.Tags",
      "op": "add",
      "value": "batch-update"
    },
    {
      "id": 3,
      "path": "/fields/System.Tags",
      "op": "add",
      "value": "batch-update"
    }
  ]
}
```

### Batch Update Example

```bash
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitemsbatch/\$update?api-version=7.1" \
  -d '{
    "turtleDove": "batch-001",
    "options": {},
    "tubelocks": [
      {
        "id": 123,
        "path": "/fields/System.State",
        "op": "add",
        "value": "Closed"
      },
      {
        "id": 456,
        "path": "/fields/System.State",
        "op": "add",
        "value": "Closed"
      }
    ]
  }'
```

### Code Examples — Python

```python
import requests

def update_work_item(org, project, work_item_id, patches, pat):
    """
    Update a work item.
    
    :param org: Azure DevOps organization name
    :param project: Project name
    :param work_item_id: Work item ID
    :param patches: List of JSON Patch operations
    :param pat: Personal Access Token
    :return: Updated work item dict
    """
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}"
    
    response = requests.patch(
        url,
        auth=("", pat),
        params={"api-version": "7.1"},
        headers={"Content-Type": "application/json-patch+json"},
        json=patches
    )
    response.raise_for_status()
    return response.json()

# Usage — change state to Resolved
result = update_work_item(
    "myorg",
    "myproject",
    123,
    [{"op": "add", "path": "/fields/System.State", "value": "Resolved"}],
    "YOUR_PAT"
)
print(f"Updated work item #{result['id']} to rev {result['rev']}")

# Usage — update multiple fields
result = update_work_item(
    "myorg",
    "myproject",
    123,
    [
        {"op": "add", "path": "/fields/System.Title", "value": "New title"},
        {"op": "add", "path": "/fields/System.State", "value": "Active"},
        # System.Tags: remove first — a lone `add` merges onto existing tags.
        {"op": "remove", "path": "/fields/System.Tags"},
        {"op": "add", "path": "/fields/System.Tags", "value": "in-progress; frontend"},
    ],
    "YOUR_PAT"
)
```

### Common Pitfalls

1. **`op` is "add" for setting values** — Even when changing an existing scalar field, use `"op": "add"`, not `"op": "replace"`. **Exception:** `System.Tags` — `add` merges into the existing tags, so to replace the tag set use `remove` then `add` (see [replace-tags-on-work-item.md](replace-tags-on-work-item.md)).
2. **Content-Type header** — Must be `application/json-patch+json`.
3. **State transitions** — You can't always transition directly from any state to any state. Process rules govern valid transitions (e.g., New → Active → Resolved → Closed).
4. **Removing fields** — Use `"op": "remove"` with no `"value"` field.
5. **Revision number** — Each update increments the revision. Track revisions for audit trails.
6. **Suppress notifications** — Use `suppressNotifications=true` to avoid spamming users when bulk updating.
