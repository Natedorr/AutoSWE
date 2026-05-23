# Update a label

Source: https://docs.github.com/en/rest/issues/labels

## Update a label

```
PATCH /repos/{owner}/{repo}/labels/{name}
```

Updates a label using the given label name.


### Parameters


#### Headers


- **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.



#### Path and query parameters

- **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

- **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

- **`name`** (string) (required)




#### Body parameters

- **`new_name`** (string)
  The new name of the label. Emoji can be added to label names, using either native emoji or colon-style markup. For example, typing :strawberry: will render the emoji . For a full list of available emoji and codes, see "Emoji cheat sheet."

- **`color`** (string)
  The hexadecimal color code for the label, without the leading #.

- **`description`** (string)
  A short description of the label. Must be 100 characters or fewer.





### HTTP response status codes


- **200** - OK




### Code examples



#### Example

**Request:**

```curl
curl -L \
  -X PATCH \
  https://api.github.com/repos/OWNER/REPO/labels/NAME \
  -d '{
  "new_name": "bug :bug:",
  "description": "Small bug fix required",
  "color": "b01f26"
}'
```

**Response schema (Status: 200):**

Same response schema as [Create a label](#create-a-label).




