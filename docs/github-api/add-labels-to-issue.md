# Add labels to an issue

Source: https://docs.github.com/en/rest/issues/labels

## Add labels to an issue

```
POST /repos/{owner}/{repo}/issues/{issue_number}/labels
```

Adds labels to an issue.


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




#### Body parameters

- **`labels`** (array of strings)
  The names of the labels to add to the issue's existing labels. You can also pass an array of labels directly, but GitHub recommends passing an object with the labels key. To replace all of the labels for an issue, use "Set labels for an issue."





### HTTP response status codes


- **200** - OK


- **301** - Moved permanently


- **404** - Resource not found


- **410** - Gone


- **422** - Validation failed, or the endpoint has been spammed.




### Code examples



#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER/labels \
  -d '{
  "labels": [
    "bug",
    "enhancement"
  ]
}'
```

**Response schema (Status: 200):**

Same response schema as [List labels for an issue](#list-labels-for-an-issue).




