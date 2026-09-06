# Rerequest a check suite

Source: https://docs.github.com/en/rest/checks/suites

## Rerequest a check suite

```
POST /repos/{owner}/{repo}/check-suites/{check_suite_id}/rerequest
```

Triggers GitHub to rerequest an existing check suite, without pushing new code to a repository. This endpoint will trigger the check\_suite webhook event with the action rerequested. When a check suite is rerequested, its status is reset to queued and the conclusion is cleared.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

* **`check_suite_id`** (integer) (required)
  The unique identifier of the check suite.

### HTTP response status codes

* **201** - Created

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/check-suites/CHECK_SUITE_ID/rerequest
```

**Response schema (Status: 201):**

