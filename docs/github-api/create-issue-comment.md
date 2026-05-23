# Create an issue comment

Source: https://docs.github.com/en/rest/issues/comments

## Create an issue comment

```
POST /repos/{owner}/{repo}/issues/{issue_number}/comments
```

You can use the REST API to create comments on issues and pull requests. Every pull request is an issue, but not every issue is a pull request.
This endpoint triggers notifications.
Creating content too quickly using this endpoint may result in secondary rate limiting.
For more information, see "Rate limits for the API"
and "Best practices for using the REST API."
This endpoint supports the following custom media types. For more information, see "Media types."

application/vnd.github.raw+json: Returns the raw markdown body. Response will include body. This is the default if you do not pass any specific media type.
application/vnd.github.text+json: Returns a text only representation of the markdown body. Response will include body\_text.
application/vnd.github.html+json: Returns HTML rendered from the body's markdown. Response will include body\_html.
application/vnd.github.full+json: Returns raw, text, and HTML representations. Response will include body, body\_text, and body\_html.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

* **`issue_number`** (integer) (required)
  The number that identifies the issue.

#### Body parameters

* **`body`** (string) (required)
  The contents of the comment.

### HTTP response status codes

* **201** - Created

* **403** - Forbidden

* **404** - Resource not found

* **410** - Gone

* **422** - Validation failed, or the endpoint has been spammed.

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER/comments \
  -d '{
  "body": "Me too"
}'
```

**Response schema (Status: 201):**

Same response schema as [Get an issue comment](#get-an-issue-comment).

