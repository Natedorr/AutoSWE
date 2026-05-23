# Get Current User

> Grounding reference for Azure DevOps Profile API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/profile/profiles/get

---

## Get Current User Profile

```
GET https://app.vssps.visualstudio.com/_apis/profile/profiles/me?api-version=7.1
```

Get the profile of the currently authenticated user (the user associated with the PAT). Uses `me` as the profile ID.

### Important

This endpoint uses a different base URL than most Azure DevOps APIs:
- Base: `https://app.vssps.visualstudio.com` (Profile service)
- NOT `https://dev.azure.com/{org}`

### Parameters

#### Headers

- **`Authorization`** (string) (required)
  Basic authentication with a Personal Access Token (PAT). Format: `Basic base64(:YOUR_PAT)`.

#### Path and query parameters

- **`id`** (string) (required)
  Always `me` for the current user. Can also be a user GUID for another user.

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`details`** (boolean) (optional)
  Return public profile information such as display name, email address, country.
  Default: `false`

- **`withAttributes`** (boolean) (optional)
  If true, gets profile attributes. Requires `partition` parameter.

- **`partition`** (string) (optional)
  The partition (named group) of attributes to return. Required with `withAttributes`.

- **`coreAttributes`** (string) (optional)
  Comma-delimited list of core profile attributes: `Email`, `Avatar`, `DisplayName`, `ContactWithOffers`.

### HTTP response status codes

- **200** — OK. Returns the user's profile object.
- **401** — Unauthorized. Invalid or missing PAT.
- **403** — Forbidden. PAT lacks profile scope.
- **404** — Not Found. User profile not found.

### Response schema (Status: 200)

- `displayName`: string — User's display name.
- `publicAlias`: string — Public alias (GUID-based).
- `emailAddress`: string — User's email address.
- `coreRevision`: integer — Core profile revision number.
- `timeStamp`: string, format: date-time — Last update timestamp.
- `id`: required, string — User's profile GUID.
- `revision`: integer — Profile revision number.
- `attributes`: object — Profile attributes (when `withAttributes=true`).

### Code examples

#### Example: Get current user profile

**Request:**

```bash
curl -u ":$ADO_PAT" \
  "https://app.vssps.visualstudio.com/_apis/profile/profiles/me?api-version=7.1"
```

**Response (Status: 200):**

```json
{
  "displayName": "John Doe",
  "publicAlias": "d6245f20-2af8-44f4-9451-8107cb2767db",
  "emailAddress": "john.doe@example.com",
  "coreRevision": 1647,
  "timeStamp": "2014-05-12T22:23:07.727+00:00",
  "id": "d6245f20-2af8-44f4-9451-8107cb2767db",
  "revision": 1647
}
```

#### Example: Get profile with details

```bash
curl -u ":$ADO_PAT" \
  "https://app.vssps.visualstudio.com/_apis/profile/profiles/me?details=true&api-version=7.1"
```

#### Python Example

```python
import requests

def get_current_user(pat):
    """
    Get the current authenticated user's profile.
    
    :param pat: Personal Access Token
    :return: User profile dict
    """
    url = "https://app.vssps.visualstudio.com/_apis/profile/profiles/me"
    
    response = requests.get(
        url, auth=("", pat),
        params={"api-version": "7.1", "details": "true"}
    )
    response.raise_for_status()
    return response.json()

# Usage
user = get_current_user("YOUR_PAT")
print(f"User: {user['displayName']} ({user['emailAddress']})")
```

### Common Pitfalls

1. **Different base URL** — This endpoint uses `app.vssps.visualstudio.com`, NOT `dev.azure.com`. This is a common source of errors.
2. **PAT requires profile scope** — The PAT must have profile read scope, which is not included in all PAT scopes.
3. **`me` keyword** — Use `me` to get the current user's profile. Can also use a user GUID to get another user's profile.
4. **Email address may be empty** — If the user hasn't set an email in their Visual Studio profile, `emailAddress` can be empty.
5. **Not org-scoped** — This is a global profile endpoint. It works the same regardless of which org the PAT was created in.
