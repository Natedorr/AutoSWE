# Create a commit status

Source: https://docs.github.com/en/rest/commits/statuses

## Create a commit status

```
POST /repos/{owner}/{repo}/statuses/{sha}
```

Users with push access in a repository can create commit statuses for a given SHA.
Note: there is a limit of 1000 statuses per sha and context within a repository. Attempts to create more than 1000 statuses will result in a validation error.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

* **`sha`** (string) (required)

#### Body parameters

* **`state`** (string) (required)
  The state of the status.
  Can be one of: `error`, `failure`, `pending`, `success`

* **`target_url`** (string or null)
  The target URL to associate with this status. This URL will be linked from the GitHub UI to allow users to easily see the source of the status.
  For example, if your continuous integration system is posting build status, you would want to provide the deep link for the build output for this specific SHA:
  <http://ci.example.com/user/repo/build/sha>

* **`description`** (string or null)
  A short description of the status.

* **`context`** (string)
  A string label to differentiate this status from the status of other systems. This field is case-insensitive.
  Default: `default`

### HTTP response status codes

* **201** - Created

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/statuses/SHA \
  -d '{
  "state": "success",
  "target_url": "https://example.com/build/status",
  "description": "The build succeeded!",
  "context": "continuous-integration/jenkins"
}'
```

**Response schema (Status: 201):**

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

