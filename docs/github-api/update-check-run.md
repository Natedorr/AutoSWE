# Update a check run

Source: https://docs.github.com/en/rest/checks/runs

## Update a check run

```
PATCH /repos/{owner}/{repo}/check-runs/{check_run_id}
```

Updates a check run for a specific commit in a repository.
Note

The endpoints to manage checks only look for pushes in the repository where the check suite or check run were created. Pushes to a branch in a forked repository are not detected and return an empty pull\_requests array.

OAuth apps and personal access tokens (classic) cannot use this endpoint.

### Parameters

#### Headers

* **`accept`** (string)
  Setting to `application/vnd.github+json` is recommended.

#### Path and query parameters

* **`owner`** (string) (required)
  The account owner of the repository. The name is not case sensitive.

* **`repo`** (string) (required)
  The name of the repository without the .git extension. The name is not case sensitive.

* **`check_run_id`** (integer) (required)
  The unique identifier of the check run.

#### Body parameters

* **`name`** (string)
  The name of the check. For example, "code-coverage".

* **`details_url`** (string)
  The URL of the integrator's site that has the full details of the check.

* **`external_id`** (string)
  A reference for the run on the integrator's system.

* **`started_at`** (string)
  This is a timestamp in ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ.

* **`status`** (string)
  The current status of the check run. Only GitHub Actions can set a status of waiting, pending, or requested.
  Can be one of: `queued`, `in_progress`, `completed`, `waiting`, `requested`, `pending`

* **`conclusion`** (string)
  Required if you provide completed\_at or a status of completed. The final conclusion of the check.
  Note: Providing conclusion will automatically set the status parameter to completed. You cannot change a check run conclusion to stale, only GitHub can set this.
  Can be one of: `action_required`, `cancelled`, `failure`, `neutral`, `success`, `skipped`, `stale`, `timed_out`

* **`completed_at`** (string)
  The time the check completed. This is a timestamp in ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ.

* **`output`** (object)
  Check runs can accept a variety of data in the output object, including a title and summary and can optionally provide descriptive details about the run.
  * **`title`** (string)
    Required.
  * **`summary`** (string) (required)
    Can contain Markdown.
  * **`text`** (string)
    Can contain Markdown.
  * **`annotations`** (array of objects)
    Adds information from your analysis to specific lines of code. Annotations are visible in GitHub's pull request UI. Annotations are visible in GitHub's pull request UI. The Checks API limits the number of annotations to a maximum of 50 per API request. To create more than 50 annotations, you have to make multiple requests to the Update a check run endpoint. Each time you update the check run, annotations are appended to the list of annotations that already exist for the check run. GitHub Actions are limited to 10 warning annotations and 10 error annotations per step. For details about annotations in the UI, see "About status checks".
    * **`path`** (string) (required)
      The path of the file to add an annotation to. For example, assets/css/main.css.
    * **`start_line`** (integer) (required)
      The start line of the annotation. Line numbers start at 1.
    * **`end_line`** (integer) (required)
      The end line of the annotation.
    * **`start_column`** (integer)
      The start column of the annotation. Annotations only support start\_column and end\_column on the same line. Omit this parameter if start\_line and end\_line have different values. Column numbers start at 1.
    * **`end_column`** (integer)
      The end column of the annotation. Annotations only support start\_column and end\_column on the same line. Omit this parameter if start\_line and end\_line have different values.
    * **`annotation_level`** (string) (required)
      The level of the annotation.
      Can be one of: `notice`, `warning`, `failure`
    * **`message`** (string) (required)
      A short description of the feedback for these lines of code. The maximum size is 64 KB.
    * **`title`** (string)
      The title that represents the annotation. The maximum size is 255 characters.
    * **`raw_details`** (string)
      Details about this annotation. The maximum size is 64 KB.
  * **`images`** (array of objects)
    Adds images to the output displayed in the GitHub pull request UI.
    * **`alt`** (string) (required)
      The alternative text for the image.
    * **`image_url`** (string) (required)
      The full URL of the image.
    * **`caption`** (string)
      A short image description.

* **`actions`** (array of objects)
  Possible further actions the integrator can perform, which a user may trigger. Each action includes a label, identifier and description. A maximum of three actions are accepted. To learn more about check runs and requested actions, see "Check runs and requested actions."
  * **`label`** (string) (required)
    The text to be displayed on a button in the web UI. The maximum size is 20 characters.
  * **`description`** (string) (required)
    A short explanation of what this action would do. The maximum size is 40 characters.
  * **`identifier`** (string) (required)
    A reference for the action on the integrator's system. The maximum size is 20 characters.

### HTTP response status codes

* **200** - OK

### Code examples

#### Example

**Request:**

```curl
curl -L \
  -X PATCH \
  https://api.github.com/repos/OWNER/REPO/check-runs/CHECK_RUN_ID \
  -d '{
  "name": "mighty_readme",
  "started_at": "2018-05-04T01:14:52Z",
  "status": "completed",
  "conclusion": "success",
  "completed_at": "2018-05-04T01:14:52Z",
  "output": {
    "title": "Mighty Readme report",
    "summary": "There are 0 failures, 2 warnings, and 1 notices.",
    "text": "You may have some misspelled words on lines 2 and 4. You also may want to add a section in your README about how to install your app.",
    "annotations": [
      {
        "path": "README.md",
        "annotation_level": "warning",
        "title": "Spell Checker",
        "message": "Check your spelling for 'banaas'.",
        "raw_details": "Do you mean 'bananas' or 'banana'?",
        "start_line": 2,
        "end_line": 2
      },
      {
        "path": "README.md",
        "annotation_level": "warning",
        "title": "Spell Checker",
        "message": "Check your spelling for 'aples'",
        "raw_details": "Do you mean 'apples' or 'Naples'",
        "start_line": 4,
        "end_line": 4
      }
    ],
    "images": [
      {
        "alt": "Super bananas",
        "image_url": "http://example.com/images/42"
      }
    ]
  }
}'
```

**Response schema (Status: 200):**

Same response schema as [Create a check run](#create-a-check-run).

