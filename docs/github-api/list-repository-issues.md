# List repository issues

Source: https://docs.github.com/en/rest/issues/issues

## List repository issues

```
GET /repos/{owner}/{repo}/issues
```

List issues in a repository. Only open issues will be listed.
Note

GitHub's REST API considers every pull request an issue, but not every issue is a pull request. For this reason, "Issues" endpoints may return both issues and pull requests in the response. You can identify pull requests by the pull_request key. Be aware that the id of a pull request returned from "Issues" endpoints will be an issue id. To find out the pull request id, use the "List pull requests" endpoint.

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

- **`milestone`** (string)
  If an integer is passed, it should refer to a milestone by its number field. If the string * is passed, issues with any milestone are accepted. If the string none is passed, issues without milestones are returned.

- **`state`** (string)
  Indicates the state of the issues to return.
  Default: `open`
  Can be one of: `open`, `closed`, `all`

- **`assignee`** (string)
  Can be the name of a user. Pass in none for issues with no assigned user, and * for issues assigned to any user.

- **`type`** (string)
  Can be the name of an issue type. If the string * is passed, issues with any type are accepted. If the string none is passed, issues without type are returned.

- **`creator`** (string)
  The user that created the issue.

- **`mentioned`** (string)
  A user that's mentioned in the issue.

- **`labels`** (string)
  A list of comma separated label names. Example: bug,ui,@high

- **`sort`** (string)
  What to sort results by.
  Default: `created`
  Can be one of: `created`, `updated`, `comments`

- **`direction`** (string)
  The direction to sort the results by.
  Default: `desc`
  Can be one of: `asc`, `desc`

- **`since`** (string)
  Only show results that were last updated after the given time. This is a timestamp in ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ.

- **`per_page`** (integer)
  The number of results per page (max 100). For more information, see "Using pagination in the REST API."
  Default: `30`

- **`page`** (integer)
  The page number of the results to fetch. For more information, see "Using pagination in the REST API."
  Default: `1`






### HTTP response status codes


- **200** - OK


- **301** - Moved permanently


- **404** - Resource not found


- **422** - Validation failed, or the endpoint has been spammed.




### Code examples



#### Example

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/repos/OWNER/REPO/issues
```

**Response schema (Status: 200):**

Same response schema as [List issues assigned to the authenticated user](#list-issues-assigned-to-the-authenticated-user).




