# Builds - List - REST API (Azure DevOps Build)

Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/build/builds/list?view=azure-devops-rest-7.1


# Builds - List

- Service:
    - Build

- API Version:
    - 7.1

Gets a list of builds.

```http
GET https://dev.azure.com/{organization}/{project}/_apis/build/builds?api-version=7.1
```

 With optional parameters: 

```http
GET https://dev.azure.com/{organization}/{project}/_apis/build/builds?definitions={definitions}&queues={queues}&buildNumber={buildNumber}&minTime={minTime}&maxTime={maxTime}&requestedFor={requestedFor}&reasonFilter={reasonFilter}&statusFilter={statusFilter}&resultFilter={resultFilter}&tagFilters={tagFilters}&properties={properties}&$top={$top}&continuationToken={continuationToken}&maxBuildsPerDefinition={maxBuildsPerDefinition}&deletedFilter={deletedFilter}&queryOrder={queryOrder}&branchName={branchName}&buildIds={buildIds}&repositoryId={repositoryId}&repositoryType={repositoryType}&api-version=7.1
```

## URI Parameters

| Name | In | Required | Type | Description |
| --- | --- | --- | --- | --- |
| organization | path | True | string | The name of the Azure DevOps organization. |
| project | path | True | string | Project ID or project name |
| api-version | query | True | string | Version of the API to use. This should be set to '7.1' to use this version of the api. |
| $top | query |  | integer (int32) | The maximum number of builds to return. |
| branchName | query |  | string | If specified, filters to builds that built branches that built this branch. |
| buildIds | query |  | string (array (int32)) | A comma-delimited list that specifies the IDs of builds to retrieve. |
| buildNumber | query |  | string | If specified, filters to builds that match this build number. Append \* to do a prefix search. |
| continuationToken | query |  | string | A continuation token, returned by a previous call to this method, that can be used to return the next set of builds. |
| definitions | query |  | string (array (int32)) | A comma-delimited list of definition IDs. If specified, filters to builds for these definitions. |
| deletedFilter | query |  | QueryDeletedOption | Indicates whether to exclude, include, or only return deleted builds. |
| maxBuildsPerDefinition | query |  | integer (int32) | The maximum number of builds to return per definition. |
| maxTime | query |  | string (date-time) | If specified, filters to builds that finished/started/queued before this date based on the queryOrder specified. |
| minTime | query |  | string (date-time) | If specified, filters to builds that finished/started/queued after this date based on the queryOrder specified. |
| properties | query |  | string (array (string)) | A comma-delimited list of properties to retrieve. |
| queryOrder | query |  | BuildQueryOrder | The order in which builds should be returned. |
| queues | query |  | string (array (int32)) | A comma-delimited list of queue IDs. If specified, filters to builds that ran against these queues. |
| reasonFilter | query |  | BuildReason | If specified, filters to builds that match this reason. |
| repositoryId | query |  | string | If specified, filters to builds that built from this repository. |
| repositoryType | query |  | string | If specified, filters to builds that built from repositories of this type. |
| requestedFor | query |  | string | If specified, filters to builds requested for the specified user. |
| resultFilter | query |  | BuildResult | If specified, filters to builds that match this result. |
| statusFilter | query |  | BuildStatus | If specified, filters to builds that match this status. |
| tagFilters | query |  | string (array (string)) | A comma-delimited list of tags. If specified, filters to builds that have the specified tags. |

## Responses

| Name | Type | Description |
| --- | --- | --- |
| 200 OK | Build[] | successful operation |

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
| AgentPoolQueue | Represents a queue for running builds. |
| AgentSpecification | Specification of the agent defined by the pool provider. |
| Build | Data representation of a build. |
| BuildController |  |
| BuildLogReference | Represents a reference to a build log. |
| BuildQueryOrder | The order in which builds should be returned. |
| BuildReason | The reason that the build was created. |
| BuildRepository | Represents a repository used by a build definition. |
| BuildRequestValidationResult | Represents the result of validating a build request. |
| BuildResult | The build result. |
| BuildStatus | The build status. |
| ControllerStatus | The status of the controller. |
| DefinitionQueueStatus | A value that indicates whether builds can be queued against this definition. |
| DefinitionReference | Represents a reference to a definition. |
| DefinitionType | The type of the definition. |
| Demand | Represents a demand used by a definition or build. |
| IdentityRef |  |
| ProjectState | Project state. |
| ProjectVisibility | Project visibility. |
| PropertiesCollection | The class represents a property bag as a collection of key-value pairs. Values of all primitive types (any type with a `TypeCode != TypeCode.Object`) except for `DBNull` are accepted. Values of type Byte[], Int32, Double, DateType and String preserve their type, other primitives are retuned as a String. Byte[] expected as base64 encoded string. |
| QueryDeletedOption | Indicates whether to exclude, include, or only return deleted builds. |
| QueueOptions | Additional options for queueing the build. |
| QueuePriority | The build's priority. |
| ReferenceLinks | The class to represent a collection of REST reference links. |
| TaskAgentPoolReference | Represents a reference to an agent pool. |
| TaskOrchestrationPlanReference | Represents a reference to an orchestration plan. |
| TeamProjectReference | Represents a shallow reference to a TeamProject. |
| ValidationResult | The result. |

### AgentPoolQueue

Object

Represents a queue for running builds.

| Name | Type | Description |
| --- | --- | --- |
| \_links | ReferenceLinks | The class to represent a collection of REST reference links. |
| id | integer (int32) | The ID of the queue. |
| name | string | The name of the queue. |
| pool | TaskAgentPoolReference | The pool used by this queue. |
| url | string | The full http link to the resource. |

### AgentSpecification

Object

Specification of the agent defined by the pool provider.

| Name | Type | Description |
| --- | --- | --- |
| identifier | string | Agent specification unique identifier. |

### Build

Object

Data representation of a build.

| Name | Type | Description |
| --- | --- | --- |
| \_links | ReferenceLinks | The class to represent a collection of REST reference links. |
| agentSpecification | AgentSpecification | The agent specification for the build. |
| appendCommitMessageToRunName | boolean | Append Commit Message To BuildNumber in UI. |
| buildNumber | string | The build number/name of the build. |
| buildNumberRevision | integer (int32) | The build number revision. |
| controller | BuildController | The build controller. This is only set if the definition type is Xaml. |
| definition | DefinitionReference | The definition associated with the build. |
| deleted | boolean | Indicates whether the build has been deleted. |
| deletedBy | IdentityRef | The identity of the process or person that deleted the build. |
| deletedDate | string (date-time) | The date the build was deleted. |
| deletedReason | string | The description of how the build was deleted. |
| demands | Demand[] | A list of demands that represents the agent capabilities required by this build. |
| finishTime | string (date-time) | The time that the build was completed. |
| id | integer (int32) | The ID of the build. |
| lastChangedBy | IdentityRef | The identity representing the process or person that last changed the build. |
| lastChangedDate | string (date-time) | The date the build was last changed. |
| logs | BuildLogReference | Information about the build logs. |
| orchestrationPlan | TaskOrchestrationPlanReference | The orchestration plan for the build. |
| parameters | string | The parameters for the build. |
| plans | TaskOrchestrationPlanReference[] | Orchestration plans associated with the build (build, cleanup) |
| priority | QueuePriority | The build's priority. |
| project | TeamProjectReference | The team project. |
| properties | PropertiesCollection | The class represents a property bag as a collection of key-value pairs. Values of all primitive types (any type with a `TypeCode != TypeCode.Object`) except for `DBNull` are accepted. Values of type Byte[], Int32, Double, DateType and String preserve their type, other primitives are retuned as a String. Byte[] expected as base64 encoded string. |
| quality | string | The quality of the xaml build (good, bad, etc.) |
| queue | AgentPoolQueue | The queue. This is only set if the definition type is Build. WARNING: this field is deprecated and does not corresponds to the jobs queues. |
| queueOptions | QueueOptions | Additional options for queueing the build. |
| queuePosition | integer (int32) | The current position of the build in the queue. |
| queueTime | string (date-time) | The time that the build was queued. |
| reason | BuildReason | The reason that the build was created. |
| repository | BuildRepository | The repository. |
| requestedBy | IdentityRef | The identity that queued the build. |
| requestedFor | IdentityRef | The identity on whose behalf the build was queued. |
| result | BuildResult | The build result. |
| retainedByRelease | boolean | Indicates whether the build is retained by a release. |
| sourceBranch | string | The source branch. |
| sourceVersion | string | The source version. |
| startTime | string (date-time) | The time that the build was started. |
| status | BuildStatus | The status of the build. |
| tags | string[] |  |
| templateParameters | object | Parameters to template expression evaluation |
| triggerInfo | object | Sourceprovider-specific information about what triggered the build |
| triggeredByBuild | Build | The build that triggered this build via a Build completion trigger. |
| uri | string | The URI of the build. |
| url | string | The REST URL of the build. |
| validationResults | BuildRequestValidationResult[] | Represents the result of validating a build request. |

### BuildController

Object

| Name | Type | Description |
| --- | --- | --- |
| \_links | ReferenceLinks | The class to represent a collection of REST reference links. |
| createdDate | string (date-time) | The date the controller was created. |
| description | string | The description of the controller. |
| enabled | boolean | Indicates whether the controller is enabled. |
| id | integer (int32) | Id of the resource |
| name | string | Name of the linked resource (definition name, controller name, etc.) |
| status | ControllerStatus | The status of the controller. |
| updatedDate | string (date-time) | The date the controller was last updated. |
| uri | string | The controller's URI. |
| url | string | Full http link to the resource |

### BuildLogReference

Object

Represents a reference to a build log.

| Name | Type | Description |
| --- | --- | --- |
| id | integer (int32) | The ID of the log. |
| type | string | The type of the log location. |
| url | string | A full link to the log resource. |

### BuildQueryOrder

Enumeration

The order in which builds should be returned.

| Value | Description |
| --- | --- |
| finishTimeAscending | Order by finish time ascending. |
| finishTimeDescending | Order by finish time descending. |
| queueTimeDescending | Order by queue time descending. |
| queueTimeAscending | Order by queue time ascending. |
| startTimeDescending | Order by start time descending. |
| startTimeAscending | Order by start time ascending. |

### BuildReason

Enumeration

The reason that the build was created.

| Value | Description |
| --- | --- |
| none | No reason. This value should not be used. |
| manual | The build was started manually. |
| individualCI | The build was started for the trigger TriggerType.ContinuousIntegration. |
| batchedCI | The build was started for the trigger TriggerType.BatchedContinuousIntegration. |
| schedule | The build was started for the trigger TriggerType.Schedule. |
| scheduleForced | The build was started for the trigger TriggerType.ScheduleForced. |
| userCreated | The build was created by a user. |
| validateShelveset | The build was started manually for private validation. |
| checkInShelveset | The build was started for the trigger ContinuousIntegrationType.Gated. |
| pullRequest | The build was started by a pull request. Added in resource version 3. |
| buildCompletion | The build was started when another build completed. |
| resourceTrigger | The build was started when resources in pipeline triggered it |
| triggered | The build was triggered for retention policy purposes. |
| all | All reasons. |

### BuildRepository

Object

Represents a repository used by a build definition.

| Name | Type | Description |
| --- | --- | --- |
| checkoutSubmodules | boolean | Indicates whether to checkout submodules. |
| clean | string | Indicates whether to clean the target folder when getting code from the repository. |
| defaultBranch | string | The name of the default branch. |
| id | string | The ID of the repository. |
| name | string | The friendly name of the repository. |
| properties | object |  |
| rootFolder | string | The root folder. |
| type | string | The type of the repository. |
| url | string | The URL of the repository. |

### BuildRequestValidationResult

Object

Represents the result of validating a build request.

| Name | Type | Description |
| --- | --- | --- |
| message | string | The message associated with the result. |
| result | ValidationResult | The result. |

### BuildResult

Enumeration

The build result.

| Value | Description |
| --- | --- |
| none | No result |
| succeeded | The build completed successfully. |
| partiallySucceeded | The build completed compilation successfully but had other errors. |
| failed | The build completed unsuccessfully. |
| canceled | The build was canceled before starting. |

### BuildStatus

Enumeration

The build status.

| Value | Description |
| --- | --- |
| none | No status. |
| inProgress | The build is currently in progress. |
| completed | The build has completed. |
| cancelling | The build is cancelling |
| postponed | The build is inactive in the queue. |
| notStarted | The build has not yet started. |
| all | All status. |

### ControllerStatus

Enumeration

The status of the controller.

| Value | Description |
| --- | --- |
| unavailable | Indicates that the build controller cannot be contacted. |
| available | Indicates that the build controller is currently available. |
| offline | Indicates that the build controller has taken itself offline. |

### DefinitionQueueStatus

Enumeration

A value that indicates whether builds can be queued against this definition.

| Value | Description |
| --- | --- |
| enabled | When enabled the definition queue allows builds to be queued by users, the system will queue scheduled, gated and continuous integration builds, and the queued builds will be started by the system. |
| paused | When paused the definition queue allows builds to be queued by users and the system will queue scheduled, gated and continuous integration builds. Builds in the queue will not be started by the system. |
| disabled | When disabled the definition queue will not allow builds to be queued by users and the system will not queue scheduled, gated or continuous integration builds. Builds already in the queue will not be started by the system. |

### DefinitionReference

Object

Represents a reference to a definition.

| Name | Type | Description |
| --- | --- | --- |
| createdDate | string (date-time) | The date this version of the definition was created. |
| id | integer (int32) | The ID of the referenced definition. |
| name | string | The name of the referenced definition. |
| path | string | The folder path of the definition. |
| project | TeamProjectReference | A reference to the project. |
| queueStatus | DefinitionQueueStatus | A value that indicates whether builds can be queued against this definition. |
| revision | integer (int32) | The definition revision number. |
| type | DefinitionType | The type of the definition. |
| uri | string | The definition's URI. |
| url | string | The REST URL of the definition. |

### DefinitionType

Enumeration

The type of the definition.

| Value | Description |
| --- | --- |
| xaml |  |
| build |  |

### Demand

Object

Represents a demand used by a definition or build.

| Name | Type | Description |
| --- | --- | --- |
| name | string | The name of the capability referenced by the demand. |
| value | string | The demanded value. |

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

### ProjectState

Enumeration

Project state.

| Value | Description |
| --- | --- |
| deleting | Project is in the process of being deleted. |
| new | Project is in the process of being created. |
| wellFormed | Project is completely created and ready to use. |
| createPending | Project has been queued for creation, but the process has not yet started. |
| all | All projects regardless of state except Deleted. |
| unchanged | Project has not been changed. |
| deleted | Project has been deleted. |

### ProjectVisibility

Enumeration

Project visibility.

| Value | Description |
| --- | --- |
| private | The project is only visible to users with explicit access. |
| public | The project is visible to all. |

### PropertiesCollection

Object

The class represents a property bag as a collection of key-value pairs. Values of all primitive types (any type with a `TypeCode != TypeCode.Object`) except for `DBNull` are accepted. Values of type Byte[], Int32, Double, DateType and String preserve their type, other primitives are retuned as a String. Byte[] expected as base64 encoded string.

| Name | Type | Description |
| --- | --- | --- |
| count | integer (int32) | The count of properties in the collection. |
| item | object |  |
| keys | string[] | The set of keys in the collection. |
| values | string[] | The set of values in the collection. |

### QueryDeletedOption

Enumeration

Indicates whether to exclude, include, or only return deleted builds.

| Value | Description |
| --- | --- |
| excludeDeleted | Include only non-deleted builds. |
| includeDeleted | Include deleted and non-deleted builds. |
| onlyDeleted | Include only deleted builds. |

### QueueOptions

Enumeration

Additional options for queueing the build.

| Value | Description |
| --- | --- |
| none | No queue options |
| doNotRun | Create a plan Id for the build, do not run it |

### QueuePriority

Enumeration

The build's priority.

| Value | Description |
| --- | --- |
| low | Low priority. |
| belowNormal | Below normal priority. |
| normal | Normal priority. |
| aboveNormal | Above normal priority. |
| high | High priority. |

### ReferenceLinks

Object

The class to represent a collection of REST reference links.

| Name | Type | Description |
| --- | --- | --- |
| links | object | The readonly view of the links. Because Reference links are readonly, we only want to expose them as read only. |

### TaskAgentPoolReference

Object

Represents a reference to an agent pool.

| Name | Type | Description |
| --- | --- | --- |
| id | integer (int32) | The pool ID. |
| isHosted | boolean | A value indicating whether or not this pool is managed by the service. |
| name | string | The pool name. |

### TaskOrchestrationPlanReference

Object

Represents a reference to an orchestration plan.

| Name | Type | Description |
| --- | --- | --- |
| orchestrationType | integer (int32) | The type of the plan. |
| planId | string (uuid) | The ID of the plan. |

### TeamProjectReference

Object

Represents a shallow reference to a TeamProject.

| Name | Type | Description |
| --- | --- | --- |
| abbreviation | string | Project abbreviation. |
| defaultTeamImageUrl | string | Url to default team identity image. |
| description | string | The project's description (if any). |
| id | string (uuid) | Project identifier. |
| lastUpdateTime | string (date-time) | Project last update time. |
| name | string | Project name. |
| revision | integer (int64) | Project revision. |
| state | ProjectState | Project state. |
| url | string | Url to the full version of the object. |
| visibility | ProjectVisibility | Project visibility. |

### ValidationResult

Enumeration

The result.

| Value | Description |
| --- | --- |
| ok |  |
| warning |  |
| error |  |

---
