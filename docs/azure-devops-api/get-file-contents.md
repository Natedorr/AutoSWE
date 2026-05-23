# Get File Contents

> Grounding reference for Azure DevOps Git API
> Source: https://learn.microsoft.com/en-us/rest/api/azure/devops/git/items/get

---

## Get File Contents

```
GET /{organization}/{project}/_apis/git/repositories/{repositoryId}/items?path={path}&api-version=7.1
```

Get item metadata and/or content for a single file or directory in a repository. Can retrieve file contents as text, download as file, or get directory listings.

### Parameters

#### Headers

- **`Authorization`** (string) (required)
  Basic authentication with a Personal Access Token (PAT). Format: `Basic base64(:YOUR_PAT)`.

#### Path and query parameters

- **`organization`** (string) (required)
  Name of your Azure DevOps organization.

- **`project`** (string) (required)
  Project ID or project name.

- **`repositoryId`** (string) (required)
  Repository ID (GUID) or name.

- **`path`** (string) (required)
  The item path within the repository. Use `/` for the repository root.

- **`api-version`** (string) (required)
  API version. Use `7.1` for latest stable.

- **`versionDescriptor.version`** (string) (optional)
  Version string identifier. Can be a branch name (e.g., `main`), tag name (e.g., `v1.0`), or commit SHA.

- **`versionDescriptor.versionType`** (string) (optional)
  Version type. Values: `branch`, `tag`, `commit`, `changeset`.
  Default: `branch`

- **`versionDescriptor.versionOptions`** (string) (optional)
  Version options. Values: `none`, `excludeHiddenItems`, `followRenames`, `skipRenames`.

- **`includeContent`** (boolean) (optional)
  If true, includes file content in the response. For directories, returns metadata only.
  Default: `false`

- **`download`** (boolean) (optional)
  If true, returns the file as a download (Content-Disposition header). Default is `false`.

- **`$format`** (string) (optional)
  Override response format. Values: `json`, `zip`.
  Note: `zip` returns the entire directory as a compressed archive.

- **`recursionLevel`** (string) (optional)
  Recursion level for directory listings. Values: `none`, `oneLevel`, `full`.
  Default: `none`

- **`includeContentMetadata`** (boolean) (optional)
  If true, includes content metadata (encoding, size).
  Default: `false`

- **`latestProcessedChange`** (boolean) (optional)
  If true, includes the latest processed change information.
  Default: `false`

- **`scopePath`** (string) (optional)
  Path scope (for multi-repo queries). Default is `null`.

- **`resolveLfs`** (boolean) (optional)
  If true, resolves Git LFS pointer files to return actual content.
  Default: `false`

- **`sanitize`** (boolean) (optional)
  If true, sanitizes SVG files and returns them as images.
  Default: `false`

### HTTP response status codes

- **200** — OK. Returns the file content or metadata.
- **304** — Not Modified. File hasn't changed since last request (if using If-Modified-Since).
- **401** — Unauthorized. Invalid or missing PAT.
- **403** — Forbidden. PAT lacks required scope or repo access.
- **404** — Not Found. Organization, project, repository, file, or version not found.

### Response schema (Status: 200)

When `includeContent=true`:

- `path`: required, string — Path to the item.
- `gitSha1`: string — SHA-1 hash of the item content.
- `size`: integer — File size in bytes.
- `content`: string — Base64-encoded file content (when `includeContent=true`).
- `contentType`: string — Content type (`blob`, `tree`, `symlink`).
- `encoding`: string — Content encoding (e.g., `base64`).
- `url`: string — REST API URL for this item.
- `downloadUrl`: string — URL to download the item.
- `items`: array — Child items when requesting a directory (when `recursionLevel` > `none`).

When `download=true`:

Returns the raw file content as a stream (no JSON wrapper).

### Code examples

#### Example: Get file contents as base64

**Request:**

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/items?path=/src/index.ts&versionDescriptor.version=main&includeContent=true&api-version=7.1"
```

**Response (Status: 200):**

```json
{
  "path": "/src/index.ts",
  "gitSha1": "a1b2c3d4e5f6789012345678901234567890abcd",
  "size": 1234,
  "content": "aW1wb3J0IHsgTW9kZWwgZnJvbSAnZmFrZSc7Cg==",
  "contentType": "blob",
  "encoding": "base64",
  "url": "https://dev.azure.com/myorg/_apis/git/repositories/my-repo/items?path=/src/index.ts",
  "downloadUrl": "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/items/src/index.ts?version=GBmain&download=true"
}
```

#### Example: Download file directly

```bash
curl -u ":$ADO_PAT" \
  -o package.json \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/items?path=/package.json&versionDescriptor.version=main&download=true&api-version=7.1"
```

#### Example: Get directory listing

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/items?path=/src&recursionLevel=oneLevel&api-version=7.1"
```

#### Example: Get file from a specific commit

```bash
curl -u ":$ADO_PAT" \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/items?path=/README.md&versionDescriptor.version=d7f4a1b2c3e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9&versionDescriptor.versionType=commit&includeContent=true&api-version=7.1"
```

#### Example: Download entire directory as zip

```bash
curl -u ":$ADO_PAT" \
  -o src.zip \
  "https://dev.azure.com/myorg/myproject/_apis/git/repositories/my-repo/items?path=/src&\$format=zip&api-version=7.1"
```

#### Python Example — Decode file content

```python
import requests
import base64

def get_file_contents(org, project, repo, path, branch="main", pat="YOUR_PAT"):
    """
    Get file contents from a repository.
    
    :param org: Azure DevOps organization name
    :param project: Project name
    :param repo: Repository name or ID
    :param path: File path in the repository
    :param branch: Branch name (default: main)
    :param pat: Personal Access Token
    :return: File content as string
    """
    url = f"https://dev.azure.com/{org}/{project}/_apis/git/repositories/{repo}/items"
    
    response = requests.get(
        url, auth=("", pat),
        params={
            "path": path,
            "versionDescriptor.version": branch,
            "versionDescriptor.versionType": "branch",
            "includeContent": "true",
            "api-version": "7.1"
        }
    )
    response.raise_for_status()
    data = response.json()
    
    if data.get("contentType") == "blob":
        return base64.b64decode(data["content"]).decode("utf-8")
    return None  # Directory, not a file

# Usage
content = get_file_contents("myorg", "myproject", "my-repo", "/package.json")
print(content)
```

### Common Pitfalls

1. **Content is base64-encoded** — File content comes as base64 when `includeContent=true`. You must decode it.
2. **Path must start with `/`** — The `path` parameter should begin with a forward slash: `/src/index.ts`, not `src/index.ts`.
3. **Directories don't have content** — `includeContent=true` only works for files. For directories, use `recursionLevel` to list children.
4. **`$format` needs escaping in bash** — In bash, `$format` is interpreted as a variable. Escape it: `\$format=zip` or quote the URL.
5. **Large files** — Very large files can cause timeout issues. Use `download=true` to get a direct stream instead of base64 JSON.
6. **Git LFS files** — By default, LFS files return pointer files. Set `resolveLfs=true` to get actual content (may have size limits).
7. **Version defaults to HEAD of default branch** — If you don't specify `versionDescriptor.version`, it uses the default branch HEAD.
