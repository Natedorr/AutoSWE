# List Work Items

> Grounding reference for Azure DevOps Work Items API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work%20items/query

---

## Overview

There are two approaches to listing work items in Azure DevOps:

1. **Approach A — Direct GET** (`/_apis/wit/workitems`) — Simple, limited filtering
2. **Approach B — WIQL Query** (`/_apis/wit/wiql/query`) — Full query language, recommended for filtering

---

## Approach A — Direct GET (Limited)

### Endpoint

```
GET /{organization}/{project}/_apis/wit/workitems?api-version=7.1
```

### Description

Retrieve work items from a project. This endpoint has limited filtering capabilities — it cannot perform complex queries. Best used for simple batch retrieval or when you already know the IDs.

### Parameters

#### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `api-version` | string | **Yes** | API version (e.g., `7.1`) |
| `$filter` | string | No | OData filter expression (e.g., `$filter=WorkItemTypeId eq 'Bug'`) |
| `$top` | integer | No | Maximum number of results to return |
| `$skip` | integer | No | Number of results to skip |
| `$expand` | string | No | Expand related data (e.g., `relations`) |
| `$fields` | string | No | Comma-separated list of fields to return (e.g., `System.Title,System.State`) |
| `ids` | string | No | Comma-separated list of specific work item IDs |
| `continuationToken` | string | No | Token from previous response for pagination |

#### Headers

- **`Authorization`** (string)
  Basic authentication with PAT. Format: `Basic base64(:YOUR_PAT)`

### Examples

#### List Work Items with Filter

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems?api-version=7.1&\$filter=WorkItemTypeId eq 'Bug'"
```

#### Get Specific Work Items by ID

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems?ids=1,2,3&api-version=7.1"
```

#### Get Work Items with Specific Fields Only

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems?api-version=7.1&\$fields=System.Title,System.State,System.Id"
```

#### Paginated Request

```bash
# First page
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems?api-version=7.1&\$top=50"

# Next page (using continuation token from response)
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems?api-version=7.1&\$top=50&continuationToken=abc123def456"
```

### Response

Returns a response envelope with work items:

```json
{
  "count": 25,
  "value": [
    {
      "id": 123,
      "fields": {
        "System.Id": 123,
        "System.Title": "Fix login bug",
        "System.State": "Active",
        "System.WorkItemType": "Bug",
        "System.AssignedTo": {
          "displayName": "John Doe",
          "id": "guid-here"
        },
        "System.CreatedDate": "2024-01-15T10:30:00Z",
        "System.ChangedDate": "2024-01-16T14:20:00Z"
      }
    }
  ],
  "continuationToken": "abc123def456..."
}
```

### HTTP Response Status Codes

- **200** — OK
- **400** — Bad Request (invalid filter or parameters)
- **401** — Unauthorized (missing or invalid PAT)
- **404** — Not Found (project doesn't exist)

### Limitations

- Cannot use complex `AND`/`OR` logic in `$filter`
- Cannot sort results with this endpoint
- Cannot query across projects easily
- Limited to simple equality filters
- Use WIQL (Approach B) for anything beyond basic filtering

---

## Approach B — WIQL Query (Recommended)

### Endpoint

```
POST /{organization}/{project}/_apis/wit/wiql?query?api-version=7.1
```

### Description

Submit a Work Item Query Language (WIQL) query to find work items. WIQL is Azure DevOps's query language for work items, similar to SQL but designed for work items. This is the **recommended approach** for any filtering beyond basic equality.

WIQL returns only the IDs of matching work items. To get full details, use the batch GET endpoint with the returned IDs.

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

### Examples

#### Find Open Bugs

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.WorkItemType] = ''Bug'' AND [System.State] <> ''Closed'' ORDER BY [System.ChangedDate] desc"
  }'
```

#### Find Items Assigned to a User

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.AssignedTo] = ''John Doe'' AND [System.State] <> ''Closed''"
  }'
```

#### Find Items in a Specific Iteration (Sprint)

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title], [System.State] FROM WorkItems WHERE [System.IterationPath] UNDER ''MyProject/Sprint 5''"
  }'
```

#### Find Items with Specific Tags

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.Tags] CONTAINS ''security''"
  }'
```

#### Date Range Query

```bash
curl -u ":$ADO_PAT" \
  -X POST \
  -H "Content-Type: application/json" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/wiql?api-version=7.1" \
  -d '{
    "query": "SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.ChangedDate] >= ''2024-01-01T00:00:00Z'' AND [System.ChangedDate] <= ''2024-01-31T23:59:59Z''"
  }'
```

### Response

WIQL returns only the IDs and requested fields — not full work item details:

```json
{
  "id": "query-guid-here",
  "queryString": "SELECT [System.Id], [System.Title] FROM WorkItems ...",
  "columns": [
    { "refName": "System.Id", "name": "ID", "isIdentity": true },
    { "refName": "System.Title", "name": "Title" }
  ],
  "workItems": [
    { "id": 123, "fields": { "System.Id": 123, "System.Title": "Fix login bug" } },
    { "id": 456, "fields": { "System.Id": 456, "System.Title": "Update UI" } }
  ]
}
```

### Getting Full Work Item Details After WIQL

WIQL returns IDs and limited fields. To get full details, use the batch GET:

```bash
# Get full details for work items returned by WIQL
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/wit/workitems?ids=123,456,789&\$expand=all&api-version=7.1"
```

### HTTP Response Status Codes

- **200** — OK, query executed successfully
- **400** — Bad Request (invalid WIQL syntax)
- **401** — Unauthorized (missing or invalid PAT)
- **404** — Not Found (project doesn't exist)

---

## WIQL Syntax Reference

WIQL is similar to SQL but designed for work item fields. See the [CQL Reference](https://learn.microsoft.com/en-us/azure/devops/boards/queries/query-help-for-the-query-editor) for full syntax.

### Common Operators

| Operator | Description |
|---|---|
| `=` | Equals |
| `<>` | Not equals |
| `>` | Greater than |
| `<` | Less than |
| `>=` | Greater than or equal |
| `<=` | Less than or equal |
| `CONTAINS` | Contains substring |
| `NOT CONTAINS` | Does not contain substring |
| `UNDER` | Under a node in the iteration/area hierarchy |
| `NOT UNDER` | Not under a node |
| `CHILD OF` | Direct child of a parent work item |
| `PARENT OF` | Direct parent of a child work item |
| `AND` / `OR` / `NOT` | Boolean operators |

### Common Field References

| Field | Description |
|---|---|
| `[System.Id]` | Work item ID |
| `[System.Title]` | Title |
| `[System.State]` | State (New, Active, Resolved, Closed) |
| `[System.WorkItemType]` | Type (Bug, User Story, Task, etc.) |
| `[System.AssignedTo]` | Assigned user |
| `[System.CreatedBy]` | Creator |
| `[System.CreatedDate]` | Creation date |
| `[System.ChangedDate]` | Last modified date |
| `[System.Tags]` | Tags |
| `[System.IterationPath]` | Iteration/sprint path |
| `[System.AreaPath]` | Area path |
| `[System.TeamProject]` | Project name |

### Special Values

- `@TeamProject` — Current project
- `@Me` — Current user
- `@Iteration` — Current iteration

---

## Common Pitfalls

1. **Single quotes in WIQL** — Escape single quotes in JSON by doubling them: `''Bug''` becomes `'Bug'` in the actual query.
2. **WIQL returns IDs only** — WIQL gives you IDs and selected fields. Use batch GET for full details.
3. **Batch GET ID limit** — There's a limit on how many IDs you can pass in a single batch GET. If you have many results, split into multiple requests.
4. **`$filter` is limited** — Approach A's `$filter` doesn't support complex logic. Use WIQL for anything beyond simple equality.
5. **Continuation tokens** — Not all endpoints support them. Check the specific endpoint docs.
