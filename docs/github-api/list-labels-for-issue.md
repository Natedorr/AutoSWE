# List labels for an issue

Source: https://docs.github.com/en/rest/issues/labels

## List labels for an issue

```
GET /repos/{owner}/{repo}/issues/{issue_number}/labels
```

Lists all labels for an issue.


### Parameters


#### Headers


- **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.



#### Path and query parameters

- **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

- **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

- **`issue_number`** (integer) (required)
  The number that identifies the issue.

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


- **410** - Gone




### Code examples



#### Example

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER/labels
```

**Response schema (Status: 200):**

Array of `Label`:
  * `id`: required, integer, format: int64
  * `node_id`: required, string
  * `url`: required, string, format: uri
  * `name`: required, string
  * `description`: required, string or null
  * `color`: required, string
  * `default`: required, boolean




