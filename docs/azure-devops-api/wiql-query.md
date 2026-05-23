# WIQL Query

> Grounding reference for Azure DevOps Work Item Query Language
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work%20items/query
> CQL Reference: https://learn.microsoft.com/en-us/azure/devops/boards/queries/query-help-for-the-query-editor

---

## WIQL (Work Item Query Language)

```
POST /{organization}/{project}/_apis/wit/wiql?query?api-version=7.1
```

WIQL is Azure DevOps's query language for searching and filtering work items. It is the **primary mechanism** for finding work items — far more powerful than the `$filter` parameter on the direct GET endpoint.

WIQL returns matching work item IDs and selected fields. To get full work item details, use the batch GET endpoint with the returned IDs.

### Request Body

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.State] <> 'Closed' ORDER BY [System.ChangedDate] desc"
}
```

### Headers

| Header | Value |
|---|---|
| `Authorization` | `Basic base64(:YOUR_PAT)` |
| `Content-Type` | `application/json` |

---

## Common Query Patterns

### Find Open Bugs

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.State], [System.AssignedTo] FROM WorkItems WHERE [System.WorkItemType] = 'Bug' AND [System.State] <> 'Closed' ORDER BY [System.ChangedDate] desc"
}
```

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title], [System.State], [System.AssignedTo] FROM WorkItems WHERE [System.WorkItemType] = ''Bug'' AND [System.State] <> ''Closed'' ORDER BY [System.ChangedDate] desc"
  }'
```

### Find Items Assigned to a User

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.AssignedTo] = 'John Doe' AND [System.State] <> 'Closed' ORDER BY [System.ChangedDate] desc"
}
```

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.AssignedTo] = ''John Doe'' AND [System.State] <> ''Closed''"
  }'
```

### Find Items Assigned to Current User

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.AssignedTo] = @Me AND [System.State] <> 'Closed'"
}
```

### Find Items in a Specific Iteration (Sprint)

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.IterationPath] UNDER 'MyProject/Sprint 5' AND [System.State] <> 'Closed'"
}
```

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.IterationPath] UNDER ''MyProject/Sprint 5'' AND [System.State] <> ''Closed''"
  }'
```

### Find Items with Specific Tags

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.Tags] FROM WorkItems WHERE [System.Tags] CONTAINS 'security'"
}
```

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title], [System.Tags] FROM WorkItems WHERE [System.Tags] CONTAINS ''security''"
  }'
```

### Date Range Queries

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.ChangedDate] FROM WorkItems WHERE [System.ChangedDate] >= '2024-01-01T00:00:00Z' AND [System.ChangedDate] <= '2024-01-31T23:59:59Z'"
}
```

### Find Items in Current Project (Using @TeamProject)

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.TeamProject] = '@TeamProject' AND [System.State] <> 'Closed' ORDER BY [System.ChangedDate] desc"
}
```

### Find Unassigned Items

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.AssignedTo] IS EMPTY AND [System.State] = 'Active'"
}
```

### Find Items by Multiple Work Item Types

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State] FROM WorkItems WHERE [System.WorkItemType] IN ('Bug', 'Task') AND [System.State] <> 'Closed'"
}
```

### Find Parent Items (Epics/Stories with Children)

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.WorkItemType] FROM WorkItems WHERE [System.WorkItemType] = 'Epic' AND [System.State] <> 'Closed'"
}
```

### Complex Query with Multiple Conditions

```json
{
  "query": "SELECT [System.Id], [System.Title], [System.WorkItemType], [System.State], [System.Priority], [System.AssignedTo] FROM WorkItems WHERE ([System.WorkItemType] = 'Bug' OR [System.WorkItemType] = 'Task') AND [System.State] = 'Active' AND [System.Priority] <= 2 ORDER BY [System.Priority] asc, [System.ChangedDate] desc"
}
```

---

## WIQL Syntax Reference

### SELECT Clause

```sql
SELECT [Field1], [Field2], [Field3] FROM WorkItems
```

Select specific fields. Common fields:

| Field | Description |
|---|---|
| `[System.Id]` | Work item ID |
| `[System.Title]` | Title |
| `[System.State]` | State |
| `[System.WorkItemType]` | Type |
| `[System.AssignedTo]` | Assigned user |
| `[System.CreatedBy]` | Creator |
| `[System.CreatedDate]` | Creation date |
| `[System.ChangedDate]` | Last modified date |
| `[System.Tags]` | Tags |
| `[System.IterationPath]` | Iteration path |
| `[System.AreaPath]` | Area path |
| `[System.Priority]` | Priority |

### WHERE Clause — Operators

| Operator | Example | Description |
|---|---|---|
| `=` | `[System.State] = 'Active'` | Equals |
| `<>` | `[System.State] <> 'Closed'` | Not equals |
| `>` | `[System.Priority] > 2` | Greater than |
| `<` | `[System.Priority] < 3` | Less than |
| `>=` | `[System.ChangedDate] >= '2024-01-01'` | Greater than or equal |
| `<=` | `[System.ChangedDate] <= '2024-12-31'` | Less than or equal |
| `CONTAINS` | `[System.Tags] CONTAINS 'bug'` | Contains substring |
| `NOT CONTAINS` | `[System.Tags] NOT CONTAINS 'wontfix'` | Does not contain |
| `IS EMPTY` | `[System.AssignedTo] IS EMPTY` | Field is null/empty |
| `IS NOT EMPTY` | `[System.AssignedTo] IS NOT EMPTY` | Field has a value |
| `UNDER` | `[System.IterationPath] UNDER 'Project/Sprint'` | Under hierarchy node |
| `NOT UNDER` | `[System.IterationPath] NOT UNDER 'Project/Archived'` | Not under node |
| `CHILD OF` | `[System.Id] CHILD OF @WIT123` | Direct child of |
| `PARENT OF` | `[System.Id] PARENT OF @WIT456` | Direct parent of |
| `IN` | `[System.WorkItemType] IN ('Bug', 'Task')` | In list |

### Special Tokens

| Token | Description |
|---|---|
| `@TeamProject` | Current project |
| `@Me` | Current user (authenticated user) |
| `@Iteration` | Current iteration |
| `@WIT{id}` | Reference to another work item by ID |

### ORDER BY

```sql
ORDER BY [System.ChangedDate] desc
ORDER BY [System.Priority] asc, [System.ChangedDate] desc
```

- `asc` — ascending (default)
- `desc` — descending

---

## Full Workflow Example

### Step 1: Run WIQL Query

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = ''Bug'' AND [System.State] <> ''Closed''"
  }'
```

### Step 2: Extract IDs from Response

Response includes `workItems` array with IDs:

```json
{
  "workItems": [
    { "id": 101 },
    { "id": 102 },
    { "id": 103 }
  ]
}
```

### Step 3: Get Full Details via Batch GET

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems?ids=101,102,103&\$expand=all&api-version=7.1"
```

### Python End-to-End Example

```python
import requests

def query_and_fetch(org, project, wiql_query, pat):
    """Run a WIQL query and fetch full work item details."""
    
    # Step 1: Run WIQL
    wiql_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/wiql"
    wiql_response = requests.post(
        wiql_url,
        auth=("", pat),
        params={"api-version": "7.1"},
        headers={"Content-Type": "application/json"},
        json={"query": wiql_query}
    )
    wiql_response.raise_for_status()
    wiql_result = wiql_response.json()
    
    # Step 2: Extract IDs
    ids = [wi["id"] for wi in wiql_result.get("workItems", [])]
    if not ids:
        return []
    
    # Step 3: Batch get full details
    batch_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems"
    batch_response = requests.get(
        batch_url,
        auth=("", pat),
        params={
            "api-version": "7.1",
            "ids": ",".join(str(i) for i in ids),
            "$expand": "all"
        }
    )
    batch_response.raise_for_status()
    
    return batch_response.json().get("value", [])

# Usage
bugs = query_and_fetch(
    "myorg",
    "myproject",
    "SELECT [System.Id] FROM WorkItems WHERE [System.WorkItemType] = 'Bug' AND [System.State] <> 'Closed'",
    "YOUR_PAT"
)

for bug in bugs:
    print(f"#{bug['id']}: {bug['fields']['System.Title']} ({bug['fields']['System.State']})")
```

---

## HTTP Response Status Codes

- **200** — OK, query executed successfully
- **400** — Bad Request (invalid WIQL syntax)
- **401** — Unauthorized (missing or invalid PAT)
- **404** — Not Found (project doesn't exist)

## Common Pitfalls

1. **Single quotes in JSON** — Escape single quotes in JSON by doubling them: `''Bug''` becomes `'Bug'` in the actual query. This is the most common source of errors.
2. **WIQL returns limited data** — WIQL gives you selected fields and IDs. Use batch GET for full details including relations.
3. **Batch GET ID limits** — There's a URL length limit for batch GET. If you have many results, split into multiple requests.
4. **`UNDER` operator** — Use `UNDER` for iteration/area hierarchy queries, not `=`. `=` only matches exact paths.
5. **Date format** — Use ISO 8601 format: `'2024-01-15T00:00:00Z'`.
6. **`@Me` vs email** — `@Me` resolves to the authenticated user. You can also use email addresses or display names directly.
7. **Query timeout** — Very large queries may time out. Add `ORDER BY` with a reasonable `$top` limit.
8. **Field references** — Always use bracket notation: `[System.Title]`, not `System.Title`.
