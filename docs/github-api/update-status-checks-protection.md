# Update status check protection

Source: https://docs.github.com/en/rest/branches/branch-protection

## Update status check protection

```
PATCH /repos/{owner}/{repo}/branches/{branch}/protection/required_status_checks
```

Protected branches are available in public repositories with GitHub Free and GitHub Free for organizations, and in public and private repositories with GitHub Pro, GitHub Team, GitHub Enterprise Cloud, and GitHub Enterprise Server. For more information, see GitHub's products in the GitHub Help documentation.
Updating required status checks requires admin or owner permissions to the repository and branch protection to be enabled.

### Parameters

#### Headers

- **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

- **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

- **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

- **`branch`** (string) (required)
  The name of the branch. Cannot contain wildcard characters. To use wildcard characters in branch names, use the GraphQL API.

#### Body parameters

- **`strict`** (boolean)
  Require branches to be up to date before merging.

- **`contexts`** (array of strings)
  Closing down notice: The list of status checks to require in order to merge into this branch. If any of these checks have recently been set by a particular GitHub App, they will be required to come from that app in future for the branch to merge. Use checks instead of contexts for more fine-grained control.

- **`checks`** (array of objects)
  The list of status checks to require in order to merge into this branch.
  - **`context`** (string) (required)
    The name of the required check
  - **`app_id`** (integer)
    The ID of the GitHub App that must provide this check. Omit this field to automatically select the GitHub App that has recently provided this check, or any app if it was not set by a GitHub App. Pass -1 to explicitly allow any app to set the status.

### HTTP response status codes

- **200** - OK

- **404** - Resource not found

- **422** - Validation failed, or the endpoint has been spammed.

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X PATCH \
  https://api.github.com/repos/OWNER/REPO/branches/BRANCH/protection/required_status_checks \
  -d '{
  "strict": true,
  "contexts": [
    "continuous-integration/travis-ci"
  ]
}'
```

**Response schema (Status: 200):**

Same response schema as [Get status checks protection](#get-status-checks-protection).

