# Remove Tag from Work Item

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work%20items/update

---

## Remove Tag from Work Item

```
PATCH /{organization}/{project}/_apis/wit/workitems/{id}?api-version=7.1
```

Remove a specific tag from a work item's `System.Tags` field while preserving other tags. Since tags are stored as a semicolon-separated string, you must read the current value, remove the target tag, and write back the result.

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

### Workflow: Read → Remove Tag → Write

```bash
# Step 1: Get the current tags
EXISTING=$(curl -s -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?fields=System.Tags&api-version=7.1" \
  | jq -r '.fields["System.Tags"] // ""')

# Step 2: Remove the target tag (case-sensitive match)
TAG_TO_REMOVE="high-priority"
NEW_TAGS=$(echo "$EXISTING" | tr ';' '\n' | sed "s/^[[:space:]]*//;s/[[:space:]]*$//" | grep -v "^${TAG_TO_REMOVE}$" | paste -sd '; ' -)

# Step 3: Update (or remove field if no tags remain)
if [ -z "$NEW_TAGS" ]; then
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
else
  curl -u ":$ADO_PAT" \
    -X PATCH \
    -H "Content-Type: application/json-patch+json" \
    "https://dev.azure.com/myorg/myproject/_apis/wit/workitems/123?api-version=7.1" \
    -d "[
      {
        \"op\": \"add\",
        \"path\": \"/fields/System.Tags\",
        \"value\": \"$NEW_TAGS\"
      }
    ]"
fi
```

### Code Example — Python

```python
import requests

def remove_tag_from_work_item(org, project, work_item_id, tag_to_remove, pat):
    """
    Remove a specific tag from a work item, preserving other tags.
    
    :param org: Azure DevOps organization name
    :param project: Project name
    :param work_item_id: Work item ID
    :param tag_to_remove: Tag string to remove
    :param pat: Personal Access Token
    :return: Updated work item dict
    """
    # Step 1: Get current tags
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{work_item_id}"
    current = requests.get(
        url, auth=("", pat),
        params={"api-version": "7.1", "fields": "System.Tags"}
    ).json()

    raw = current.get("fields", {}).get("System.Tags", "")
    if not raw:
        return current  # No tags to remove

    # Step 2: Remove target tag
    existing_tags = {t.strip() for t in raw.split(";") if t.strip()}
    existing_tags.discard(tag_to_remove.strip())

    # Step 3: Update or clear
    if existing_tags:
        combined = "; ".join(sorted(existing_tags))
        patch = [{"op": "add", "path": "/fields/System.Tags", "value": combined}]
    else:
        patch = [{"op": "remove", "path": "/fields/System.Tags"}]

    response = requests.patch(
        url, auth=("", pat),
        params={"api-version": "7.1"},
        headers={"Content-Type": "application/json-patch+json"},
        json=patch
    )
    response.raise_for_status()
    return response.json()

# Usage
result = remove_tag_from_work_item(
    "myorg", "myproject", 123,
    "high-priority",
    "YOUR_PAT"
)
```

### HTTP Response Status Codes

- **200** — OK, work item updated
- **400** — Bad Request (invalid JSON Patch format)
- **401** — Unauthorized (missing or invalid PAT)
- **403** — Forbidden (PAT lacks work item write scope)
- **404** — Not Found (work item doesn't exist)

### Common Pitfalls

1. **Read-modify-write required** — No single API call removes one tag. You must read the field, parse the semicolon-separated string, remove the target, and write back.
2. **Race conditions** — If another user modifies tags between your read and write, their changes are lost. Consider using the work item revision number for optimistic concurrency.
3. **Case-sensitive matching** — "Bug" and "bug" are different tags. Match exactly.
4. **Empty result** — If removing the last tag, use `"op": "remove"` rather than setting an empty string.
5. **Whitespace handling** — Tags may have varying whitespace around semicolons. Normalize with `.strip()` before comparing.
