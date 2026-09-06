# Rerequest a check run

Source: https://docs.github.com/en/rest/checks/runs

## Rerequest a check run

```
POST /repos/{owner}/{repo}/check-runs/{check_run_id}/rerequest
```

Triggers GitHub to rerequest an existing check run, without pushing new code to a repository. This endpoint will trigger the check\_run webhook event with the action rerequested. When a check run is rerequested, the status of the check suite it belongs to is reset to queued and the conclusion is cleared. The check run itself is not updated. GitHub apps recieving the check\_run webhook with the rerequested action should then decide if the check run should be reset or updated and call the update check\_run endpoint to update the check\_run if desired.
For more information about how to re-run GitHub Actions jobs, see "Re-run a job from a workflow run".

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

* **201** - Created

* **403** - Forbidden if the check run is not rerequestable or doesn't belong to the authenticated GitHub App

* **404** - Resource not found

* **422** - Validation error if the check run is not rerequestable

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/check-runs/CHECK_RUN_ID/rerequest
```

**Response schema (Status: 201):**

