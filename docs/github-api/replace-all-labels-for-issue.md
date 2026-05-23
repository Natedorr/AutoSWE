# Replace all labels for an issue

Source: https://docs.github.com/en/rest/issues/labels

## Set labels for an issue

```
PUT /repos/{owner}/{repo}/issues/{issue_number}/labels
```

Removes any previous labels and sets the new labels for an issue.


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
  The names of the labels to set for the issue. The labels you set replace any existing labels. You can pass an empty array to remove all labels. Alternatively, you can pass a single label as a string or an array of labels directly, but GitHub recommends passing an object with the labels key. You can also add labels to the existing labels for an issue. For more information, see "Add labels to an issue."





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
  -X PUT \
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




