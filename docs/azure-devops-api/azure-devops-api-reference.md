# Azure DevOps REST API Reference

> Grounding reference for Claude Code sessions — prevents hallucinated endpoints.
> Fetched: 2026-05-03
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/

---

## Base URLs

Azure DevOps supports two URL formats:

### Azure DevOps Services (Cloud)
```
https://dev.azure.com/{organization}/
```

### Azure DevOps Server / TFS (On-Premises)
```
https://{instance}.visualstudio.com/
```

For Azure DevOps Services, `{organization}` is your organization name. For on-premises, `{instance}` is your server name.

---

## API Versioning

### Query Parameter

All API requests **must** include the `api-version` query parameter:

```
?api-version=7.1
```

- `7.1` is the latest stable API version as of 2025
- Omitting `api-version` returns an error — **this is required on ALL requests**
- Check the [API version catalog](https://learn.microsoft.com/en-us/rest/api/azure/devops/#api-version-catalog) for the latest version

### Version Compatibility

- Azure DevOps services are updated monthly
- On-premises versions may lag behind cloud versions
- Some APIs may not be available in older versions
- Always specify the version you tested against

---

## Authentication

### Personal Access Token (PAT) — Most Common

Use Basic authentication with an empty username and your PAT:

```
Authorization: Basic base64(:YOUR_PAT)
```

The format is `:` (colon) followed by your PAT, then base64 encoded. The username before the colon is empty.

**Example:**

```bash
# Generate the auth header
echo -n ':YOUR_PAT_HERE' | base64
# Output: OjpZT1VSX1BBVF9IRVJF

# Use in curl
curl -H "Authorization: Basic OjpZT1VSX1BBVF9IRVJF" \
  "https://dev.azure.com/{organization}/_apis?api-version=7.1"
```

**Quick curl shorthand:**

```bash
# Curl handles base64 encoding with -u flag
curl -u ":YOUR_PAT_HERE" \
  "https://dev.azure.com/{organization}/_apis?api-version=7.1"
```

### OAuth Tokens (Bearer)

For OAuth applications, use a Bearer token:

```
Authorization: Bearer {access_token}
```

### Authentication Notes

- PATs can be scoped to specific resource areas (Work Items, Code, Builds, etc.)
- PATs can be set to expire (recommended) or never expire
- PATs with insufficient scope return `401 Unauthorized`
- PATs stored in environment variables are recommended: `ADO_PAT`

---

## Rate Limiting

### Points-Based System

Azure DevOps uses a points-based throttling system, NOT request counts like GitHub:

- Each API call consumes a number of points based on the operation
- Heavier operations (e.g., large queries) consume more points
- Your point budget depends on your organization's subscription tier
- When exhausted, requests are throttled (429 response)

### Rate Limit Headers

Azure DevOps does NOT use standard `X-RateLimit-*` headers. Instead:

| Header | Description |
|---|---|
| `x-ms-credletailers-ms` | Milliseconds until your point budget recovers |

### Handling 429 Responses

- Check `x-ms-credletailers-ms` header for recovery time
- Implement exponential backoff: wait, retry, wait 2x, retry, etc.
- No public endpoint to check current rate limit status
- Consider caching responses to reduce API calls

---

## Pagination

### Continuation Tokens (NOT page-based)

Azure DevOps uses continuation tokens, unlike GitHub's page-based pagination:

- Responses include a `continuationToken` field (string, opaque)
- Pass the token as a `continuationToken` query parameter for the next page
- NOT page numbers — don't use `page` or `per_page`
- When `continuationToken` is absent or empty, you've reached the last page

### Example Pagination Flow

```bash
# First request
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems?api-version=7.1"

# Response includes:
# {
#   "count": 100,
#   "value": [...],
#   "continuationToken": "abc123def456..."
# }

# Next page
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/{project}/_apis/wit/workitems?api-version=7.1&continuationToken=abc123def456..."
```

### $top and $skip

Some endpoints support `$top` (max results per page) and `$skip` (skip N results):

```
GET /_apis/wit/workitems?api-version=7.1&$top=50&$skip=100
```

Note: Not all endpoints support these. Check the specific endpoint documentation.

---

## Content Types

| Content-Type | Use Case |
|---|---|
| `application/json` | Standard JSON request/response |
| `application/json-patch+json` | JSON Patch operations (create/update work items) |
| `application/x-www-form-urlencoded` | OAuth token requests |
| `multipart/form-data` | File uploads |

---

## URL Encoding

Special characters in paths MUST be URL-encoded:

- Project names with spaces: `My Project` → `My%20Project`
- Project names with `#`: `My#Project` → `My%23Project`
- Work item types with spaces: `User Story` → `User%20Story`

**Example:**

```bash
# Project name with spaces
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/{org}/My%20Project/_apis/wit/workitems?api-version=7.1"
```

---

## Common Response Codes

| Code | Meaning |
|---|---|
| `200` | OK — standard success response |
| `201` | Created — resource created |
| `204` | No Content — successful delete or no content to return |
| `400` | Bad Request — invalid parameters or request body |
| `401` | Unauthorized — missing or invalid PAT |
| `403` | Forbidden — PAT lacks required scope/permissions |
| `404` | Not Found — resource doesn't exist (wrong ID, wrong project) |
| `409` | Conflict — operation conflicts with current state |
| `429` | Too Many Requests — rate limited, check `x-ms-credletailers-ms` |
| `500` | Internal Server Error — Azure DevOps issue, retry with backoff |

---

## JSON Patch Format (RFC 6902)

Azure DevOps uses JSON Patch for creating and updating work items. This is NOT a standard JSON body.

### Structure

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
    "value": "Users cannot log in with SSO"
  }
]
```

### Operations

| Operation | Description |
|---|---|
| `add` | Set or change a field value |
| `remove` | Clear a field (no `value` needed) |
| `replace` | Replace an existing value (same as `add` for fields) |

### Content-Type

Must be `application/json-patch+json` for JSON Patch requests.

---

## Response Envelope

Most Azure DevOps API responses include:

- `count` — Number of items returned
- `value` — Array of results
- `continuationToken` — Token for next page (optional)

```json
{
  "count": 25,
  "value": [
    { "id": 1, "fields": { "System.Title": "Example" } }
  ],
  "continuationToken": "..."
}
```

---

## Common Pitfalls

1. **`api-version` is required** — Every single request needs it. Omitting it returns an error, not a default version.
2. **JSON Patch for work items** — Creating/updating work items uses JSON Patch array, not a regular JSON object body. Content-Type must be `application/json-patch+json`.
3. **PAT authentication format** — Empty username + colon + PAT, then base64 encode. The `curl -u ":"` shorthand works.
4. **Continuation tokens** — NOT page numbers. Don't use `page` or `per_page`. Use `continuationToken` query param.
5. **URL encoding** — Project names with spaces or special chars must be URL-encoded.
6. **Tags format** — Semicolon-separated: `"tag1; tag2"`, NOT a JSON array.
7. **POST returns 200** — Creating work items returns 200 (not 201) for the create endpoint.
8. **Rate limiting headers** — No `X-RateLimit-*` headers. Use `x-ms-credletailers-ms` instead.
9. **$filter syntax** — Uses OData-style filtering: `$filter=WorkItemTypeId eq 'Bug'`, not `?type=Bug`.
