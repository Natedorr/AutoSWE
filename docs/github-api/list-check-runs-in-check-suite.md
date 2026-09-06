# List check runs in a check suite

Source: https://docs.github.com/en/rest/checks/runs

## List check runs in a check suite

```
GET /repos/{owner}/{repo}/check-suites/{check_suite_id}/check-runs
```

Lists check runs for a check suite using its id.
Note

The endpoints to manage checks only look for pushes in the repository where the check suite or check run were created. Pushes to a branch in a forked repository are not detected and return an empty pull\_requests array.

OAuth app tokens and personal access tokens (classic) need the repo scope to use this endpoint on a private repository.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

* **`check_suite_id`** (integer) (required)
  The unique identifier of the check suite.

* **`check_name`** (string)
  Returns check runs with the specified name.

* **`status`** (string)
  Returns check runs with the specified status.
  Can be one of: `queued`, `in_progress`, `completed`

* **`filter`** (string)
  Filters check runs by their completed\_at timestamp. latest returns the most recent check runs.
  Default: `latest`
  Can be one of: `latest`, `all`

* **`per_page`** (integer)
  The number of results per page (max 100). For more information, see "Using pagination in the REST API."
  Default: `30`

* **`page`** (integer)
  The page number of the results to fetch. For more information, see "Using pagination in the REST API."
  Default: `1`

### HTTP response status codes

* **200** - OK

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/repos/OWNER/REPO/check-suites/CHECK_SUITE_ID/check-runs
```

**Response schema (Status: 200):**

* `total_count`: required, integer
* `check_runs`: required, array of `CheckRun`:
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

