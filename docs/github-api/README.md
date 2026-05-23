# GitHub REST API Reference

> Grounding reference for Claude Code sessions — prevents hallucinated endpoints.
> Fetched: 2026-05-02

---

## Rate Limits

### Primary Rate Limits

| Authentication Method | Limit |
|---|---|
| Unauthenticated | 60 requests/hour (per IP) |
| Authenticated (PAT, OAuth, GitHub App) | 5,000 requests/hour |
| GitHub Enterprise Cloud | 15,000 requests/hour |
| `GITHUB_TOKEN` (Actions) | 1,000 requests/hour per repo |
| Git LFS (unauthenticated) | 300 requests/minute |
| Git LFS (authenticated) | 3,000 requests/minute |

### Secondary Rate Limits

- Max 100 concurrent requests (shared across REST + GraphQL)
- Max 900 points/minute for REST API endpoints
- Max 80 content-generating requests/minute, 500/hour
- No way to programmatically check secondary rate limit status

### Rate Limit Response Headers

| Header | Description |
|---|---|
| `x-ratelimit-limit` | Max requests per hour |
| `x-ratelimit-remaining` | Requests remaining in current window |
| `x-ratelimit-used` | Requests made in current window |
| `x-ratelimit-reset` | UTC epoch seconds when window resets |
| `x-ratelimit-resource` | Rate limit resource name |

### Exceeding Rate Limits

- Primary: `403` or `429` response, `x-ratelimit-remaining: 0`. Wait until `x-ratelimit-reset`.
- Secondary: `403` or `429` with message. Check `retry-after` header. Exponential backoff recommended.
- `GET /rate_limit` endpoint checks status (doesn't count against primary, but can count against secondary).

---

## Pagination

### Default Behavior

- Default: 30 items per page
- `per_page` parameter: up to 100 items per page
- `link` header in response contains prev/next/first/last URLs

### Link Header Format

```
link: <https://api.github.com/repositories/123/issues?page=2>; rel="prev",
      <https://api.github.com/repositories/123/issues?page=4>; rel="next",
      <https://api.github.com/repositories/123/issues?page=515>; rel="last",
      <https://api.github.com/repositories/123/issues?page=1>; rel="first"
```

### Using with Octokit.js

```javascript
const data = await octokit.paginate("GET /repos/{owner}/{repo}/issues", {
  owner: "octocat",
  repo: "Spoon-Knife",
  per_page: 100,
  headers: { "X-GitHub-Api-Version": "2022-11-28" },
});
```

### Manual Pagination (Python example)

```python
# Follow `link` header for `rel="next"` until no more pages
import re

async def get_all_pages(session, url):
    all_items = []
    while url:
        async with session.get(url, params={"per_page": 100}) as resp:
            items = await resp.json()
            all_items.extend(items)
            link_header = resp.headers.get("Link", "")
            # Extract next URL from link header
            next_match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
            url = next_match.group(1) if next_match else None
    return all_items
```

---

## Issues API

### List Issues

```
GET /repos/{owner}/{repo}/issues
```

Parameters: `state`, `labels`, `sort` (created/updated/comments), `direction` (asc/desc), `since`, `state_reason`, `milestone`, `labels`, `assignee`, `creator`, `mentioned`, `per_page`, `page`

### List Repository Issues

```
GET /repos/{owner}/{repo}/issues
```

### Get Single Issue

```
GET /repos/{owner}/{repo}/issues/{issue_number}
```

### Create Issue

```
POST /repos/{owner}/{repo}/issues
```

Body: `title`, `body` (flavored markdown), `labels`, `assignees`, `milestone`, `assignee` (deprecated)

### Update Issue

```
PATCH /repos/{owner}/{repo}/issues/{issue_number}
```

Body: `title`, `body`, `labels`, `state` (open/closed), `state_reason` (completed/not_planned), `assignees`, `milestone`

### List Issue Comments

```
GET /repos/{owner}/{repo}/issues/{issue_number}/comments
```

Parameters: `sort` (created/updated), `direction` (asc/desc), `since`, `per_page`, `page`

### Create Issue Comment

```
POST /repos/{owner}/{repo}/issues/{issue_number}/comments
```

Body: `body` (required, flavored markdown)

### Update Issue Comment

```
PATCH /repos/{owner}/{repo}/issues/{issue_number}/comments/{comment_id}
```

Body: `body` (required)

### Delete Issue Comment

```
DELETE /repos/{owner}/{repo}/issues/{issue_number}/comments/{comment_id}
```

### List Labels on Issue

```
GET /repos/{owner}/{repo}/issues/{issue_number}/labels
```

### Replace All Labels on Issue

```
PUT /repos/{owner}/{repo}/issues/{issue_number}/labels
```

Body: `labels` (array of label names) — replaces ALL existing labels

### Add Labels to Issue

```
POST /repos/{owner}/{repo}/issues/{issue_number}/labels
```

Body: `labels` (array of label names) — adds to existing labels

### Remove Label from Issue

```
DELETE /repos/{owner}/{repo}/issues/{issue_number}/labels/{name}
```

### Remove All Labels from Issue

```
DELETE /repos/{owner}/{repo}/issues/{issue_number}/labels
```

---

## Pull Request API

### List Pull Requests

```
GET /repos/{owner}/{repo}/pulls
```

Parameters: `state`, `head`, `base`, `sort`, `direction`, `per_page`, `page`

### Get Single Pull Request

```
GET /repos/{owner}/{repo}/pulls/{pull_number}
```

### Create Pull Request

```
POST /repos/{owner}/{repo}/pulls
```

Body: `title`, `head`, `base`, `body`, `maintainer_can_modify`, `draft`

### Update Pull Request

```
PATCH /repos/{owner}/{repo}/pulls/{pull_number}
```

Body: `title`, `body`, `base`, `state`, `maintainer_can_modify`, `reviewers`

### List Pull Request Comments

```
GET /repos/{owner}/{repo}/pulls/{pull_number}/comments
```

### Create Pull Request Review

```
POST /repos/{owner}/{repo}/pulls/{pull_number}/reviews
```

Body: `body`, `event` (APPROVE/REQUEST_CHANGES/COMMENT), `commit_id`, comments[]

### List Pull Request Reviews

```
GET /repos/{owner}/{repo}/pulls/{pull_number}/reviews
```

---

## Labels API

### List Repository Labels

```
GET /repos/{owner}/{repo}/labels
```

Parameters: `per_page`, `page`

### Create Label

```
POST /repos/{owner}/{repo}/labels
```

Body: `name`, `color` (hex without #), `description`

### Update Label

```
PATCH /repos/{owner}/{repo}/labels/{name}
```

Body: `name`, `color`, `description`

### Delete Label

```
DELETE /repos/{owner}/{repo}/labels/{name}
```

---

## Authentication

### Personal Access Token

Include in Authorization header:
```
Authorization: token ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

Or as a Bearer token:
```
Authorization: Bearer ghp_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
```

### Required Headers

- `Accept: application/vnd.github+json` (required for API v3)
- `X-GitHub-Api-Version: 2022-11-28` (recommended for latest features)

---

## Response Codes

| Code | Meaning |
|---|---|
| 200 | OK |
| 201 | Created |
| 204 | No Content (successful delete) |
| 304 | Not Modified |
| 401 | Unauthorized (bad/missing token) |
| 403 | Forbidden (rate limited or no permission) |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Too Many Requests (rate limited) |

---

## Media Types / Previews

- `application/vnd.github+json` — default
- `application/vnd.github.raw+json` — raw content
- `application/vnd.github.html+json` — HTML-rendered content

---

## User API

### Get Authenticated User

```
GET /user
```

Returns the authenticated user object.

### List User Repos

```
GET /user/repos
```

Parameters: `type` (all/owner/member), `sort`, `direction`, `per_page`, `page`

### Auto-Assign Issue

```
POST /repos/{owner}/{repo}/issues/{issue_number}/assignees
```

Body: `assignees` (array of usernames)

## Common Pitfalls

1. **Issue vs Pull Request:** Issues and PRs share the same issue endpoints. PRs appear in issue lists. Use `GET /repos/{owner}/{repo}/pulls/{number}` to specifically get PR data.
2. **Label replacement:** `PUT /repos/{owner}/{repo}/issues/{issue_number}/labels` replaces ALL labels. Use `POST` to add to existing labels.
3. **Pagination:** Always check for `link` header with `rel="next"` — don't assume single page.
4. **Rate limiting:** Secondary rate limits have no check endpoint. Implement exponential backoff.
5. **Markdown:** `body` fields use GitHub-flavored markdown. Escape `<` and `>` in code blocks.
