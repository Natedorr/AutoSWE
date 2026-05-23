# Create an issue

Source: https://docs.github.com/en/rest/issues/issues

## Create an issue

```
POST /repos/{owner}/{repo}/issues
```

Any user with pull access to a repository can create an issue. If issues are disabled in the repository, the API returns a 410 Gone status.
This endpoint triggers notifications. Creating content too quickly using this endpoint may result in secondary rate limiting. For more information, see "Rate limits for the API"
and "Best practices for using the REST API."
This endpoint supports the following custom media types. For more information, see "Media types."

application/vnd.github.raw+json: Returns the raw markdown body. Response will include body. This is the default if you do not pass any specific media type.
application/vnd.github.text+json: Returns a text only representation of the markdown body. Response will include body_text.
application/vnd.github.html+json: Returns HTML rendered from the body's markdown. Response will include body_html.
application/vnd.github.full+json: Returns raw, text, and HTML representations. Response will include body, body_text, and body_html.


### Parameters


#### Headers


- **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.



#### Path and query parameters

- **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

- **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.




#### Body parameters

- **`title`** (string or integer) (required)
  The title of the issue.

- **`body`** (string)
  The contents of the issue.

- **`milestone`** (null or string or integer)
  The number of the milestone to associate this issue with. NOTE: Only users with push access can set the milestone for new issues. The milestone is silently dropped otherwise.

- **`labels`** (array)
  Labels to associate with this issue. NOTE: Only users with push access can set labels for new issues. Labels are silently dropped otherwise.

- **`assignees`** (array of strings)
  Logins for Users to assign to this issue. NOTE: Only users with push access can set assignees for new issues. Assignees are silently dropped otherwise.

- **`type`** (string or null)
  The name of the issue type to associate with this issue. NOTE: Only users with push access can set the type for new issues. The type is silently dropped otherwise.





### HTTP response status codes


- **201** - Created


- **400** - Bad Request


- **403** - Forbidden


- **404** - Resource not found


- **410** - Gone


- **422** - Validation failed, or the endpoint has been spammed.


- **503** - Service unavailable




### Code examples



#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/issues \
  -d '{
  "title": "Found a bug",
  "body": "I'm having a problem with this.",
  "assignees": [
    "octocat"
  ],
  "milestone": 1,
  "labels": [
    "bug"
  ]
}'
```

**Response schema (Status: 201):**

* `id`: required, integer, format: int64
* `node_id`: required, string
* `url`: required, string, format: uri
* `repository_url`: required, string, format: uri
* `labels_url`: required, string
* `comments_url`: required, string, format: uri
* `events_url`: required, string, format: uri
* `html_url`: required, string, format: uri
* `number`: required, integer
* `state`: required, string
* `state_reason`: string or null, enum: `completed`, `reopened`, `not_planned`, `duplicate`, `null`
* `title`: required, string
* `body`: string or null
* `user`: required, any of:
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
* `labels`: required, array of object
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
* `locked`: required, boolean
* `active_lock_reason`: string or null
* `comments`: required, integer
* `pull_request`: object:
  * `merged_at`: string or null, format: date-time
  * `diff_url`: required, string or null, format: uri
  * `html_url`: required, string or null, format: uri
  * `patch_url`: required, string or null, format: uri
  * `url`: required, string or null, format: uri
* `closed_at`: required, string or null, format: date-time
* `created_at`: required, string, format: date-time
* `updated_at`: required, string, format: date-time
* `draft`: boolean
* `closed_by`: any of:
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
* `body_html`: string
* `body_text`: string
* `timeline_url`: string, format: uri
* `type`: `Issue Type`:
  * `id`: required, integer
  * `node_id`: required, string
  * `name`: required, string
  * `description`: required, string or null
  * `color`: string or null, enum: `gray`, `blue`, `green`, `yellow`, `orange`, `red`, `pink`, `purple`, `null`
  * `created_at`: string, format: date-time
  * `updated_at`: string, format: date-time
  * `is_enabled`: boolean
* `repository`: `Repository`:
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
* `performed_via_github_app`: any of:
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
* `author_association`: string, enum: `COLLABORATOR`, `CONTRIBUTOR`, `FIRST_TIMER`, `FIRST_TIME_CONTRIBUTOR`, `MANNEQUIN`, `MEMBER`, `NONE`, `OWNER`
* `reactions`: `Reaction Rollup`:
  * `url`: required, string, format: uri
  * `total_count`: required, integer
  * `+1`: required, integer
  * `-1`: required, integer
  * `laugh`: required, integer
  * `confused`: required, integer
  * `heart`: required, integer
  * `hooray`: required, integer
  * `eyes`: required, integer
  * `rocket`: required, integer
* `sub_issues_summary`: `Sub-issues Summary`:
  * `total`: required, integer
  * `completed`: required, integer
  * `percent_completed`: required, integer
* `parent_issue_url`: string or null, format: uri
* `pinned_comment`: any of:
  * **null**
  * **Issue Comment**
    * `id`: required, integer, format: int64
    * `node_id`: required, string
    * `url`: required, string, format: uri
    * `body`: string
    * `body_text`: string
    * `body_html`: string
    * `html_url`: required, string, format: uri
    * `user`: required, any of:
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
    * `created_at`: required, string, format: date-time
    * `updated_at`: required, string, format: date-time
    * `issue_url`: required, string, format: uri
    * `author_association`: string, enum: `COLLABORATOR`, `CONTRIBUTOR`, `FIRST_TIMER`, `FIRST_TIME_CONTRIBUTOR`, `MANNEQUIN`, `MEMBER`, `NONE`, `OWNER`
    * `performed_via_github_app`: any of:
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
    * `reactions`: `Reaction Rollup`:
      * `url`: required, string, format: uri
      * `total_count`: required, integer
      * `+1`: required, integer
      * `-1`: required, integer
      * `laugh`: required, integer
      * `confused`: required, integer
      * `heart`: required, integer
      * `hooray`: required, integer
      * `eyes`: required, integer
      * `rocket`: required, integer
    * `pin`: any of:
      * **null**
      * **Pinned Issue Comment**
        * `pinned_at`: required, string, format: date-time
        * `pinned_by`: required, any of:
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
* `issue_dependencies_summary`: `Issue Dependencies Summary`:
  * `blocked_by`: required, integer
  * `blocking`: required, integer
  * `total_blocked_by`: required, integer
  * `total_blocking`: required, integer
* `issue_field_values`: array of `Issue Field Value`:
  * `issue_field_id`: required, integer, format: int64
  * `node_id`: required, string
  * `data_type`: required, string, enum: `text`, `single_select`, `number`, `date`
  * `value`: required, any of:
    * **string**
    * **number**
    * **integer**
  * `single_select_option`: object or null:
    * `id`: required, integer, format: int64
    * `name`: required, string
    * `color`: required, string




