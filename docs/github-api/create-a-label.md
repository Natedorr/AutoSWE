# Create a label

Source: https://docs.github.com/en/rest/issues/labels

## Create a label

```
POST /repos/{owner}/{repo}/labels
```

Creates a label for the specified repository with the given name and color. The name and color parameters are required. The color must be a valid hexadecimal color code.


### Parameters


#### Headers


- **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.



#### Path and query parameters

- **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

- **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.




#### Body parameters

- **`name`** (string) (required)
  The name of the label. Emoji can be added to label names, using either native emoji or colon-style markup. For example, typing :strawberry: will render the emoji . For a full list of available emoji and codes, see "Emoji cheat sheet."

- **`color`** (string)
  The hexadecimal color code for the label, without the leading #.

- **`description`** (string)
  A short description of the label. Must be 100 characters or fewer.





### HTTP response status codes


- **201** - Created


- **404** - Resource not found


- **422** - Validation failed, or the endpoint has been spammed.




### Code examples



#### Example

**Request:**

```curl
curl -L \
  -X POST \
  https://api.github.com/repos/OWNER/REPO/labels \
  -d '{
  "name": "bug",
  "description": "Something isn't working",
  "color": "f29513"
}'
```

**Response schema (Status: 201):**

* `id`: required, integer, format: int64
* `node_id`: required, string
* `url`: required, string, format: uri
* `name`: required, string
* `description`: required, string or null
* `color`: required, string
* `default`: required, boolean




