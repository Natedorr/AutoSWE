# Replace Tags on Work Item

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/update?view=azure-devops-rest-7.1

---

## Replace Tags on Work Item

```
PATCH /{organization}/{project}/_apis/wit/workitems/{id}?api-version=7.1
```

Completely replace all tags on a work item by setting `System.Tags` to a new value. This overwrites whatever tags existed before.

> **Why a single `replace` op?** Two constraints force this shape:
>
> - ADO rejects **two operations on the same field in one patch body** — a
>   remove-then-add pair on `System.Tags` fails the whole request with
>   **HTTP 400 VS403691** ("A field cannot be updated more than once in the
>   same update"). The old two-op approach therefore wrote *no* tag at all
>   (issue #235 follow-up).
> - `op: "add"` on `System.Tags` is **additive** — it merges the value into the
>   existing set rather than overwriting it, so a lone `add` accumulates tags
>   across calls.
>
> `op: "replace"` is the only op that sets the field exactly, and it works on
> both a populated *and* an empty `System.Tags` (verified live). This is what
> autoSWE does in `AzureTracker.set_status`.

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
    "op": "replace",
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
      "op": "replace",
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
      "op": "replace",
      "path": "/fields/System.Tags",
      "value": ""
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

    # A single `replace` sets the field exactly. Do NOT pair it with a
    # remove/add: ADO rejects two ops on one field in a body (VS403691), and
    # `add` is additive. Emptying the set is just a replace with "".
    patch_ops = [
        {"op": "replace", "path": "/fields/System.Tags",
         "value": "; ".join(new_tags)},
    ]

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
2. **One op on `System.Tags`, not two** — A single `replace`. Pairing a `remove` and an `add` on the same field in one body is rejected with HTTP 400 VS403691 and the whole write fails.
3. **`replace` to clear** — To remove all tags, use `"op": "replace"` with `"value": ""`; `replace` on an empty value clears the field (verified live).
4. **Tag format** — Semicolon-separated string: `"tag1; tag2; tag3"`. Whitespace after semicolons is cosmetic but recommended for consistency.
