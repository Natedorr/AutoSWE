# Runs - List - REST API (Azure DevOps Pipelines)

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/pipelines/runs/list?view=azure-devops-rest-7.1


# Runs - List

- Service:
    - Pipelines

- API Version:
    - 7.1

Gets top 10000 runs for a particular pipeline.

```http
GET https://dev.azure.com/{organization}/{project}/_apis/pipelines/{pipelineId}/runs?api-version=7.1
```

## URI Parameters

| Name | In | Required | Type | Description |
| --- | --- | --- | --- | --- |
| organization | path | True | string | The name of the Azure DevOps organization. |
| pipelineId | path | True | integer (int32) | The pipeline id |
| project | path | True | string | Project ID or project name |
| api-version | query | True | string | Version of the API to use. This should be set to '7.1' to use this version of the api. |

## Responses

| Name | Type | Description |
| --- | --- | --- |
| 200 OK | Run[] | successful operation |

## Security

### oauth2

Type:  oauth2Flow:  accessCodeAuthorization URL:  https://app.vssps.visualstudio.com/oauth2/authorize&response\_type=AssertionToken URL:  https://app.vssps.visualstudio.com/oauth2/token?client\_assertion\_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer&grant\_type=urn:ietf:params:oauth:grant-type:jwt-bearer

#### Scopes

| Name | Description |
| --- | --- |
| vso.build | Grants the ability to access build artifacts, including build results, definitions, and requests, and the ability to receive notifications about build events via service hooks. |

## Definitions

| Name | Description |
| --- | --- |
| Container |  |
| ContainerResource |  |
| PipelineReference | A reference to a Pipeline. |
| PipelineResource |  |
| ReferenceLinks | The class to represent a collection of REST reference links. |
| Repository |  |
| RepositoryResource |  |
| RepositoryType |  |
| Run |  |
| RunResources |  |
| RunResult |  |
| RunState |  |
| Variable |  |

### Container

Object

| Name | Type | Description |
| --- | --- | --- |
| environment | object |  |
| image | string |  |
| mapDockerSocket | boolean |  |
| options | string |  |
| ports | string[] |  |
| volumes | string[] |  |

### ContainerResource

Object

| Name | Type | Description |
| --- | --- | --- |
| container | Container |  |

### PipelineReference

Object

A reference to a Pipeline.

| Name | Type | Description |
| --- | --- | --- |
| folder | string | Pipeline folder |
| id | integer (int32) | Pipeline ID |
| name | string | Pipeline name |
| revision | integer (int32) | Revision number |
| url | string |  |

### PipelineResource

Object

| Name | Type | Description |
| --- | --- | --- |
| pipeline | PipelineReference | A reference to a Pipeline. |
| version | string |  |

### ReferenceLinks

Object

The class to represent a collection of REST reference links.

| Name | Type | Description |
| --- | --- | --- |
| links | object | The readonly view of the links. Because Reference links are readonly, we only want to expose them as read only. |

### Repository

Object

| Name | Type | Description |
| --- | --- | --- |
| type | RepositoryType |  |

### RepositoryResource

Object

| Name | Type | Description |
| --- | --- | --- |
| refName | string |  |
| repository | Repository |  |
| version | string |  |

### RepositoryType

Enumeration

| Value | Description |
| --- | --- |
| unknown |  |
| gitHub |  |
| azureReposGit |  |
| gitHubEnterprise |  |
| azureReposGitHyphenated |  |

### Run

Object

| Name | Type | Description |
| --- | --- | --- |
| \_links | ReferenceLinks | The class to represent a collection of REST reference links. |
| createdDate | string (date-time) |  |
| finalYaml | string |  |
| finishedDate | string (date-time) |  |
| id | integer (int32) |  |
| name | string |  |
| pipeline | PipelineReference | A reference to a Pipeline. |
| resources | RunResources |  |
| result | RunResult |  |
| state | RunState |  |
| templateParameters | object |  |
| url | string |  |
| variables | &lt;string, Variable&gt; |  |

### RunResources

Object

| Name | Type | Description |
| --- | --- | --- |
| containers | &lt;string, ContainerResource&gt; |  |
| pipelines | &lt;string, PipelineResource&gt; |  |
| repositories | &lt;string, RepositoryResource&gt; |  |

### RunResult

Enumeration

| Value | Description |
| --- | --- |
| unknown |  |
| succeeded |  |
| failed |  |
| canceled |  |

### RunState

Enumeration

| Value | Description |
| --- | --- |
| unknown |  |
| inProgress |  |
| canceling |  |
| completed |  |

### Variable

Object

| Name | Type | Description |
| --- | --- | --- |
| isSecret | boolean |  |
| value | string |  |

---
