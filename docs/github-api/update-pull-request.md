# Update a pull request

Source: https://docs.github.com/en/rest/pulls/pulls

## Update a pull request

```
PATCH /repos/{owner}/{repo}/pulls/{pull_number}
```

Draft pull requests are available in public repositories with GitHub Free and GitHub Free for organizations, GitHub Pro, and legacy per-repository billing plans, and in public and private repositories with GitHub Team and GitHub Enterprise Cloud. For more information, see GitHub's products in the GitHub Help documentation.
To open or update a pull request in a public repository, you must have write access to the head or the source branch. For organization-owned repositories, you must be a member of the organization that owns the repository to open or update a pull request.
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

* **`pull_number`** (integer) (required)
  The number that identifies the pull request.

#### Body parameters

* **`title`** (string)
  The title of the pull request.

* **`body`** (string)
  The contents of the pull request.

* **`state`** (string)
  State of this Pull Request. Either open or closed.
  Can be one of: `open`, `closed`

* **`base`** (string)
  The name of the branch you want your changes pulled into. This should be an existing branch on the current repository. You cannot update the base branch on a pull request to point to another repository.

* **`maintainer_can_modify`** (boolean)
  Indicates whether maintainers can modify the pull request.

### HTTP response status codes

* **200** - OK

* **403** - Forbidden

* **422** - Validation failed, or the endpoint has been spammed.

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X PATCH \
  https://api.github.com/repos/OWNER/REPO/pulls/PULL_NUMBER \
  -d '{
  "title": "new title",
  "body": "updated body",
  "state": "open",
  "base": "master"
}'
```

**Response schema (Status: 200):**

Same response schema as [Create a pull request](#create-a-pull-request).
