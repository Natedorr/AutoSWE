# Issue / Work-Item Attachment Ingestion

**Status: design doc + API investigation (2026-10-09).** Not implemented yet.
This doc records *how* attachments on issues and comments can be discovered and
downloaded per provider, with **live-tested examples** from this host
(`Natedorr/openclaw-config` issue #13 as the probe issue, public repo
`Beenda1/Hanzala-Sarfraz` #3 as the external sample).

## Problem Statement

Today autoSWE pulls only **text** from issues:

- `autoswe/harness/prompts.py` injects `Issue body:` + `Comments so far:`
  verbatim into planner/coder/reviewer prompts.
- `fetch_comments()` (both providers) grabs `body` strings only.

If a user attaches a file to an issue or a comment, autoSWE's model sees a URL
it cannot read or fetch. This doc defines how to close that gap.

## Provider 1: GitHub

### 1.1 There is no documented REST endpoint for attachments

GitHub's REST API has **no `GET .../attachments` endpoint** and no way to list
an issue's attachments programmatically. Community confirmation (cli/cli
discussion #11832, 2025): "there is still no stable, supported API to download
issue attachments in CI the way you can fetch release assets."

So the design must **discover attachment URLs from the markdown body**, then
download via the URL itself.

### 1.2 Where attachment URLs appear

When a user attaches a file in the web UI, GitHub stores it under
`https://github.com/user-attachments/assets/<uuid>` and embeds that URL in the
issue body / comment markdown, e.g.:

```markdown
![probe](https://github.com/user-attachments/assets/8a05e9fb-1ff3-411c-8990-ccd27f39cc05)
```

Fetching the issue with the default media type returns this raw markdown in
`body`. So discovery is a regex over `body` + all comment bodies:

```
https?://github\.com/user-attachments/assets/[0-9a-f-]{36}
```

**Live example** (probe issue, `Natedorr/openclaw-config#13`):

```
$ gh api repos/Natedorr/openclaw-config/issues/13 --jq .body
Testing how AutoSWE can ingest issue attachments.

![probe](https://github.com/user-attachments/assets/8a05e9fb-1ff3-411c-8990-ccd27f39cc05)
```

Comment body likewise contains the embedded URL:

```
$ gh api repos/Natedorr/openclaw-config/issues/13/comments --jq '.[] | .body'
Follow-up image (comment attachment, different asset):

![followup](https://github.com/user-attachments/assets/20419ebc-dcf3-4db7-9239-ad14ab971dec)

Also a raw link: https://github.com/user-attachments/assets/46adc667-1d23-4c1e-876a-5d4c289fe09f
```

### 1.3 Downloading the URL — two mechanisms that work

**Mechanism A — redirect-follow (works for public repos).**
A `GET` on the attachment URL with `-L` (follow redirects) returns a 302 to a
pre-signed S3 URL. No auth header needed at the redirect step; the S3 URL
carries its own `X-Amz-Signature`.

```
$ curl -sS -L -o file.png \
    "https://github.com/user-attachments/assets/b45006e0-fabd-43a6-8d81-789330c687d7"
# -> 302 to:
#    https://github-production-user-asset-6210df.s3.amazonaws.com/
#      327327092/664608870-b45006e0-...png
#      ?X-Amz-Algorithm=AWS4-HMAC-SHA256
#      &X-Amz-Credential=AKIAVC...%2F20261010%2Fus-east-1%2Fs3%2Faws4_request
#      &X-Amz-Date=20261010T041559Z
#      &X-Amz-Expires=300
#      &X-Amz-Signature=***
#      &X-Amz-SignedHeaders=host
#      &response-content-type=image/png
# HTTP 200, content-type image/png, 62433 bytes
```

Caveats observed live:
- **Private repos:** the same `GET` returns **404** even with a valid PAT
  (`Authorization: Bearer`, `Basic`, `?token=` all failed) when the
  attachment belongs to a *private* repo (`Natedorr/openclaw-config`).
  `user-attachments` URLs are served for the repo's visibility; private
  assets are not reachable via the plain redirect. (Probe repo is private;
  public sample worked anonymously.)
- The pre-signed S3 URL is **time-limited** (~300s). Fine for a one-shot
  download at task setup; not a durable link to cache.
- Filenames are **not in the URL** — the S3 key ends with a `.png`/`.jpg`
  suffix derived from the uploaded content type. If the real filename matters
  (e.g. `data.csv`), it is only recoverable from the markdown `alt` text or
  the surrounding issue text, not the URL itself.

**Mechanism B — signed JWT from `body_html` (works for private repos).**
Fetching the issue/comment with the `html+json` media type renders the body
to HTML. For attachments, GitHub renders an `<img src=...>` whose URL is a
`private-user-images.githubusercontent.com` link with a **`jwt` query param**.
That signed URL downloads the file directly (200), works anonymously, and is
the same mechanism GitHub uses to serve private-repo user content.

```
$ gh api repos/Natedorr/openclaw-config/issues/13 \
    -H "Accept: application/vnd.github.html+json" --jq .body_html
<p dir="auto">Testing how AutoSWE can ingest issue attachments.</p>
<p dir="auto"><a target="_blank" ...
  href="https://private-user-images.githubusercontent.com/185386482/
        670243970-8a05e9fb-1ff3-411c-8990-ccd27f39cc05.png
        ?jwt=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzUxMiJ9.eyJpc3MiOiJnaXRodWIuY29t...">
  <img src="https://private-user-images.githubusercontent.com/185386482/
        670243970-8a05e9fb-1ff3-411c-8990-ccd27f39cc05.png?jwt=eyJ0eXAi..."
       alt="probe" style="max-width: 100%;"></a></p>
```

```
$ curl -sS -L -o file.png \
    "https://private-user-images.githubusercontent.com/185386482/
     670243970-8a05e9fb-1ff3-411c-8990-ccd27f39cc05.png?jwt=eyJ0eXAi..."
# HTTP 200, 74 bytes
$ file file.png
file.png: PNG image data, 8 x 8, 8-bit/color RGB, non-interlaid
```

Decoding the `jwt` (base64url of the payload segment) shows it is a signed
token wrapping a pre-signed S3 request:

```json
{
 "iss": "github.com",
 "aud": "raw.githubusercontent.com",
 "key": "key5",
 "exp": 1791606018,
 "nbf": 1791605718,
 "path": "/185386482/670243970-8a05e9fb-....png?X-Amz-Algorithm=...&X-Amz-Expires=300&..."
}
```

The `path` suffix (`response-content-type=image/png`) reveals the stored
content type. Note the JWT also has an `exp` — these signed URLs are
short-lived (~300s), so **fetch and download in the same operation**; do not
persist the signed URL.

### 1.4 Which mechanism to use (recommendation)

| Scenario | Mechanism |
|----------|-----------|
| Public repo, attachment in issue/comment body | **A** (redirect-follow) — simplest, no extra API call |
| Private repo (e.g. any internal autoSWE target) | **B** (body_html signed JWT) |
| Need the filename | Neither gives it from the URL; use markdown `alt` text or issue prose |

Recommended implementation: try **A** first (`GET -L`); if it returns 404,
fall back to **B** (re-fetch the containing body with `html+json`, extract the
`private-user-images...?jwt=` URL, download). Both are best-effort and must
never hard-fail the task — a missing attachment is a warning, not an error.

### 1.5 Uploading (out of scope for autoSWE, but documented)

There is **no documented REST API to upload** an attachment to an issue. The
only working path found (community-documented) is an **undocumented**
`uploads.github.com` endpoint, which accepts **images only** (jpg/png/gif/webp
tested OK; csv/pdf/zip/txt all rejected with "content_type not allowed"):

```
# repo_id from: gh api repos/OWNER/REPO --jq .id
$ curl -sS \
  "https://uploads.github.com/user-attachments/assets?name=probe.png&content_type=image/png&repository_id=1192331190" \
  -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" \
  --data-binary @probe.png
# -> {"url":"https://github.com/user-attachments/assets/8a05e9fb-..."}
```

The returned URL is then embedded in the issue/comment markdown. Because this
endpoint is undocumented and **image-only**, autoSWE should **not** rely on it
for uploading. The ingestion design (above) assumes attachments were created
in the web UI.

### 1.6 Non-image files (CSV, PDF, log, etc.)

GitHub's attachment system accepts any file type *from the web UI* (the
image-only restriction is only on the undocumented upload endpoint). So a CSV
or PDF attached in the web UI produces the same
`github.com/user-attachments/assets/<uuid>` URL and is downloadable via
Mechanism A/B. The only wrinkle: the S3 key's file extension reflects the
*stored* content type, so for a `.csv` the redirect target may end in a
non-CSV extension. The ingester should therefore **not trust the URL
extension** for the on-disk filename; it should use the markdown context
(alt text / nearby filename mention) or fall back to a generic
`attachment-<n>.<guessed-ext>`.

**Content-type detection** is the robust approach: download the bytes, sniff
the magic bytes (`image/png`, `image/jpeg`, `text/csv` vs binary), and name
the file accordingly.

## Provider 2: Azure DevOps

Azure has a **first-class, documented** attachments API — this is easier than
GitHub.

### 2.1 Discovering attachments on a work item

A work item's attachments are exposed as **relations** when fetched with
`$expand=all` (which autoSWE's Azure tracker already does —
`autoswe/providers/azure/tracker.py:223-224`). Each attachment appears as a
relation of type `attachment`:

```
GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?expand=all
```

Response (excerpt):

```json
{
  "id": 434,
  "relations": [
    {
      "rel": "AttachedFile",
      "url": "https://dev.azure.com/{org}/{project}/_apis/wit/attachments/{id}",
      "attributes": {
        "name": "failing-input.csv",
        "size": 1234
      }
    }
  ]
}
```

So discovery = parse `relations[]` where `rel == "AttachedFile"`; the
`url` is the download URL and `attributes.name` is the **real filename**
(unlike GitHub, where the name is not in the URL).

### 2.2 Downloading

```
GET https://dev.azure.com/{org}/{project}/_apis/wit/attachments/{id}?api-version=7.1
Authorization: Basic base64(:{PAT})
```

Returns the raw file bytes. Reference:
`learn.microsoft.com/en-us/rest/api/azure/devops/wit/attachments/get`
(view `azure-devops-rest-7.1`).

Concrete curl (PAT auth, matching autoSWE's existing Basic-auth header in
`autoswe/providers/azure/api.py:81`):

```
$ curl -sS -o failing-input.csv \
  "https://dev.azure.com/{org}/{project}/_apis/wit/attachments/{id}?api-version=7.1" \
  -H "Authorization: Basic $(echo -n ':PAT' | base64)"
# -> raw bytes of the attachment
```

### 2.3 Uploading (for completeness)

```
POST https://dev.azure.com/{org}/{project}/_apis/wit/attachments?fileName=data.csv&uploadType=attachment&api-version=7.1
Authorization: Basic base64(:{PAT})
Content-Type: application/octet-stream
# body: raw file bytes
# -> 201, Location header is the attachment URL
```

Reference:
`learn.microsoft.com/en-us/rest/api/azure/devops/wit/attachments/create`.

## Proposed autoSWE Design (cross-provider)

A small, provider-agnostic attachment layer that runs at **task setup**
(before the planner/coder runs), in the worktree:

1. **Discover** — GitHub: regex `user-attachments/assets/<uuid>` over issue
   body + all comment bodies (also scan `body_html` for the signed
   `private-user-images` URL as the private-repo fallback). Azure: parse
   `relations[]` with `rel == "AttachedFile"`.
2. **Download** — GitHub: try redirect-follow (Mechanism A), fall back to
   signed JWT (Mechanism B). Azure: `GET _apis/wit/attachments/{id}`.
   All best-effort: a failure logs a warning and continues.
3. **Name & store** — prefer the provider-supplied filename (Azure
   `attributes.name`); otherwise sniff content-type / use markdown alt text /
   fall back to `attachment-<n>.<ext>`. Store under
   `<worktree>/data/attachments/<issue>#/<filename>` (ephemeral, gitignored —
   **not** committed by default).
4. **Manifest** — append to the planner/coder/reviewer prompt a block:

   ```
   Attached files available locally (relative to worktree):
   - data/attachments/123/failing-input.csv  (text/csv, 1234 bytes)
   - data/attachments/123/screenshot.png     (image/png, 62433 bytes)
   ```

   so the model knows the files are on disk and can `read`/`process` them.
   CSV/text are fully ingested by the backend; images are viewable by
   claude_code-style backends.
5. **Config flag** — `attachments.enabled` (default `true`), plus optional
   `attachments.commit` (default `false`) to commit them into the branch if a
   fix references them.

## Open Questions

1. **Private-repo GitHub uploads:** Mechanism B (body_html JWT) is the only
   confirmed path for private repos. Needs a live test on a private repo with
   a *web-UI-attached* file (this host's probe used the upload endpoint, which
   is image-only; confirm a private CSV attached in the UI is reachable).
2. **Filename for GitHub attachments:** no reliable source in the URL. Decide
   the fallback strategy (alt text vs content-type sniff vs `attachment-N`).
3. **Security:** attachments are untrusted user input. The ingester must
   sandbox them (never execute, size cap, path-traversal guard on the
   provider-supplied filename — Azure `attributes.name` is attacker-influenced).
4. **Size cap:** cap each attachment (e.g. 10 MB) and total per issue to
   avoid blowing up the worktree / prompt context.

## Probe Artifacts (this investigation)

- Probe issue: `Natedorr/openclaw-config#13` — "TEST: attachment ingestion
  probe (close me)". Close after implementation.
- Sample public asset used for Mechanism A:
  `github.com/user-attachments/assets/b45006e0-fabd-43a6-8d81-789330c687d7`
  (from `Beenda1/Hanzala-Sarfraz#3`).
