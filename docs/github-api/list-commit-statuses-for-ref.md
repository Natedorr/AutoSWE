# List commit statuses for a reference

Source: https://docs.github.com/en/rest/commits/statuses

## List commit statuses for a reference

```
GET /repos/{owner}/{repo}/commits/{ref}/statuses
```

Users with pull access in a repository can view commit statuses for a given ref. The ref can be a SHA, a branch name, or a tag name. Statuses are returned in reverse chronological order. The first status in the list will be the latest one.
This resource is also available via a legacy route: GET /repos/:owner/:repo/statuses/:ref.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

* **`ref`** (string) (required)
  The commit reference. Can be a commit SHA, branch name (heads/BRANCH\_NAME), or tag name (tags/TAG\_NAME). For more information, see "Git References" in the Git documentation.

* **`per_page`** (integer)
  The number of results per page (max 100). For more information, see "Using pagination in the REST API."
  Default: `30`

* **`page`** (integer)
  The page number of the results to fetch. For more information, see "Using pagination in the REST API."
  Default: `1`

### HTTP response status codes

* **200** - OK

* **301** - Moved permanently

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/repos/OWNER/REPO/commits/REF/statuses
```

**Response schema (Status: 200):**

Array of `Status`:

* `url`: required, string
* `avatar_url`: required, string or null
* `id`: required, integer
* `node_id`: required, string
* `state`: required, string
* `description`: required, string or null
* `target_url`: required, string or null
* `context`: required, string
* `created_at`: required, string
* `updated_at`: required, string
* `creator`: required, any of:
  * **null**
  * **Simple User**
    * `name`: string or null
    * `email`: string or null
    * `login`: required, string
    * `id`: required, integer, format: int64
    * `node_id`: required, string
    * `avatar_url`: required, string, format: uri
    * `gravatar_id`: required, string or null
    * `url`: required, string, format: uri
    * `html_url`: required, string, format: uri
    * `followers_url`: required, string, format: uri
    * `following_url`: required, string
    * `gists_url`: required, string
    * `starred_url`: required, string
    * `subscriptions_url`: required, string, format: uri
    * `organizations_url`: required, string, format: uri
    * `repos_url`: required, string, format: uri
    * `events_url`: required, string
    * `received_events_url`: required, string, format: uri
    * `type`: required, string
    * `site_admin`: required, boolean
    * `starred_at`: string
    * `user_view_type`: string

