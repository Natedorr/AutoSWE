# List check runs for a Git reference

Source: https://docs.github.com/en/rest/checks/runs

## List check runs for a Git reference

```
GET /repos/{owner}/{repo}/commits/{ref}/check-runs
```

Lists check runs for a commit ref. The ref can be a SHA, branch name, or a tag name.
Note

The endpoints to manage checks only look for pushes in the repository where the check suite or check run were created. Pushes to a branch in a forked repository are not detected and return an empty pull\_requests array.

If there are more than 1000 check suites on a single git reference, this endpoint will limit check runs to the 1000 most recent check suites. To iterate over all possible check runs, use the List check suites for a Git reference endpoint and provide the check\_suite\_id parameter to the List check runs in a check suite endpoint.
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

* **`app_id`** (integer)

### HTTP response status codes

* **200** - OK

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/repos/OWNER/REPO/commits/REF/check-runs
```

**Response schema (Status: 200):**

Same response schema as [List check runs in a check suite](#list-check-runs-in-a-check-suite).

