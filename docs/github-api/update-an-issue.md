# Update an issue

Source: https://docs.github.com/en/rest/issues/issues

## Update an issue

```
PATCH /repos/{owner}/{repo}/issues/{issue_number}
```

Issue owners and users with push access or Triage role can edit an issue.
This endpoint supports the following custom media types. For more information, see "Media types."

application/vnd.github.raw+json: Returns the raw markdown body. Response will include body. This is the default if you do not pass any specific media type.
application/vnd.github.text+json: Returns a text only representation of the markdown body. Response will include body_text.
application/vnd.github.html+json: Returns HTML rendered from the body's markdown. Response will include body_html.
application/vnd.github.full+json: Returns raw, text, and HTML representations. Response will include body, body_text, and body_html.


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

- **`title`** (null or string or integer)
  The title of the issue.

- **`body`** (string or null)
  The contents of the issue.

- **`state`** (string)
  The open or closed state of the issue.
  Can be one of: `open`, `closed`

- **`state_reason`** (string or null)
  The reason for the state change. Ignored unless state is changed.
  Can be one of: `completed`, `not_planned`, `duplicate`, `reopened`, `null`

- **`milestone`** (null or string or integer)
  The number of the milestone to associate this issue with or use null to remove the current milestone. Only users with push access can set the milestone for issues. Without push access to the repository, milestone changes are silently dropped.

- **`labels`** (array)
  Labels to associate with this issue. Pass one or more labels to replace the set of labels on this issue. Send an empty array ([]) to clear all labels from the issue. Only users with push access can set labels for issues. Without push access to the repository, label changes are silently dropped.

- **`assignees`** (array of strings)
  Usernames to assign to this issue. Pass one or more user logins to replace the set of assignees on this issue. Send an empty array ([]) to clear all assignees from the issue. Only users with push access can set assignees for new issues. Without push access to the repository, assignee changes are silently dropped.

- **`issue_field_values`** (array of objects)
  An array of issue field values to set on this issue. Each field value must include the field ID and the value to set. Only users with push access can set field values for issues
  - **`field_id`** (integer) (required)
    The ID of the issue field to set
  - **`value`** (string or number) (required)
    The value to set for the field

- **`type`** (string or null)
  The name of the issue type to associate with this issue or use null to remove the current issue type. Only users with push access can set the type for issues. Without push access to the repository, type changes are silently dropped.





### HTTP response status codes


- **200** - OK


- **301** - Moved permanently


- **403** - Forbidden


- **404** - Resource not found


- **410** - Gone


- **422** - Validation failed, or the endpoint has been spammed.


- **503** - Service unavailable




### Code examples



#### Example

**Request:**

```curl
curl -L \
  -X PATCH \
  https://api.github.com/repos/OWNER/REPO/issues/ISSUE_NUMBER \
  -d '{
  "title": "Found a bug",
  "body": "I'm having a problem with this.",
  "assignees": [
    "octocat"
  ],
  "milestone": 1,
  "state": "open",
  "labels": [
    "bug"
  ]
}'
```

**Response schema (Status: 200):**

Same response schema as [Create an issue](#create-an-issue).




