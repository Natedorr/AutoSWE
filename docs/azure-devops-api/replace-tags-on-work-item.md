# Replace Tags on Work Item

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/update?view=azure-devops-rest-7.1

---

## Replace Tags on Work Item

```
PATCH /{organization}/{project}/_apis/wit/workitems/{id}?api-version=7.1
```

Completely replace all tags on a work item by setting `System.Tags` to a new value. This overwrites whatever tags existed before.

> **Why two ops?** ADO applies `op: "add"` on `System.Tags` *additively* — the
> value is merged into the existing tag set, not written over it. A lone `add`
> therefore accumulates tags across calls. To get a true replace you must first
> `remove` the field (clearing it to empty) and then `add` the new value. This
> is what autoSWE does in `AzureTracker.set_status` (issue #235).

### Parameters

#### Headers

| Header | Value |
|---|---|
| `Authorization` | `Basic base64(:YOUR_PAT)` |
| `Content-Type` | `application/json-patch+json` |

#### Path Parameters

- **`organization`** (string) (required)
  Your Azure DevOps organization name.

- **`project`** (string) (required)
  The project name or ID.

- **`id`** (integer) (required)
  The work item ID to update.

#### Query Parameters

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

### Request Body — JSON Patch Array

```json
[
  {
    "op": "remove",
    "path": "/fields/System.Tags"
  },
  {
    "op": "add",
    "path": "/fields/System.Tags",
    "value": "bug; high-priority; security"
  }
]
```

### Code Examples

#### Replace all tags with new set

```bash
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
  -d '[
    {
      "op": "remove",
      "path": "/fields/System.Tags"
    },
    {
      "op": "add",
      "path": "/fields/System.Tags",
      "value": "bug; high-priority; security"
    }
  ]'
```

#### Clear all tags (set to empty)

```bash
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
  -d '[
    {
      "op": "remove",
      "path": "/fields/System.Tags"
    }
  ]'
```

#### Python Example

```python
import requests

def replace_tags(org, project, work_item_id, new_tags, pat):
    """
    Replace all tags on a work item with a new set.
    
    :param org: Azure DevOps organization name
    :param project: Project name
    :param work_item_id: Work item ID
    :param new_tags: List of tag strings (replaces all existing tags)
    :param pat: Personal Access Token
    :return: Updated work item dict
    """
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}"

    # `add` on System.Tags is additive, so a true replace requires `remove`
    # first. When the new set is empty, a lone `remove` suffices.
    if new_tags:
        patch_ops = [
            {"op": "remove", "path": "/fields/System.Tags"},
            {"op": "add", "path": "/fields/System.Tags", "value": "; ".join(new_tags)},
        ]
    else:
        patch_ops = [{"op": "remove", "path": "/fields/System.Tags"}]

    response = requests.patch(
        url, auth=("", pat),
        params={"api-version": "7.1"},
        headers={"Content-Type": "application/json-patch+json"},
        json=patch_ops
    )
    response.raise_for_status()
    return response.json()

# Usage
result = replace_tags("myorg", "myproject", 123, ["bug", "critical"], "YOUR_PAT")
```

### HTTP Response Status Codes

- **200** — OK, work item updated
- **400** — Bad Request (invalid JSON Patch format)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item write scope)
- **404** — Not Found (work item doesn't exist)

### Common Pitfalls

1. **This DESTROYS existing tags** — Unlike `add-tags-to-work-item`, this replaces everything. Use only when you want a clean slate.
2. **Remove before add** — `add` on `System.Tags` is additive, so pair it with a preceding `remove` to replace the tag set instead of merging into it.
3. **Use `op: "remove"` to clear** — To remove all tags, use `"op": "remove"` with no value, rather than setting to an empty string.
4. **Tag format** — Semicolon-separated string: `"tag1; tag2; tag3"`. Whitespace after semicolons is cosmetic but recommended for consistency.
