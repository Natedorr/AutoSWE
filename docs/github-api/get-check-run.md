# Get a check run

Source: https://docs.github.com/en/rest/checks/runs

## Get a check run

```
GET /repos/{owner}/{repo}/check-runs/{check_run_id}
```

Gets a single check run using its id.
Note

The Checks API only looks for pushes in the repository where the check suite or check run were created. Pushes to a branch in a forked repository are not detected and return an empty pull\_requests array.

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

* **`check_run_id`** (integer) (required)
  The unique identifier of the check run.

### HTTP response status codes

* **200** - OK

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X GET \
  https://api.github.com/repos/OWNER/REPO/check-runs/CHECK_RUN_ID
```

**Response schema (Status: 200):**

Same response schema as [Create a check run](#create-a-check-run).

