# Cancel a workflow run

Source: https://docs.github.com/en/rest/actions/workflow-runs

## Cancel a workflow run

```
POST /repos/{owner}/{repo}/actions/runs/{run_id}/cancel
```

Cancels a workflow run using its id.
OAuth tokens and personal access tokens (classic) need the repo scope to use this endpoint.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

* **`run_id`** (integer) (required)
  The unique identifier of the workflow run.

### HTTP response status codes

* **202** - Accepted

* **409** - Conflict

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/actions/runs/RUN_ID/cancel
```

**Response schema (Status: 202):**

