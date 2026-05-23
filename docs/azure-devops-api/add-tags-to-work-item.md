# Add Tags to Work Item

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work%20items/update

---

## Add Tags to Work Item

```
PATCH /{organization}/{project}/_apis/wit/workitems/{id}?api-version=7.1
```

Append tags to an existing work item's `System.Tags` field. Tags are stored as a semicolon-separated string — NOT a JSON array.

### Important

You cannot "append" tags via the API directly. You must first read the current value of `System.Tags`, then send back the combined string. There is no `op: "append"` for this field.

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
  The project name or ID. URL-encode special characters.

- **`id`** (integer) (required)
  The work item ID to update.

#### Query Parameters

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`bypassRules`** (boolean) (optional)
  Set to `true` to bypass validation rules.

- **`bypassPolicy`** (boolean) (optional)
  Set to `true` to bypass policy checks.

### Workflow: Append Tags (Read → Modify → Write)

```bash
# Step 1: Get the current tags
EXISTING=$(curl -s -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?fields=System.Tags&api-version=7.1" \
  | jq -r '.fields["System.Tags"] // ""')

# Step 2: Build the new tag string (deduplicate and append)
NEW_TAG="high-priority"
if [ -z "$EXISTING" ]; then
  TAGS="$NEW_TAG"
else
  # Check if tag already exists (case-sensitive)
  if ! echo "$EXISTING" | grep -qw "$NEW_TAG"; then
    TAGS="$EXISTING; $NEW_TAG"
  else
    TAGS="$EXISTING"
  fi
fi

# Step 3: Update with the combined tag string
curl -u ":$ADO_PAT" \
  -X PATCH \
  -H "Content-Type: application/json-patch+json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
  -d "[
    {
      \"op\": \"add\",
      \"path\": \"/fields/System.Tags\",
      \"value\": \"$TAGS\"
    }
  ]"
```

### Code Example — Python

```python
import requests

def add_tags_to_work_item(org, project, work_item_id, tags_to_add, pat):
    """
    Append tags to a work item without overwriting existing tags.
    
    :param org: Azure DevOps organization name
    :param project: Project name
    :param work_item_id: Work item ID
    :param tags_to_add: List of tag strings to add
    :param pat: Personal Access Token
    :return: Updated work item dict
    """
    # Step 1: Get current tags
    get_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}"
    current = requests.get(
        get_url, auth=("", pat),
        params={"api-version": "7.1", "fields": "System.Tags"}
    ).json()

    existing_tags = set()
    raw = current.get("fields", {}).get("System.Tags", "")
    if raw:
        existing_tags = {t.strip() for t in raw.split(";") if t.strip()}

    # Step 2: Merge tags
    for tag in tags_to_add:
        existing_tags.add(tag.strip())

    combined = "; ".join(sorted(existing_tags))

    # Step 3: Update
    patch_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}"
    response = requests.patch(
        patch_url, auth=("", pat),
        params={"api-version": "7.1"},
        headers={"Content-Type": "application/json-patch+json"},
        json=[{"op": "add", "path": "/fields/System.Tags", "value": combined}]
    )
    response.raise_for_status()
    return response.json()

# Usage
result = add_tags_to_work_item(
    "myorg", "myproject", 123,
    ["high-priority", "security"],
    "YOUR_PAT"
)
```

### HTTP Response Status Codes

- **200** — OK, work item updated
- **400** — Bad Request (invalid field or JSON Patch format)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item write scope)
- **404** — Not Found (work item doesn't exist)

### Common Pitfalls

1. **No native append** — The API has no append operator for `System.Tags`. You must read → modify → write.
2. **Race conditions** — If another user modifies tags between your read and write, their changes will be overwritten. Use the revision number for optimistic concurrency if needed.
3. **Semicolon separator** — Tags use `; ` (semicolon + space) as separator. Inconsistent formatting causes duplicates in the UI.
4. **Case sensitivity** — "Bug" and "bug" are treated as different tags. Normalize before merging.
5. **Empty string** — A work item with no tags returns `System.Tags` as `null` or absent, not an empty string. Handle both cases.
6. **`op: "add"` not `"append"`** — Even appending uses `"op": "add"` with the full combined string.
