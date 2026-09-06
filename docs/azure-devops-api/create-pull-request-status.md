# Pull Request Statuses - Create - REST API (Azure DevOps Git)

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/pull-request-statuses/create?view=azure-devops-rest-7.1


# Pull Request Statuses - Create

- Service:
    - Git

- API Version:
    - 7.1

Create a pull request status.

The only required field for the status is `Context.Name` that uniquely identifies the status. Note that you can specify iterationId in the request body to post the status on the iteration.

```http
POST https://dev.azure.com/{organization}/{project}/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}/statuses?api-version=7.1
```

## URI Parameters

| Name | In | Required | Type | Description |
| --- | --- | --- | --- | --- |
| organization | path | True | string | The name of the Azure DevOps organization. |
| pullRequestId | path | True | integer (int32) | ID of the pull request. |
| repositoryId | path | True | string | The repository ID of the pull request’s target branch. |
| project | path |  | string | Project ID or project name |
| api-version | query | True | string | Version of the API to use. This should be set to '7.1' to use this version of the api. |

## Request Body

| Name | Type | Description |
| --- | --- | --- |
| \_links | ReferenceLinks | Reference links. |
| context | GitStatusContext | Context of the status. |
| createdBy | IdentityRef | Identity that created the status. |
| creationDate | string (date-time) | Creation date and time of the status. |
| description | string | Status description. Typically describes current state of the status. |
| id | integer (int32) | Status identifier. |
| iterationId | integer (int32) | ID of the iteration to associate status with. Minimum value is 1. |
| properties | PropertiesCollection | Custom properties of the status. |
| state | GitStatusState | State of the status. |
| targetUrl | string | URL with status details. |
| updatedDate | string (date-time) | Last update date and time of the status. |

## Responses

| Name | Type | Description |
| --- | --- | --- |
| 200 OK | GitPullRequestStatus | successful operation |

## Security

### oauth2

Type:  oauth2Flow:  accessCodeAuthorization URL:  https://app.vssps.visualstudio.com/oauth2/authorize&response\_type=AssertionToken URL:  https://app.vssps.visualstudio.com/oauth2/token?client\_assertion\_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer&grant\_type=urn:ietf:params:oauth:grant-type:jwt-bearer

#### Scopes

| Name | Description |
| --- | --- |
| vso.code\_write | Grants the ability to read, update, and delete source code, access metadata about commits, changesets, branches, and other version control artifacts. Also grants the ability to create and manage pull requests and code reviews and to receive notifications about version control events via service hooks. |
| vso.code\_status | Grants the ability to read and write commit and pull request status. |

## Examples

| On iteration |
| --- |
| On pull request |
| With properties |

### On iteration

#### Sample request

# [HTTP](#tab/HTTP)
```http
POST https://dev.azure.com/fabrikam/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}/statuses?api-version=7.1

{
  "iterationId": 1,
  "state": "succeeded",
  "description": "Sample status succeeded",
  "context": {
    "name": "sample-status-2",
    "genre": "vsts-samples"
  },
  "targetUrl": "http://fabrikam-fiber-inc.com/CI/builds/1"
}

```

---

#### Sample response

- Status code:
    - 200

```json
{
  "iterationId": 1,
  "id": 1,
  "state": "succeeded",
  "description": "Sample status succeeded",
  "context": {
    "name": "sample-status-2",
    "genre": "vsts-samples"
  },
  "creationDate": "2017-09-19T14:50:26.4429056Z",
  "updatedDate": "2017-09-19T14:50:26.4429056Z",
  "createdBy": {
    "id": "6f168adb-59d4-4fc0-be3b-fb21b939b2a6",
    "displayName": "Normal Paulk",
    "uniqueName": "fabrikamfiber16@hotmail.com",
    "url": "https://dev.azure.com/fabrikam/_apis/Identities/6f168adb-59d4-4fc0-be3b-fb21b939b2a6",
    "imageUrl": "https://dev.azure.com/fabrikam/_api/_common/identityImage?id=6f168adb-59d4-4fc0-be3b-fb21b939b2a6"
  },
  "targetUrl": "http://fabrikam-fiber-inc.com/CI/builds/1",
  "_links": {
    "self": {
      "href": "https://dev.azure.com/fabrikam/_apis/git/repositories/b92c8408-a0c9-4292-88af-bc005a1b8272/pullRequests/2/statuses/1"
    },
    "repository": {
      "href": "https://dev.azure.com/fabrikam/_apis/git/repositories/b92c8408-a0c9-4292-88af-bc005a1b8272"
    }
  }
}
```

### On pull request

#### Sample request

# [HTTP](#tab/HTTP)
```http
POST https://dev.azure.com/fabrikam/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}/statuses?api-version=7.1

{
  "state": "succeeded",
  "description": "Sample status succeeded",
  "context": {
    "name": "sample-status-4",
    "genre": "vsts-samples"
  },
  "targetUrl": "http://fabrikam-fiber-inc.com/CI/builds/1"
}

```

---

#### Sample response

- Status code:
    - 200

```json
{
  "id": 1,
  "state": "succeeded",
  "description": "Sample status succeeded",
  "context": {
    "name": "sample-status-4",
    "genre": "vsts-samples"
  },
  "creationDate": "2017-09-19T14:50:25.1680228Z",
  "updatedDate": "2017-09-19T14:50:25.1680228Z",
  "createdBy": {
    "id": "6f168adb-59d4-4fc0-be3b-fb21b939b2a6",
    "displayName": "Normal Paulk",
    "uniqueName": "fabrikamfiber16@hotmail.com",
    "url": "https://dev.azure.com/fabrikam/_apis/Identities/6f168adb-59d4-4fc0-be3b-fb21b939b2a6",
    "imageUrl": "https://dev.azure.com/fabrikam/_api/_common/identityImage?id=6f168adb-59d4-4fc0-be3b-fb21b939b2a6"
  },
  "targetUrl": "http://fabrikam-fiber-inc.com/CI/builds/1",
  "_links": {
    "self": {
      "href": "https://dev.azure.com/fabrikam/_apis/git/repositories/b92c8408-a0c9-4292-88af-bc005a1b8272/pullRequests/1/statuses/1"
    },
    "repository": {
      "href": "https://dev.azure.com/fabrikam/_apis/git/repositories/b92c8408-a0c9-4292-88af-bc005a1b8272"
    }
  }
}
```

### With properties

#### Sample request

# [HTTP](#tab/HTTP)
```http
POST https://dev.azure.com/fabrikam/_apis/git/repositories/{repositoryId}/pullRequests/{pullRequestId}/statuses?api-version=7.1

{
  "properties": {
    "sampleId": 7,
    "customInfo": "Custom status information",
    "startedDateTime": {
      "$type": "System.DateTime",
      "$value": "2017-09-19T14:50:26.7410146Z"
    },
    "weight": {
      "$type": "System.Double",
      "$value": 1.75
    },
    "bytes": {
      "$type": "System.Byte[]",
      "$value": "dGhpcyBpcyBzYW1wbGUgYmFzZTY0IGVuY29kZWQgc3RyaW5n"
    },
    "globalId": {
      "$type": "System.Guid",
      "$value": "1e788cb9-9d3d-4dc6-ac05-822092d17f90"
    }
  },
  "state": "succeeded",
  "description": "Sample status succeeded",
  "context": {
    "name": "sample-status-1",
    "genre": "vsts-samples"
  },
  "targetUrl": "http://fabrikam-fiber-inc.com/CI/builds/1"
}

```

---

#### Sample response

- Status code:
    - 200

```json
{
  "properties": {
    "bytes": {
      "$type": "System.Byte[]",
      "$value": "dGhpcyBpcyBzYW1wbGUgYmFzZTY0IGVuY29kZWQgc3RyaW5n"
    },
    "customInfo": {
      "$type": "System.String",
      "$value": "Custom status information"
    },
    "globalId": {
      "$type": "System.String",
      "$value": "1e788cb99d3d4dc6ac05822092d17f90"
    },
    "sampleId": {
      "$type": "System.Int32",
      "$value": 7
    },
    "startedDateTime": {
      "$type": "System.DateTime",
      "$value": "2017-09-19T14:50:26.74Z"
    },
    "weight": {
      "$type": "System.Double",
      "$value": 1.75
    }
  },
  "id": 1,
  "state": "succeeded",
  "description": "Sample status succeeded",
  "context": {
    "name": "sample-status-1",
    "genre": "vsts-samples"
  },
  "creationDate": "2017-09-19T14:50:26.7780242Z",
  "updatedDate": "2017-09-19T14:50:26.7780242Z",
  "createdBy": {
    "id": "6f168adb-59d4-4fc0-be3b-fb21b939b2a6",
    "displayName": "Normal Paulk",
    "uniqueName": "fabrikamfiber16@hotmail.com",
    "url": "https://dev.azure.com/fabrikam/_apis/Identities/6f168adb-59d4-4fc0-be3b-fb21b939b2a6",
    "imageUrl": "https://dev.azure.com/fabrikam/_api/_common/identityImage?id=6f168adb-59d4-4fc0-be3b-fb21b939b2a6"
  },
  "targetUrl": "http://fabrikam-fiber-inc.com/CI/builds/1",
  "_links": {
    "self": {
      "href": "https://dev.azure.com/fabrikam/_apis/git/repositories/b92c8408-a0c9-4292-88af-bc005a1b8272/pullRequests/3/statuses/1"
    },
    "repository": {
      "href": "https://dev.azure.com/fabrikam/_apis/git/repositories/b92c8408-a0c9-4292-88af-bc005a1b8272"
    }
  }
}
```

## Definitions

| Name | Description |
| --- | --- |
| GitPullRequestStatus | This class contains the metadata of a service/extension posting pull request status. Status can be associated with a pull request or an iteration. |
| GitStatusContext | Status context that uniquely identifies the status. |
| GitStatusState | State of the status. |
| IdentityRef |  |
| PropertiesCollection | The class represents a property bag as a collection of key-value pairs. Values of all primitive types (any type with a `TypeCode != TypeCode.Object`) except for `DBNull` are accepted. Values of type Byte[], Int32, Double, DateType and String preserve their type, other primitives are retuned as a String. Byte[] expected as base64 encoded string. |
| ReferenceLinks | The class to represent a collection of REST reference links. |

### GitPullRequestStatus

Object

This class contains the metadata of a service/extension posting pull request status. Status can be associated with a pull request or an iteration.

| Name | Type | Description |
| --- | --- | --- |
| \_links | ReferenceLinks | Reference links. |
| context | GitStatusContext | Context of the status. |
| createdBy | IdentityRef | Identity that created the status. |
| creationDate | string (date-time) | Creation date and time of the status. |
| description | string | Status description. Typically describes current state of the status. |
| id | integer (int32) | Status identifier. |
| iterationId | integer (int32) | ID of the iteration to associate status with. Minimum value is 1. |
| properties | PropertiesCollection | Custom properties of the status. |
| state | GitStatusState | State of the status. |
| targetUrl | string | URL with status details. |
| updatedDate | string (date-time) | Last update date and time of the status. |

### GitStatusContext

Object

Status context that uniquely identifies the status.

| Name | Type | Description |
| --- | --- | --- |
| genre | string | Genre of the status. Typically name of the service/tool generating the status, can be empty. |
| name | string | Name identifier of the status, cannot be null or empty. |

### GitStatusState

Enumeration

State of the status.

| Value | Description |
| --- | --- |
| notSet | Status state not set. Default state. |
| pending | Status pending. |
| succeeded | Status succeeded. |
| failed | Status failed. |
| error | Status with an error. |
| notApplicable | Status is not applicable to the target object. |

### IdentityRef

Object

| Name | Type | Description |
| --- | --- | --- |
| \_links | ReferenceLinks | This field contains zero or more interesting links about the graph subject. These links may be invoked to obtain additional relationships or more detailed information about this graph subject. |
| descriptor | string | The descriptor is the primary way to reference the graph subject while the system is running. This field will uniquely identify the same graph subject across both Accounts and Organizations. |
| directoryAlias | string | Deprecated - Can be retrieved by querying the Graph user referenced in the "self" entry of the IdentityRef "\_links" dictionary |
| displayName | string | This is the non-unique display name of the graph subject. To change this field, you must alter its value in the source provider. |
| id | string |  |
| imageUrl | string | Deprecated - Available in the "avatar" entry of the IdentityRef "\_links" dictionary |
| inactive | boolean | Deprecated - Can be retrieved by querying the Graph membership state referenced in the "membershipState" entry of the GraphUser "\_links" dictionary |
| isAadIdentity | boolean | Deprecated - Can be inferred from the subject type of the descriptor (Descriptor.IsAadUserType/Descriptor.IsAadGroupType) |
| isContainer | boolean | Deprecated - Can be inferred from the subject type of the descriptor (Descriptor.IsGroupType) |
| isDeletedInOrigin | boolean |  |
| profileUrl | string | Deprecated - not in use in most preexisting implementations of ToIdentityRef |
| uniqueName | string | Deprecated - use Domain+PrincipalName instead |
| url | string | This url is the full route to the source resource of this graph subject. |

### PropertiesCollection

Object

The class represents a property bag as a collection of key-value pairs. Values of all primitive types (any type with a `TypeCode != TypeCode.Object`) except for `DBNull` are accepted. Values of type Byte[], Int32, Double, DateType and String preserve their type, other primitives are retuned as a String. Byte[] expected as base64 encoded string.

| Name | Type | Description |
| --- | --- | --- |
| count | integer (int32) | The count of properties in the collection. |
| item | object |  |
| keys | string[] | The set of keys in the collection. |
| values | string[] | The set of values in the collection. |

### ReferenceLinks

Object

The class to represent a collection of REST reference links.

| Name | Type | Description |
| --- | --- | --- |
| links | object | The readonly view of the links. Because Reference links are readonly, we only want to expose them as read only. |

---
