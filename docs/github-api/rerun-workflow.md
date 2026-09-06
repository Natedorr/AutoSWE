# Re-run a workflow

Source: https://docs.github.com/en/rest/actions/workflow-runs

## Re-run a workflow

```
POST /repos/{owner}/{repo}/actions/runs/{run_id}/rerun
```

Re-runs your workflow run using its id.
OAuth app tokens and personal access tokens (classic) need the repo scope to use this endpoint.

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

#### Body parameters

* **`enable_debug_logging`** (boolean)
  Whether to enable debug logging for the re-run.
  Default: `false`

### HTTP response status codes

* **201** - Created

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/actions/runs/RUN_ID/rerun
```

**Response schema (Status: 201):**

