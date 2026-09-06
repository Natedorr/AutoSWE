# List check suites for a Git reference

Source: https://docs.github.com/en/rest/checks/suites

## List check suites for a Git reference

```
GET /repos/{owner}/{repo}/commits/{ref}/check-suites
```

Lists check suites for a commit ref. The ref can be a SHA, branch name, or a tag name.
Note

The endpoints to manage checks only look for pushes in the repository where the check suite or check run were created. Pushes to a branch in a forked repository are not detected and return an empty pull\_requests array and a null value for head\_branch.

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

* **`ref`** (string) (required)
  The commit reference. Can be a commit SHA, branch name (heads/BRANCH\_NAME), or tag name (tags/TAG\_NAME). For more information, see "Git References" in the Git documentation.

* **`app_id`** (integer)
  Filters check suites by GitHub App id.

* **`check_name`** (string)
  Returns check runs with the specified name.

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
  https://api.github.com/repos/OWNER/REPO/commits/REF/check-suites
```

**Response schema (Status: 200):**

* `total_count`: required, integer
* `check_suites`: required, array of `CheckSuite`:
  * `id`: required, integer, format: int64
  * `node_id`: required, string
  * `head_branch`: required, string or null
  * `head_sha`: required, string
  * `status`: required, string or null, enum: `queued`, `in_progress`, `completed`, `waiting`, `requested`, `pending`, `null`
  * `conclusion`: required, string or null, enum: `success`, `failure`, `neutral`, `cancelled`, `skipped`, `timed_out`, `action_required`, `startup_failure`, `stale`, `null`
  * `url`: required, string or null
  * `before`: required, string or null
  * `after`: required, string or null
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
  * `created_at`: required, string or null, format: date-time
  * `updated_at`: required, string or null, format: date-time
  * `head_commit`: required, `Simple Commit`:
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
  * `latest_check_runs_count`: required, integer
  * `check_runs_url`: required, string
  * `rerequestable`: boolean
  * `runs_rerequestable`: boolean

