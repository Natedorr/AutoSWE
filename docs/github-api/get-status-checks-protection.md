# Get status checks protection

Source: https://docs.github.com/en/rest/branches/branch-protection

## Get status checks protection

```
GET /repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks
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
  https://api.github.com/repos/OWNER/REPO/branches/BRANCH/protection/required_status_checks
```

**Response schema (Status: 200):**

* `url`: required, string, format: uri
* `strict`: required, boolean
* `contexts`: required, array of string
* `checks`: required, array of objects:
  * `context`: required, string
  * `app_id`: required, integer or null
* `contexts_url`: required, string, format: uri

