# Create a check run

Source: https://docs.github.com/en/rest/checks/runs

## Create a check run

```
POST /repos/{owner}/{repo}/check-runs
```

Creates a new check run for a specific commit in a repository.
To create a check run, you must use a GitHub App. OAuth apps and authenticated users are not able to create a check suite.
In a check suite, GitHub limits the number of check runs with the same name to 1000. Once these check runs exceed 1000, GitHub will start to automatically delete older check runs.
Note

The Checks API only looks for pushes in the repository where the check suite or check run were created. Pushes to a branch in a forked repository are not detected and return an empty pull\_requests array.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

#### Body parameters

* **`status`** (string) (required)
  Can be one of: `completed`

### HTTP response status codes

* **201** - Created

### Code examples

#### Example of an in\_progress conclusion

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/check-runs \
  -d '{
  "name": "mighty_readme",
  "head_sha": "ce587453ced02b1526dfb4cb910479d431683101",
  "status": "in_progress",
  "external_id": "42",
  "started_at": "2018-05-04T01:14:52Z",
  "output": {
    "title": "Mighty Readme report",
    "summary": "",
    "text": ""
  }
}'
```

**Response schema (Status: 201):**

* `id`: required, integer, format: int64
* `head_sha`: required, string
* `node_id`: required, string
* `external_id`: required, string or null
* `url`: required, string
* `html_url`: required, string or null
* `details_url`: required, string or null
* `status`: required, string, enum: `queued`, `in_progress`, `completed`, `waiting`, `requested`, `pending`
* `conclusion`: required, string or null, enum: `success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`, `null`
* `started_at`: required, string or null, format: date-time
* `completed_at`: required, string or null, format: date-time
* `output`: required, object:
  * `title`: required, string or null
  * `summary`: required, string or null
  * `text`: required, string or null
  * `annotations_count`: required, integer
  * `annotations_url`: required, string, format: uri
* `name`: required, string
* `check_suite`: required, object or null:
  * `id`: required, integer
* `app`: required, any of:
  * **null**
  * **GitHub app**
    * `id`: required, integer
    * `slug`: string
    * `node_id`: required, string
    * `client_id`: string
    * `owner`: required, one of:
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
      * **Enterprise**
        * `description`: string or null
        * `html_url`: required, string, format: uri
        * `website_url`: string or null, format: uri
        * `id`: required, integer
        * `node_id`: required, string
        * `name`: required, string
        * `slug`: required, string
        * `created_at`: required, string or null, format: date-time
        * `updated_at`: required, string or null, format: date-time
        * `avatar_url`: required, string, format: uri
    * `name`: required, string
    * `description`: required, string or null
    * `external_url`: required, string, format: uri
    * `html_url`: required, string, format: uri
    * `created_at`: required, string, format: date-time
    * `updated_at`: required, string, format: date-time
    * `permissions`: required, object, additional properties: string:
      * `issues`: string
      * `checks`: string
      * `metadata`: string
      * `contents`: string
      * `deployments`: string
    * `events`: required, array of string
    * `installations_count`: integer
* `pull_requests`: required, array of `Pull Request Minimal`:
  * `id`: required, integer, format: int64
  * `number`: required, integer
  * `url`: required, string
  * `head`: required, object:
    * `ref`: required, string
    * `sha`: required, string
    * `repo`: required, object:
      * `id`: required, integer, format: int64
      * `url`: required, string
      * `name`: required, string
  * `base`: required, object:
    * `ref`: required, string
    * `sha`: required, string
    * `repo`: required, object:
      * `id`: required, integer, format: int64
      * `url`: required, string
      * `name`: required, string
* `deployment`: `Deployment`:
  * `url`: required, string, format: uri
  * `id`: required, integer
  * `node_id`: required, string
  * `task`: required, string
  * `original_environment`: string
  * `environment`: required, string
  * `description`: required, string or null
  * `created_at`: required, string, format: date-time
  * `updated_at`: required, string, format: date-time
  * `statuses_url`: required, string, format: uri
  * `repository_url`: required, string, format: uri
  * `transient_environment`: boolean
  * `production_environment`: boolean
  * `performed_via_github_app`: any of:
    * **null**
    * **GitHub app** (see above)

#### Example of a completed conclusion

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/check-runs \
  -d '{
  "name": "mighty_readme",
  "head_sha": "ce587453ced02b1526dfb4cb910479d431683101",
  "status": "completed",
  "started_at": "2017-11-30T19:39:10Z",
  "conclusion": "success",
  "completed_at": "2017-11-30T19:49:10Z",
  "output": {
    "title": "Mighty Readme report",
    "summary": "There are 0 failures, 2 warnings, and 1 notices.",
    "text": "You may have some misspelled words on lines 2 and 4. You also may want to add a section in your README about how to install your app.",
    "annotations": [
      {
        "path": "README.md",
        "annotation_level": "warning",
        "title": "Spell Checker",
        "message": "Check your spelling for 'banaas'.",
        "raw_details": "Do you mean 'bananas' or 'banana'?",
        "start_line": 2,
        "end_line": 2
      },
      {
        "path": "README.md",
        "annotation_level": "warning",
        "title": "Spell Checker",
        "message": "Check your spelling for 'aples'",
        "raw_details": "Do you mean 'apples' or 'Naples'",
        "start_line": 4,
        "end_line": 4
      }
    ],
    "images": [
      {
        "alt": "Super bananas",
        "image_url": "http://example.com/images/42"
      }
    ]
  },
  "actions": [
    {
      "label": "Fix",
      "identifier": "fix_errors",
      "description": "Allow us to fix these errors for you"
    }
  ]
}'
```

**Response schema (Status: 201):**

* `id`: required, integer, format: int64
* `head_sha`: required, string
* `node_id`: required, string
* `external_id`: required, string or null
* `url`: required, string
* `html_url`: required, string or null
* `details_url`: required, string or null
* `status`: required, string, enum: `queued`, `in_progress`, `completed`, `waiting`, `requested`, `pending`
* `conclusion`: required, string or null, enum: `success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`, `null`
* `started_at`: required, string or null, format: date-time
* `completed_at`: required, string or null, format: date-time
* `output`: required, object:
  * `title`: required, string or null
  * `summary`: required, string or null
  * `text`: required, string or null
  * `annotations_count`: required, integer
  * `annotations_url`: required, string, format: uri
* `name`: required, string
* `check_suite`: required, object or null:
  * `id`: required, integer
* `app`: required, any of:
  * **null**
  * **GitHub app**
    * `id`: required, integer
    * `slug`: string
    * `node_id`: required, string
    * `client_id`: string
    * `owner`: required, one of:
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
      * **Enterprise**
        * `description`: string or null
        * `html_url`: required, string, format: uri
        * `website_url`: string or null, format: uri
        * `id`: required, integer
        * `node_id`: required, string
        * `name`: required, string
        * `slug`: required, string
        * `created_at`: required, string or null, format: date-time
        * `updated_at`: required, string or null, format: date-time
        * `avatar_url`: required, string, format: uri
    * `name`: required, string
    * `description`: required, string or null
    * `external_url`: required, string, format: uri
    * `html_url`: required, string, format: uri
    * `created_at`: required, string, format: date-time
    * `updated_at`: required, string, format: date-time
    * `permissions`: required, object, additional properties: string:
      * `issues`: string
      * `checks`: string
      * `metadata`: string
      * `contents`: string
      * `deployments`: string
    * `events`: required, array of string
    * `installations_count`: integer
* `pull_requests`: required, array of `Pull Request Minimal`:
  * `id`: required, integer, format: int64
  * `number`: required, integer
  * `url`: required, string
  * `head`: required, object:
    * `ref`: required, string
    * `sha`: required, string
    * `repo`: required, object:
      * `id`: required, integer, format: int64
      * `url`: required, string
      * `name`: required, string
  * `base`: required, object:
    * `ref`: required, string
    * `sha`: required, string
    * `repo`: required, object:
      * `id`: required, integer, format: int64
      * `url`: required, string
      * `name`: required, string
* `deployment`: `Deployment`:
  * `url`: required, string, format: uri
  * `id`: required, integer
  * `node_id`: required, string
  * `task`: required, string
  * `original_environment`: string
  * `environment`: required, string
  * `description`: required, string or null
  * `created_at`: required, string, format: date-time
  * `updated_at`: required, string, format: date-time
  * `statuses_url`: required, string, format: uri
  * `repository_url`: required, string, format: uri
  * `transient_environment`: boolean
  * `production_environment`: boolean
  * `performed_via_github_app`: any of:
    * **null**
    * **GitHub app** (see above)

