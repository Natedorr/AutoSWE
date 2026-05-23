# Get the authenticated user

Source: https://docs.github.com/en/rest/users/users

## Get the authenticated user

```
GET /user
```

OAuth app tokens and personal access tokens (classic) need the user scope in order for the response to include private profile information.



### HTTP response status codes


- **200** - OK


- **304** - Not modified


- **401** - Requires authentication


- **403** - Forbidden




### Code examples



#### Example 1: Status Code 200

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/user
```

**Response schema (Status: 200):**

* one of:
  * **Private User**
    * `login`: required, string
    * `id`: required, integer, format: int64
    * `user_view_type`: string
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
    * `name`: required, string or null
    * `company`: required, string or null
    * `blog`: required, string or null
    * `location`: required, string or null
    * `email`: required, string or null, format: email
    * `notification_email`: string or null, format: email
    * `hireable`: required, boolean or null
    * `bio`: required, string or null
    * `twitter_username`: string or null
    * `public_repos`: required, integer
    * `public_gists`: required, integer
    * `followers`: required, integer
    * `following`: required, integer
    * `created_at`: required, string, format: date-time
    * `updated_at`: required, string, format: date-time
    * `private_gists`: required, integer
    * `total_private_repos`: required, integer
    * `owned_private_repos`: required, integer
    * `disk_usage`: required, integer
    * `collaborators`: required, integer
    * `two_factor_authentication`: required, boolean
    * `plan`: object:
      * `collaborators`: required, integer
      * `name`: required, string
      * `space`: required, integer
      * `private_repos`: required, integer
    * `business_plus`: boolean
    * `ldap_dn`: string
  * **Public User**
    * `login`: required, string
    * `id`: required, integer, format: int64
    * `user_view_type`: string
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
    * `name`: required, string or null
    * `company`: required, string or null
    * `blog`: required, string or null
    * `location`: required, string or null
    * `email`: required, string or null, format: email
    * `notification_email`: string or null, format: email
    * `hireable`: required, boolean or null
    * `bio`: required, string or null
    * `twitter_username`: string or null
    * `public_repos`: required, integer
    * `public_gists`: required, integer
    * `followers`: required, integer
    * `following`: required, integer
    * `created_at`: required, string, format: date-time
    * `updated_at`: required, string, format: date-time
    * `plan`: object:
      * `collaborators`: required, integer
      * `name`: required, string
      * `space`: required, integer
      * `private_repos`: required, integer
    * `private_gists`: integer
    * `total_private_repos`: integer
    * `owned_private_repos`: integer
    * `disk_usage`: integer
    * `collaborators`: integer



#### Example 2: Status Code 200

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/user
```

**Response schema (Status: 200):**

* one of:
  * **Private User**
    * `login`: required, string
    * `id`: required, integer, format: int64
    * `user_view_type`: string
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
    * `name`: required, string or null
    * `company`: required, string or null
    * `blog`: required, string or null
    * `location`: required, string or null
    * `email`: required, string or null, format: email
    * `notification_email`: string or null, format: email
    * `hireable`: required, boolean or null
    * `bio`: required, string or null
    * `twitter_username`: string or null
    * `public_repos`: required, integer
    * `public_gists`: required, integer
    * `followers`: required, integer
    * `following`: required, integer
    * `created_at`: required, string, format: date-time
    * `updated_at`: required, string, format: date-time
    * `private_gists`: required, integer
    * `total_private_repos`: required, integer
    * `owned_private_repos`: required, integer
    * `disk_usage`: required, integer
    * `collaborators`: required, integer
    * `two_factor_authentication`: required, boolean
    * `plan`: object:
      * `collaborators`: required, integer
      * `name`: required, string
      * `space`: required, integer
      * `private_repos`: required, integer
    * `business_plus`: boolean
    * `ldap_dn`: string
  * **Public User**
    * `login`: required, string
    * `id`: required, integer, format: int64
    * `user_view_type`: string
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
    * `name`: required, string or null
    * `company`: required, string or null
    * `blog`: required, string or null
    * `location`: required, string or null
    * `email`: required, string or null, format: email
    * `notification_email`: string or null, format: email
    * `hireable`: required, boolean or null
    * `bio`: required, string or null
    * `twitter_username`: string or null
    * `public_repos`: required, integer
    * `public_gists`: required, integer
    * `followers`: required, integer
    * `following`: required, integer
    * `created_at`: required, string, format: date-time
    * `updated_at`: required, string, format: date-time
    * `plan`: object:
      * `collaborators`: required, integer
      * `name`: required, string
      * `space`: required, integer
      * `private_repos`: required, integer
    * `private_gists`: integer
    * `total_private_repos`: integer
    * `owned_private_repos`: integer
    * `disk_usage`: integer
    * `collaborators`: integer




