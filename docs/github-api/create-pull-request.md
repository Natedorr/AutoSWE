# Create a pull request

Source: https://docs.github.com/en/rest/pulls/pulls

## Create a pull request

```
POST /repos/{owner}/{repo}/pulls
```

Draft pull requests are available in public repositories with GitHub Free and GitHub Free for organizations, GitHub Pro, and legacy per-repository billing plans, and in public and private repositories with GitHub Team and GitHub Enterprise Cloud. For more information, see GitHub's products in the GitHub Help documentation.
To open or update a pull request in a public repository, you must have write access to the head or the source branch. For organization-owned repositories, you must be a member of the organization that owns the repository to open or update a pull request.
This endpoint triggers notifications. Creating content too quickly using this endpoint may result in secondary rate limiting. For more information, see "Rate limits for the API" and "Best practices for using the REST API."
This endpoint supports the following custom media types. For more information, see "Media types."

application/vnd.github.raw+json: Returns the raw markdown body. Response will include body. This is the default if you do not pass any specific media type.
application/vnd.github.text+json: Returns a text only representation of the markdown body. Response will include body\_text.
application/vnd.github.html+json: Returns HTML rendered from the body's markdown. Response will include body\_html.
application/vnd.github.full+json: Returns raw, text, and HTML representations. Response will include body, body\_text, and body\_html.

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

* **`title`** (string)
  The title of the new pull request. Required unless issue is specified.

* **`head`** (string) (required)
  The name of the branch where your changes are implemented. For cross-repository pull requests in the same network, namespace head with a user like this: username:branch.

* **`head_repo`** (string)
  The name of the repository where the changes in the pull request were made. This field is required for cross-repository pull requests if both repositories are owned by the same organization.

* **`base`** (string) (required)
  The name of the branch you want the changes pulled into. This should be an existing branch on the current repository. You cannot submit a pull request to one repository that requests a merge to a base of another repository.

* **`body`** (string)
  The contents of the pull request.

* **`maintainer_can_modify`** (boolean)
  Indicates whether maintainers can modify the pull request.

* **`draft`** (boolean)
  Indicates whether the pull request is a draft. See "Draft Pull Requests" in the GitHub Help documentation to learn more.

* **`issue`** (integer)
  An issue in the repository to convert to a pull request. The issue title, body, and comments will become the title, body, and comments on the new pull request. Required unless title is specified.

### HTTP response status codes

* **201** - Created

* **403** - Forbidden

* **422** - Validation failed, or the endpoint has been spammed.

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/pulls \
  -d '{
  "title": "Amazing new feature",
  "body": "Please pull these awesome changes in!",
  "head": "octocat:new-feature",
  "base": "master"
}'
```

**Response schema (Status: 201):**

* `url`: required, string, format: uri
* `id`: required, integer, format: int64
* `node_id`: required, string
* `html_url`: required, string, format: uri
* `diff_url`: required, string, format: uri
* `patch_url`: required, string, format: uri
* `issue_url`: required, string, format: uri
* `commits_url`: required, string, format: uri
* `review_comments_url`: required, string, format: uri
* `review_comment_url`: required, string
* `comments_url`: required, string, format: uri
* `statuses_url`: required, string, format: uri
* `number`: required, integer
* `state`: required, string, enum: `open`, `closed`
* `locked`: required, boolean
* `title`: required, string
* `user`: required, `Simple User`:
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
* `body`: required, string or null
* `labels`: required, array of objects:
  * `id`: required, integer, format: int64
  * `node_id`: required, string
  * `url`: required, string
  * `name`: required, string
  * `description`: required, string or null
  * `color`: required, string
  * `default`: required, boolean
* `milestone`: required, any of:
  * **null**
  * **Milestone**
    * `url`: required, string, format: uri
    * `html_url`: required, string, format: uri
    * `labels_url`: required, string, format: uri
    * `id`: required, integer
    * `node_id`: required, string
    * `number`: required, integer
    * `state`: required, string, enum: `open`, `closed`, default: `"open"`
    * `title`: required, string
    * `description`: required, string or null
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
    * `open_issues`: required, integer
    * `closed_issues`: required, integer
    * `created_at`: required, string, format: date-time
    * `updated_at`: required, string, format: date-time
    * `closed_at`: required, string or null, format: date-time
    * `due_on`: required, string or null, format: date-time
* `active_lock_reason`: string or null
* `created_at`: required, string, format: date-time
* `updated_at`: required, string, format: date-time
* `closed_at`: required, string or null, format: date-time
* `merged_at`: required, string or null, format: date-time
* `assignees`: array of `Simple User`:
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
* `requested_reviewers`: array of `Simple User`:
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
* `requested_teams`: array of `Team Simple`:
  * `id`: required, integer
  * `node_id`: required, string
  * `url`: required, string, format: uri
  * `members_url`: required, string
  * `name`: required, string
  * `description`: required, string or null
  * `permission`: required, string
  * `privacy`: string
  * `notification_setting`: string
  * `html_url`: required, string, format: uri
  * `repositories_url`: required, string, format: uri
  * `slug`: required, string
  * `ldap_dn`: string
  * `type`: required, string, enum: `enterprise`, `organization`
  * `organization_id`: integer
  * `enterprise_id`: integer
* `head`: required, object:
  * `label`: required, string
  * `ref`: required, string
  * `repo`: required, `Repository`:
    * `id`: required, integer, format: int64
    * `node_id`: required, string
    * `name`: required, string
    * `full_name`: required, string
    * `license`: required, any of:
      * **null**
      * **License Simple**
        * `key`: required, string
        * `name`: required, string
        * `url`: required, string or null, format: uri
        * `spdx_id`: required, string or null
        * `node_id`: required, string
        * `html_url`: string, format: uri
    * `forks`: required, integer
    * `permissions`: object:
      * `admin`: required, boolean
      * `pull`: required, boolean
      * `triage`: boolean
      * `push`: required, boolean
      * `maintain`: boolean
    * `owner`: required, `Simple User`:
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
    * `private`: required, boolean, default: `false`
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
    * `git_url`: required, string
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
    * `ssh_url`: required, string
    * `stargazers_url`: required, string, format: uri
    * `statuses_url`: required, string
    * `subscribers_url`: required, string, format: uri
    * `subscription_url`: required, string, format: uri
    * `tags_url`: required, string, format: uri
    * `teams_url`: required, string, format: uri
    * `trees_url`: required, string
    * `clone_url`: required, string
    * `mirror_url`: required, string or null, format: uri
    * `hooks_url`: required, string, format: uri
    * `svn_url`: required, string, format: uri
    * `homepage`: required, string or null, format: uri
    * `language`: required, string or null
    * `forks_count`: required, integer
    * `stargazers_count`: required, integer
    * `watchers_count`: required, integer
    * `size`: required, integer
    * `default_branch`: required, string
    * `open_issues_count`: required, integer
    * `is_template`: boolean, default: `false`
    * `topics`: array of string
    * `has_issues`: required, boolean, default: `true`
    * `has_projects`: required, boolean, default: `true`
    * `has_wiki`: required, boolean, default: `true`
    * `has_pages`: required, boolean
    * `has_discussions`: boolean, default: `false`
    * `has_pull_requests`: boolean, default: `true`
    * `pull_request_creation_policy`: string, enum: `all`, `collaborators_only`
    * `archived`: required, boolean, default: `false`
    * `disabled`: required, boolean
    * `visibility`: string, default: `"public"`
    * `pushed_at`: required, string or null, format: date-time
    * `created_at`: required, string or null, format: date-time
    * `updated_at`: required, string or null, format: date-time
    * `allow_rebase_merge`: boolean, default: `true`
    * `temp_clone_token`: string
    * `allow_squash_merge`: boolean, default: `true`
    * `allow_auto_merge`: boolean, default: `false`
    * `delete_branch_on_merge`: boolean, default: `false`
    * `allow_update_branch`: boolean, default: `false`
    * `squash_merge_commit_title`: string, enum: `PR_TITLE`, `COMMIT_OR_PR_TITLE`
    * `squash_merge_commit_message`: string, enum: `PR_BODY`, `COMMIT_MESSAGES`, `BLANK`
    * `merge_commit_title`: string, enum: `PR_TITLE`, `MERGE_MESSAGE`
    * `merge_commit_message`: string, enum: `PR_BODY`, `PR_TITLE`, `BLANK`
    * `allow_merge_commit`: boolean, default: `true`
    * `allow_forking`: boolean
    * `web_commit_signoff_required`: boolean, default: `false`
    * `open_issues`: required, integer
    * `watchers`: required, integer
    * `starred_at`: string
    * `anonymous_access_enabled`: boolean
    * `code_search_index_status`: object:
      * `lexical_search_ok`: boolean
      * `lexical_commit_sha`: string
  * `sha`: required, string
  * `user`: required, `Simple User`:
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
* `base`: required, object:
  * `label`: required, string
  * `ref`: required, string
  * `repo`: required, `Repository`:
    * `id`: required, integer, format: int64
    * `node_id`: required, string
    * `name`: required, string
    * `full_name`: required, string
    * `license`: required, any of:
      * **null**
      * **License Simple**
        * `key`: required, string
        * `name`: required, string
        * `url`: required, string or null, format: uri
        * `spdx_id`: required, string or null
        * `node_id`: required, string
        * `html_url`: string, format: uri
    * `forks`: required, integer
    * `permissions`: object:
      * `admin`: required, boolean
      * `pull`: required, boolean
      * `triage`: boolean
      * `push`: required, boolean
      * `maintain`: boolean
    * `owner`: required, `Simple User`:
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
    * `private`: required, boolean, default: `false`
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
    * `git_url`: required, string
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
    * `ssh_url`: required, string
    * `stargazers_url`: required, string, format: uri
    * `statuses_url`: required, string
    * `subscribers_url`: required, string, format: uri
    * `subscription_url`: required, string, format: uri
    * `tags_url`: required, string, format: uri
    * `teams_url`: required, string, format: uri
    * `trees_url`: required, string
    * `clone_url`: required, string
    * `mirror_url`: required, string or null, format: uri
    * `hooks_url`: required, string, format: uri
    * `svn_url`: required, string, format: uri
    * `homepage`: required, string or null, format: uri
    * `language`: required, string or null
    * `forks_count`: required, integer
    * `stargazers_count`: required, integer
    * `watchers_count`: required, integer
    * `size`: required, integer
    * `default_branch`: required, string
    * `open_issues_count`: required, integer
    * `is_template`: boolean, default: `false`
    * `topics`: array of string
    * `has_issues`: required, boolean, default: `true`
    * `has_projects`: required, boolean, default: `true`
    * `has_wiki`: required, boolean, default: `true`
    * `has_pages`: required, boolean
    * `has_discussions`: boolean, default: `false`
    * `has_pull_requests`: boolean, default: `true`
    * `pull_request_creation_policy`: string, enum: `all`, `collaborators_only`
    * `archived`: required, boolean, default: `false`
    * `disabled`: required, boolean
    * `visibility`: string, default: `"public"`
    * `pushed_at`: required, string or null, format: date-time
    * `created_at`: required, string or null, format: date-time
    * `updated_at`: required, string or null, format: date-time
    * `allow_rebase_merge`: boolean, default: `true`
    * `temp_clone_token`: string
    * `allow_squash_merge`: boolean, default: `true`
    * `allow_auto_merge`: boolean, default: `false`
    * `delete_branch_on_merge`: boolean, default: `false`
    * `allow_update_branch`: boolean, default: `false`
    * `squash_merge_commit_title`: string, enum: `PR_TITLE`, `COMMIT_OR_PR_TITLE`
    * `squash_merge_commit_message`: string, enum: `PR_BODY`, `COMMIT_MESSAGES`, `BLANK`
    * `merge_commit_title`: string, enum: `PR_TITLE`, `MERGE_MESSAGE`
    * `merge_commit_message`: string, enum: `PR_BODY`, `PR_TITLE`, `BLANK`
    * `allow_merge_commit`: boolean, default: `true`
    * `allow_forking`: boolean
    * `web_commit_signoff_required`: boolean, default: `false`
    * `open_issues`: required, integer
    * `watchers`: required, integer
    * `starred_at`: string
    * `anonymous_access_enabled`: boolean
    * `code_search_index_status`: object:
      * `lexical_search_ok`: boolean
      * `lexical_commit_sha`: string
  * `sha`: required, string
  * `user`: required, `Simple User`:
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
* `_links`: required, object:
  * `comments`: required, `Link`:
    * `href`: required, string
  * `commits`: required, `Link`:
    * `href`: required, string
  * `statuses`: required, `Link`:
    * `href`: required, string
  * `html`: required, `Link`:
    * `href`: required, string
  * `issue`: required, `Link`:
    * `href`: required, string
  * `review_comments`: required, `Link`:
    * `href`: required, string
  * `review_comment`: required, `Link`:
    * `href`: required, string
  * `self`: required, `Link`:
    * `href`: required, string
* `author_association`: required, string, enum: `COLLABORATOR`, `CONTRIBUTOR`, `FIRST_TIMER`, `FIRST_TIME_CONTRIBUTOR`, `MANNEQUIN`, `MEMBER`, `NONE`, `OWNER`
* `auto_merge`: required, `Auto merge`:
  * `enabled_by`: required, `Simple User`:
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
  * `merge_method`: required, string, enum: `merge`, `squash`, `rebase`
  * `commit_title`: required, string
  * `commit_message`: required, string
* `draft`: boolean
* `merged`: required, boolean
* `mergeable`: required, boolean or null
* `rebaseable`: boolean or null
* `mergeable_state`: required, string
* `merged_by`: required, any of:
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
* `comments`: required, integer
* `review_comments`: required, integer
* `maintainer_can_modify`: required, boolean
* `commits`: required, integer
* `additions`: required, integer
* `deletions`: required, integer
* `changed_files`: required, integer
