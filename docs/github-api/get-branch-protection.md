# Get branch protection

Source: https://docs.github.com/en/rest/branches/branch-protection

## Get branch protection

```
GET /repos/{owner}/{repo}/branches/{branch}/protection
```

Protected branches are available in public repositories with GitHub Free and GitHub Free for organizations, and in public and private repositories with GitHub Pro, GitHub Team, GitHub Enterprise Cloud, and GitHub Enterprise Server. For more information, see GitHub's products in the GitHub Help documentation.

### Parameters

#### Headers

- **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

- **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

- **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

- **`branch`** (string) (required)
  The name of the branch. Cannot contain wildcard characters. To use wildcard characters in branch names, use the GraphQL API.

### HTTP response status codes

- **200** - OK

- **404** - Resource not found

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/repos/OWNER/REPO/branches/BRANCH/protection
```

**Response schema (Status: 200):**

* `url`: string
* `enabled`: boolean
* `required_status_checks`: `Protected Branch Required Status Check`:
  * `url`: string
  * `enforcement_level`: string
  * `contexts`: required, array of string
  * `checks`: required, array of objects:
    * `context`: required, string
    * `app_id`: required, integer or null
  * `contexts_url`: string
  * `strict`: boolean
* `enforce_admins`: `Protected Branch Admin Enforced`:
  * `url`: required, string, format: uri
  * `enabled`: required, boolean
* `required_pull_request_reviews`: `Protected Branch Pull Request Review`:
  * `url`: string, format: uri
  * `dismissal_restrictions`: object:
    * `users`: array of `Simple User`:
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
    * `teams`: array of `Team`:
      * `id`: required, integer
      * `node_id`: required, string
      * `name`: required, string
      * `slug`: required, string
      * `description`: required, string or null
      * `privacy`: string
      * `notification_setting`: string
      * `permission`: required, string
      * `permissions`: object:
        * `pull`: required, boolean
        * `triage`: required, boolean
        * `push`: required, boolean
        * `maintain`: required, boolean
        * `admin`: required, boolean
      * `url`: required, string, format: uri
      * `html_url`: required, string, format: uri
      * `members_url`: required, string
      * `repositories_url`: required, string, format: uri
      * `type`: required, string, enum: `enterprise`, `organization`
      * `access_source`: string, enum: `direct`, `organization`, `enterprise`
      * `organization_id`: integer
      * `enterprise_id`: integer
      * `parent`: required, any of:
        * **null**
        * **Team Simple**
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
    * `apps`: array of `GitHub app`:
      * `id`: required, integer
      * `slug`: string
      * `node_id`: required, string
      * `client_id`: string
      * `owner`: required, one of:
        * **Simple User** (see above)
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
    * `url`: string
    * `users_url`: string
    * `teams_url`: string
  * `bypass_pull_request_allowances`: object:
    * `users`: array of `Simple User` (see above)
    * `teams`: array of `Team` (see above)
    * `apps`: array of `GitHub app` (see above)
  * `dismiss_stale_reviews`: required, boolean
  * `require_code_owner_reviews`: required, boolean
  * `required_approving_review_count`: integer, minimum: 0, maximum: 6
  * `require_last_push_approval`: boolean, default: `false`
* `restrictions`: `Branch Restriction Policy`:
  * `url`: required, string, format: uri
  * `users_url`: required, string, format: uri
  * `teams_url`: required, string, format: uri
  * `apps_url`: required, string, format: uri
  * `users`: required, array of objects:
    * `login`: string
    * `id`: integer, format: int64
    * `node_id`: string
    * `avatar_url`: string
    * `gravatar_id`: string
    * `url`: string
    * `html_url`: string
    * `followers_url`: string
    * `following_url`: string
    * `gists_url`: string
    * `starred_url`: string
    * `subscriptions_url`: string
    * `organizations_url`: string
    * `repos_url`: string
    * `events_url`: string
    * `received_events_url`: string
    * `type`: string
    * `site_admin`: boolean
    * `user_view_type`: string
  * `teams`: required, array of `Team` (see above)
  * `apps`: required, array of objects:
    * `id`: integer
    * `slug`: string
    * `node_id`: string
    * `owner`: object:
      * `login`: string
      * `id`: integer
      * `node_id`: string
      * `url`: string
      * `repos_url`: string
      * `events_url`: string
      * `hooks_url`: string
      * `issues_url`: string
      * `members_url`: string
      * `public_members_url`: string
      * `avatar_url`: string
      * `description`: string
      * `gravatar_id`: string
      * `html_url`: string
      * `followers_url`: string
      * `following_url`: string
      * `gists_url`: string
      * `starred_url`: string
      * `subscriptions_url`: string
      * `organizations_url`: string
      * `received_events_url`: string
      * `type`: string
      * `site_admin`: boolean
      * `user_view_type`: string
    * `name`: string
    * `client_id`: string
    * `description`: string
    * `external_url`: string
    * `html_url`: string
    * `created_at`: string
    * `updated_at`: string
    * `permissions`: object:
      * `metadata`: string
      * `contents`: string
      * `issues`: string
      * `single_file`: string
    * `events`: array of string
* `required_linear_history`: object:
  * `enabled`: boolean
* `allow_force_pushes`: object:
  * `enabled`: boolean
* `allow_deletions`: object:
  * `enabled`: boolean
* `block_creations`: object:
  * `enabled`: boolean
* `required_conversation_resolution`: object:
  * `enabled`: boolean
* `name`: string
* `protection_url`: string
* `required_signatures`: object:
  * `url`: required, string, format: uri
  * `enabled`: required, boolean
* `lock_branch`: object:
  * `enabled`: boolean, default: `false`
* `allow_fork_syncing`: object:
  * `enabled`: boolean, default: `false`

