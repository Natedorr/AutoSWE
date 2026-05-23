# Remove a label from an issue

Source: https://docs.github.com/en/rest/issues/labels

## Remove a label from an issue

```
DELETE /repos/{owner}/{repo}/issues/{issue_number}/labels/{name}
```

Removes the specified label from the issue, and returns the remaining labels on the issue. This endpoint returns a 404 Not Found status if the label does not exist.


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

- **`name`** (string) (required)






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
  -X DELETE \
  https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER/labels/NAME
```

**Response schema (Status: 200):**

Same response schema as [List labels for an issue](#list-labels-for-an-issue).




