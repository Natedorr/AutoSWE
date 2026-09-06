# List workflow runs for a repository

Source: https://docs.github.com/en/rest/actions/workflow-runs

## List workflow runs for a repository

```
GET /repos/{owner}/{repo}/actions/runs
```

Lists all workflow runs for a repository. You can use parameters to narrow the list of results. For more information about using parameters, see Parameters.
Anyone with read access to the repository can use this endpoint.
OAuth app tokens and personal access tokens (classic) need the repo scope to use this endpoint with a private repository.
This endpoint will return up to 1,000 results for each search when using the following parameters: actor, branch, check\_suite\_id, created, event, head\_sha, status.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

* **`actor`** (string)
  Returns someone's workflow runs. Use the login for the user who created the push associated with the check suite or workflow run.

* **`branch`** (string)
  Returns workflow runs associated with a branch. Use the name of the branch of the push.

* **`event`** (string)
  Returns workflow run triggered by the event you specify. For example, push, pull\_request or issue. For more information, see "Events that trigger workflows."

* **`status`** (string)
  Returns workflow runs with the check run status or conclusion that you specify. For example, a conclusion can be success or a status can be in\_progress. Only GitHub Actions can set a status of waiting, pending, or requested.
  Can be one of: `completed`, `action_required`, `cancelled`, `failure`, `neutral`, `skipped`, `stale`, `success`, `timed_out`, `in_progress`, `queued`, `requested`, `waiting`, `pending`

* **`per_page`** (integer)
  The number of results per page (max 100). For more information, see "Using pagination in the REST API."
  Default: `30`

* **`page`** (integer)
  The page number of the results to fetch. For more information, see "Using pagination in the REST API."
  Default: `1`

* **`created`** (string)
  Returns workflow runs created within the given date-time range. For more information on the syntax, see "Understanding the search syntax."

* **`exclude_pull_requests`** (boolean)
  If true pull requests are omitted from the response (empty array).
  Default: `false`

* **`check_suite_id`** (integer)
  Returns workflow runs with the check\_suite\_id that you specify.

* **`head_sha`** (string)
  Only returns workflow runs that are associated with the specified head\_sha.

### HTTP response status codes

* **200** - OK

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/repos/OWNER/REPO/actions/runs
```

**Response schema (Status: 200):**

* `total_count`: required, integer
* `workflow_runs`: required, array of `Workflow Run`:
  * `id`: required, integer, format: int64
  * `name`: string or null
  * `node_id`: required, string
  * `check_suite_id`: integer, format: int64
  * `check_suite_node_id`: string
  * `head_branch`: required, string or null
  * `head_sha`: required, string
  * `path`: required, string
  * `run_number`: required, integer
  * `run_attempt`: integer
  * `referenced_workflows`: array of `Referenced workflow` or null:
    * `path`: required, string
    * `sha`: required, string
    * `ref`: string
  * `event`: required, string
  * `status`: required, string or null
  * `conclusion`: required, string or null
  * `workflow_id`: required, integer
  * `url`: required, string
  * `html_url`: required, string
  * `pull_requests`: required, array of `Pull Request Minimal` or null:
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
  * `created_at`: required, string, format: date-time
  * `updated_at`: required, string, format: date-time
  * `actor`: `Simple User`:
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
  * `triggering_actor`: `Simple User` (see above)
  * `run_started_at`: string, format: date-time
  * `jobs_url`: required, string
  * `logs_url`: required, string
  * `check_suite_url`: required, string
  * `artifacts_url`: required, string
  * `cancel_url`: required, string
  * `rerun_url`: required, string
  * `previous_attempt_url`: string or null
  * `workflow_url`: required, string
  * `head_commit`: required, any of:
    * **null**
    * **Simple Commit**
      * `id`: required, string
      * `tree_id`: required, string
      * `message`: required, string
      * `timestamp`: required, string, format: date-time
      * `author`: required, object or null:
        * `name`: required, string
        * `email`: required, string, format: email
      * `committer`: required, object or null:
        * `name`: required, string
        * `email`: required, string, format: email
  * `repository`: required, `Minimal Repository`:
    * `id`: required, integer, format: int64
    * `node_id`: required, string
    * `name`: required, string
    * `full_name`: required, string
    * `owner`: required, `Simple User` (see above)
    * `private`: required, boolean
    * `html_url`: required, string, format: uri
    * `description`: required, string or null
    * `fork`: required, boolean
    * `url`: required, string, format: uri
    * `archive_url`: required, string
    * `assignees_url`: required, string
    * `blobs_url`: required, string
    * `branches_url`: required, string
    * `collaborators_url`: required, string
    * `comments_url`: required, string
    * `commits_url`: required, string
    * `compare_url`: required, string
    * `contents_url`: required, string
    * `contributors_url`: required, string, format: uri
    * `deployments_url`: required, string, format: uri
    * `downloads_url`: required, string, format: uri
    * `events_url`: required, string, format: uri
    * `forks_url`: required, string, format: uri
    * `git_commits_url`: required, string
    * `git_refs_url`: required, string
    * `git_tags_url`: required, string
    * `git_url`: string
    * `issue_comment_url`: required, string
    * `issue_events_url`: required, string
    * `issues_url`: required, string
    * `keys_url`: required, string
    * `labels_url`: required, string
    * `languages_url`: required, string, format: uri
    * `merges_url`: required, string, format: uri
    * `milestones_url`: required, string
    * `notifications_url`: required, string
    * `pulls_url`: required, string
    * `releases_url`: required, string
    * `ssh_url`: string
    * `stargazers_url`: required, string, format: uri
    * `statuses_url`: required, string
    * `subscribers_url`: required, string, format: uri
    * `subscription_url`: required, string, format: uri
    * `tags_url`: required, string, format: uri
    * `teams_url`: required, string, format: uri
    * `trees_url`: required, string
    * `clone_url`: string
    * `mirror_url`: string or null
    * `hooks_url`: required, string, format: uri
    * `svn_url`: string
    * `homepage`: string or null
    * `language`: string or null
    * `forks_count`: integer
    * `stargazers_count`: integer
    * `watchers_count`: integer
    * `size`: integer
    * `default_branch`: string
    * `open_issues_count`: integer
    * `is_template`: boolean
    * `topics`: array of string
    * `has_issues`: boolean
    * `has_projects`: boolean
    * `has_wiki`: boolean
    * `has_pages`: boolean
    * `has_discussions`: boolean
    * `has_pull_requests`: boolean
    * `pull_request_creation_policy`: string, enum: `all`, `collaborators_only`
    * `archived`: boolean
    * `disabled`: boolean
    * `visibility`: string
    * `pushed_at`: string or null, format: date-time
    * `created_at`: string or null, format: date-time
    * `updated_at`: string or null, format: date-time
    * `permissions`: object:
      * `admin`: boolean
      * `maintain`: boolean
      * `push`: boolean
      * `triage`: boolean
      * `pull`: boolean
    * `role_name`: string
    * `temp_clone_token`: string
    * `delete_branch_on_merge`: boolean
    * `subscribers_count`: integer
    * `network_count`: integer
    * `code_of_conduct`: `Code Of Conduct`:
      * `key`: required, string
      * `name`: required, string
      * `url`: required, string, format: uri
      * `body`: string
      * `html_url`: required, string or null, format: uri
    * `license`: object or null:
      * `key`: string
      * `name`: string
      * `spdx_id`: string
      * `url`: string or null
      * `node_id`: string
    * `forks`: integer
    * `open_issues`: integer
    * `watchers`: integer
    * `allow_forking`: boolean
    * `web_commit_signoff_required`: boolean
    * `security_and_analysis`: object or null:
      * `advanced_security`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `code_security`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `dependabot_security_updates`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `secret_scanning`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `secret_scanning_push_protection`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `secret_scanning_non_provider_patterns`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `secret_scanning_ai_detection`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `secret_scanning_delegated_alert_dismissal`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `secret_scanning_delegated_bypass`: object:
        * `status`: string, enum: `enabled`, `disabled`
      * `secret_scanning_delegated_bypass_options`: object:
        * `reviewers`: array of object
    * `custom_properties`: object, additional properties allowed
  * `head_repository`: required, `Minimal Repository` (see above)
  * `head_repository_id`: integer
  * `display_title`: required, string

