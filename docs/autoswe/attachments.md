# Issue / Work-Item Attachment Ingestion

**Status: design doc + live-verified API investigation (2026-10-09).** Not
implemented yet.

This doc records *how* attachments on issues (GitHub) and work items (Azure
DevOps) can be discovered and downloaded per provider, with **live-tested
examples** run from this host on 2026-10-09. Probe artifacts:

- GitHub: `Natedorr/openclaw-config#13` (private repo, probe issue) —
  "close me".
- Azure: org `Natedorr`, project `testProject`, **work item #218** —
  "close me".
- Public-repo sample for the redirect mechanism: `Beenda1/Hanzala-Sarfraz#3`.

Everything below that says **verified** was executed, not read from docs.
Where the docs and reality disagree, reality wins and the discrepancy is
called out.

## Problem Statement

Today autoSWE pulls only **text** from issues:

- `autoswe/harness/prompts.py` injects `Issue body:` + `Comments so far:`
  verbatim into planner/coder/reviewer prompts.
- `fetch_comments()` (both providers) grabs `body` strings only.

If a user attaches a file (CSV, image, log) to an issue or a comment,
autoSWE's model sees a URL it cannot read or fetch. This doc closes that gap
and documents the per-provider mechanics that make it possible.

---

## Provider 1: GitHub

### 1.1 There is no documented REST endpoint for attachments

GitHub's REST API has **no `GET .../attachments` endpoint** and no way to
list an issue's attachments programmatically. Community confirmation
(cli/cli discussion #11832, 2025): "there is still no stable, supported API
to download issue attachments in CI the way you can fetch release assets."

So the design must **discover attachment URLs from the markdown body**, then
download via the URL itself. There is no way around this.

### 1.2 Where attachment URLs appear

When a user attaches a file in the web UI, GitHub stores it under
`https://github.com/user-attachments/assets/<uuid>` and embeds that URL in
the issue body / comment markdown.

**Discovery = regex over `body` + every comment `body`:**

```
https?://github\.com/user-attachments/assets/[0-9a-f-]{36}
```

The *raw* markdown `body` (default media type) always contains the plain
`github.com/user-attachments/assets/<uuid>` URL, whether the file is
referenced as an embedded image or a bare link. That is what we regex.

> **Live note (2026-10-09):** the *plain* `github.com/user-attachments/...`
> URL itself is only downloadable for **public** repos. For **private**
> repos that plain URL 404s — see §1.3, Mechanism B. So discovery (finding
> the UUID) is cheap; *downloading* is the part that differs by visibility.

### 1.3 Downloading the URL — two mechanisms

**Mechanism A — redirect-follow. Works for PUBLIC repos. Verified.**

A `GET` with `-L` (follow redirects) on the plain attachment URL returns a
302 to a pre-signed S3 URL; the S3 URL carries its own `X-Amz-Signature`, so
the second hop needs no auth. Anonymous.

```
$ curl -sS -L -o file.png \
    "https://github.com/user-attachments/assets/b45006e0-fabd-43a6-8d81-789330c687d7"
# -> 302 to github-production-user-asset-*.s3.amazonaws.com/...
#       ?X-Amz-Signature=***&X-Amz-Expires=300&response-content-type=image/png
# HTTP 200, content-type image/png, 62433 bytes
```

Observed caveats:
- **Private repos: this mechanism is dead.** The same `GET` returns **404**
  even with a valid PAT (`Authorization: Bearer <PAT>` and
  `?token=<PAT>` both tried, both 404) when the asset belongs to a private
  repo. `user-attachments` URLs are served for the repo's visibility.
  *Verified on `Natedorr/openclaw-config` (private): 404 with and without
  token.*
- The pre-signed S3 URL is **time-limited (~300s)**. Fine for a one-shot
  download at task setup; not a durable link to cache.
- **Filenames are not in the URL.** The S3 key ends in a `.png`/`.jpg`/etc.
  suffix derived from the *stored* content type, not the original name.

**Mechanism B — signed JWT from `body_html`. Works for PRIVATE repos,
BUT only for embedded images. Verified (with a critical limitation).**

Fetch the issue/comment with the `html+json` media type. GitHub renders the
body to HTML; for **embedded image** references it emits an
`<img src="https://private-user-images.githubusercontent.com/...?jwt=***">`
whose `?jwt=*** the file directly, anonymously.

```
$ gh api repos/Natedorr/openclaw-config/issues/13/comments/6093838659 \
    -H "Accept: application/vnd.github.html+json" --jq .body_html
...
<img src="https://private-user-images.githubusercontent.com/185386482/
         670243970-...png?jwt=***
...
$ curl -sS -o out.png "<that signed url>"
# HTTP 200, content-type image/png, 74 bytes, SHA-256 == source
```

The `jwt` is a signed token wrapping a pre-signed S3 request; its payload
(`exp - nbf`) is ~300s. **Fetch and download in the same operation**; never
persist the signed URL.

> **CRITICAL LIMITATION (verified 2026-10-09): GitHub only issues a signed
> JWT for *embedded image* references (`![alt](<url>)`).**
>
> - A comment that references the same asset as a **plain markdown link**
>   (`[x](<url>)`) produces **zero** signed URLs in `body_html` — GitHub
>   renders it as a plain `<a href="https://github.com/user-attachments/...">`
>   with no JWT.
> - Therefore, on a **private repo**, a file that is only *linked* in prose —
>   which is exactly how GitHub renders **non-image** files (CSV, PDF, log)
>   in the web UI — is **unreachable** through both Mechanism A (404) and
>   Mechanism B (no signed URL).
>
> A CSV's bytes *can* get through a private repo only if it is (a) uploaded
> under an image content type and (b) referenced as an embedded image
> `![]()`. Verified: CSV bytes uploaded as `probe-data.csv.png`
> (`content_type=image/png`), embedded, signed URL issued, downloaded back
> anonymously, SHA-256 byte-exact (served as `image/png`). This is a hack,
> not a supported path — see §1.6.

### 1.4 Which mechanism to use

| Scenario | Mechanism |
|----------|-----------|
| Public repo, attachment in body/comment | **A** (redirect-follow) — simplest |
| Private repo, attachment **embedded as image** | **B** (body_html signed JWT) — verified byte-exact |
| Private repo, attachment only **linked** in prose | **Dead end** — no signed URL; treat as unavailable |

Recommended implementation: try **A** first (`GET -L`); if it returns 404,
fall back to **B** (re-fetch the containing body with `html+json`, extract
the `private-user-images...?jwt=*** URL, download). Both are best-effort and
must never hard-fail the task — a missing attachment is a warning, not an
error.

### 1.5 Uploading (out of scope for autoSWE, but documented)

There is **no documented REST API to upload** an attachment to an issue. The
only working path is an **undocumented** `uploads.github.com` endpoint, which
is **image-only**. Live-tested behavior (2026-10-09):

```
# repo_id from: gh api repos/OWNER/REPO --jq .id
$ curl -sS \
  "https://uploads.github.com/user-attachments/assets?name=probe-image.png&content_type=image/png&repository_id=1192331190" \
  -X POST -H "Authorization: Bearer ***" -H "Accept: application/json" \
  --data-binary @probe-image.png
# -> {"url":"https://github.com/user-attachments/assets/802b4410-..."}
```

Accepted content types: `image/png`, `image/jpeg`, `image/gif`,
`image/webp`. Rejected: `text/csv`, `text/plain`, `application/zip`,
`application/pdf`, `image/svg+xml`.

**Name must match content type.** `name=probe-data.csv` with
`content_type=image/png` →
`"name has a file extension that does not match the content type:
.csv != image/png"`. A disguised name works: `name=probe-data.csv.png` +
`content_type=image/png` with CSV bytes → `200`, bytes stored intact.

Because this endpoint is undocumented and **image-only**, autoSWE should
**not** rely on it for uploading. The ingestion design assumes attachments
were created in the web UI.

### 1.6 Non-image files (CSV, PDF, log, etc.)

The web UI accepts any file type, so a CSV/PDF attached there produces the
same `github.com/user-attachments/assets/<uuid>` URL. Downloadability:

- **Public repo:** Mechanism A works for any embedded/linked file — the
  redirect is visibility-gated, not type-gated. (Verified for images; the
  redirect is the same endpoint regardless of type.)
- **Private repo:** only *embedded image* references get a signed URL
  (§1.3). A genuine CSV is linked, not embedded → **currently unreachable**
  via the API. The only confirmed workaround is the disguise hack
  (upload under an image content type + reference as `![]()`), which returns
  the bytes but labels them `image/png`. This is an **open gap** (see
  §Open Questions, item 1).

**Content-type detection is the robust approach** regardless of provider:
download the bytes, sniff the magic bytes, and name the file accordingly. Do
not trust the URL extension or the served `Content-Type` for the on-disk
name.

---

## Provider 2: Azure DevOps

Azure has a **first-class, documented** attachments API — easier than GitHub.
All of the following was **verified live** against `Natedorr/testProject`,
work item #218.

### 2.1 Discovering attachments on a work item

Attachments are exposed as **relations**, but **only when fetched with
`$expand=all`.**

```
GET https://dev.azure.com/{org}/{project}/_apis/wit/workitems/{id}?$expand=all
Authorization: Basic ***})
```

> **Verified (2026-10-09): `$expand=all` is required.** A fetch *without* it
> returns **zero** relations on the same work item; with `$expand=all` the
> `AttachedFile` relations appear. autoSWE's Azure tracker already fetches
> with `$expand=all` (`autoswe/providers/azure/tracker.py`), so the data is
> present in its payload today and being discarded.

Observed relation shape (live, WI 218):

```json
{
  "rel": "AttachedFile",
  "url": "https://dev.azure.com/natedorr/5f5c4aeb-.../_apis/wit/attachments/daf53c9a-9f7e-4af0-ab70-4152fdb2fca0",
  "attributes": {
    "id": 1292279,
    "resourceSize": 74,
    "authorizedDate": "2026-10-10T04:29:42.83Z",
    "resourceCreatedDate": "2026-10-10T04:29:42.83Z",
    "resourceModifiedDate": "2026-10-10T04:29:42.83Z",
    "revisedDate": "9999-01-01T00:00:00Z"
  }
}
```

So discovery = parse `relations[]` where `rel == "AttachedFile"`; the `url`
is the download URL and `attributes.resourceSize` gives the byte size.

> **Discrepancy with docs (verified):** the MSDN sample shows
> `attributes.name` (the real filename), but in the live response **`name`
> was absent** — even though the work item was created with
> `attributes: {"name": ...}` on the relation, and the download response's
> `Content-Disposition` was bare `attachment` (no `filename=`). Treat
> `attributes.name` as **optional**: use it when present, otherwise fall
> back to content sniffing / `attachment-<n>` (same policy as GitHub).

### 2.2 Downloading

```
GET https://dev.azure.com/{org}/{project}/_apis/wit/attachments/{id}
Authorization: Basic ***})
# -> raw file bytes, Content-Type: application/octet-stream,
#    Content-Disposition: attachment
```

Reference: `learn.microsoft.com/en-us/rest/api/azure/devops/wit/attachments/get`
(view `azure-devops-rest-7.1`).

Concrete curl (matching autoSWE's existing Basic-auth in
`autoswe/providers/azure/api.py`):

```
$ curl -sS -o out.bin \
  "https://dev.azure.com/{org}/{project}/_apis/wit/attachments/{id}" \
  -H "Authorization: Basic *** -n ':PAT' | base64)"
```

Verified: both probe attachments (CSV 74 B, PNG 74 B) downloaded with
SHA-256 byte-exact match to the source files.

### 2.3 Uploading (for completeness)

```
POST https://dev.azure.com/{org}/{project}/_apis/wit/attachments?fileName=data.csv&api-version=7.1
Authorization: Basic ***})
Content-Type: application/octet-stream
# body: raw file bytes
# -> 201, JSON body: {"id": "<guid>", "fileName": "data.csv"}
# download URL: .../_apis/wit/attachments/<id>
```

Reference: `learn.microsoft.com/en-us/rest/api/azure/devops/wit/attachments/create`.

> **Verified (2026-10-09): do NOT pass `uploadType` on the POST.** Both
> `uploadType=attachment` and `uploadType=temporary` are rejected with
> `400 "This uploadType ... is not supported with the POST operation."`
> Omit it entirely. The `Location` response header is **empty**; the
> attachment id comes from the **JSON body's `id`** field, not the
> `Location` header.

Linking to a work item (verified): JSON-Patch on work-item create/update:

```json
{"op":"add","path":"/relations/-",
 "value":{"rel":"AttachedFile","url":".../_apis/wit/attachments/<id>",
          "attributes":{"name":"data.csv"}}}
```

Note: work-item create requires `Content-Type: application/json-patch+json`
(not `application/json`).

---

## Proposed autoSWE Design (cross-provider)

A small, provider-agnostic attachment layer that runs at **task setup**
(before the planner/coder runs), downloading into a **temp folder**
(never the worktree, never the repo):

1. **Discover** —
   - GitHub: regex `user-attachments/assets/<uuid>` over issue body + all
     comment bodies. (Raw markdown always carries the plain URL for both
     embedded and linked references.)
   - Azure: parse `relations[]` with `rel == "AttachedFile"` from the
     `$expand=all` fetch (already performed by the tracker).
2. **Download** —
   - GitHub: try Mechanism A (`GET -L`); on 404 fall back to Mechanism B
     (re-fetch containing body with `html+json`, extract the
     `private-user-images...?jwt=*** URL, download). Only embedded images
     yield a signed URL on private repos — if none is found, warn and skip.
   - Azure: `GET _apis/wit/attachments/{id}`.
   - All best-effort: a failure logs a warning and continues. Never
     hard-fail the task on a missing/unreachable attachment.
3. **Name & store** — **Decision (2026-10-10, Nate): attachments go into a
   temp folder, never the worktree and never the repo.**

   - One directory per task under the OS temp dir:
     `tempfile.mkdtemp(prefix="autoswe-attach-")`
     (e.g. `/tmp/autoswe-attach-13-a1b2c3/`), created at task setup.
   - Filename: prefer a provider-supplied name (Azure `attributes.name`
     when present; GitHub markdown `alt` text when it looks like a
     filename); otherwise **sniff content**, else `attachment-<n>.<ext>`.
   - Because the folder sits outside the worktree, committing an attachment
     is impossible by construction — no `attachments.commit` flag needed.
   - Path-traversal guard on any provider-supplied name
     (attacker-influenced on both providers): reject names containing
     `/`, `..`, or absolute paths; keep files flat in the temp dir.
   - **Cleanup:** the dispatch loop removes the temp dir in a `finally`
     block on task teardown (success, failure, or cancel). A stale-dir
     sweeper (mtime > 24h) runs at poller start for crash leftovers.
4. **Manifest** — append to the planner/coder/reviewer prompt a block with
   **absolute** paths (the temp dir is outside the worktree, so relative
   paths would mislead the model):

   ```
   Attached files available locally (temp dir, read-only):
   - /tmp/autoswe-attach-13-a1b2c3/failing-input.csv  (text/csv, 1234 bytes)
   - /tmp/autoswe-attach-13-a1b2c3/screenshot.png     (image/png, 62433 bytes)
   ```

   so the model knows the files are on disk and can `read`/`process` them.
   CSV/text are fully ingested; images are viewable by backends that support
   image input (claude_code does).
5. **Config flags** — `attachments.enabled` (default `true`);
   `attachments.max_size_bytes` (default e.g. 10 MiB per file) and
   `attachments.max_total_bytes` (default e.g. 25 MiB per issue).
   `attachments.commit` is **not a thing** — temp-folder storage makes it
   impossible; if a fix needs a fixture in the repo, the model copies it in
   as a normal tracked file as part of the fix.

## Open Questions

1. **Private-repo GitHub, non-image attachments:** a genuine CSV/PDF linked
   in prose is currently unreachable (no signed URL, plain URL 404s).
   Options: (a) accept + warn; (b) document that users must *embed* files
   as images on private repos; (c) investigate whether a web-UI-attached
   non-image ever gets a signed URL (all private-repo probes so far used
   embedded-image markdown — a web-UI-attached private CSV test is still
   owed before closing this out). This is the single biggest real-world
   limitation and the reason the feature is "best-effort, warn on miss".
2. **Filename:** no reliable source on either provider in the live probes
   (Azure `name` absent; GitHub name not in URL). Content sniffing is the
   default; decide whether markdown `alt` text is trusted enough to prefer.
3. **Security:** attachments are untrusted user input. The ingester must
   sandbox them — never execute, enforce the size caps, and path-traversal-
   guard every provider-supplied filename.
4. **Size cap defaults:** pick `max_size_bytes` / `max_total_bytes` that
   protect the worktree and prompt context without rejecting legitimate
   failing-input CSVs.

## Live Verification Log (2026-10-09)

Executed from this host; results cited inline above.

**GitHub** — `Natedorr/openclaw-config` (private, repo id `1192331190`,
probe issue `#13`):
- Upload via `uploads.github.com`: `probe-image.png` (74 B) → 200; CSV bytes
  as `probe-data.csv.png` (`content_type=image/png`) → 200; CSV named
  `probe-data.csv` + `content_type=image/png` → **400** (name/extension
  mismatch).
- Direct `github.com/user-attachments/assets/<uuid>` GET on private-repo
  assets: **404** (anonymous and with PAT) — Mechanism A confirmed dead for
  private.
- Plain-markdown-link comment: **0** signed URLs in `body_html` — confirms
  only embedded images get signed.
- Embedded-`![]()` comment: signed URLs present; both downloads → **200
  anonymous**, SHA-256 byte-exact vs source (CSV-disguised-as-PNG and real
  PNG) — **PASS**.

**Azure DevOps** — `Natedorr/testProject`, probe work item **#218**
("TEST: AutoSWE attachment ingestion probe (close me)"):
- Upload `probe-data.csv` + `probe-image.png` via
  `POST _apis/wit/attachments?fileName=...` (no `uploadType`) → **201**
  each; JSON body carried the attachment `id`.
- `uploadType=attachment` / `uploadType=temporary` on POST → **400**.
- Created WI 218 with JSON-Patch `AttachedFile` relations (work-item create
  used `Content-Type: application/json-patch+json`).
- `GET workitems/218` (no expand): **0** relations; `?$expand=all`: **2**.
- Downloaded both via `_apis/wit/attachments/{id}` with PAT Basic auth →
  **200**, SHA-256 byte-exact vs source files — **PASS**.
- Observed relation `attributes` **lacked `name`** (docs show it) — recorded
  in §2.1.

Both probe artifacts are marked "close me" and should be closed once the
implementation lands.

## Probe Artifacts (this investigation)

- Probe issue: `Natedorr/openclaw-config#13` — "TEST: attachment ingestion
  probe (close me)". Close after implementation.
- Probe work item: Azure `Natedorr/testProject` **WI 218** — "TEST: AutoSWE
  attachment ingestion probe (close me)". Close after implementation.
- Public sample asset used for Mechanism A:
  `github.com/user-attachments/assets/b45006e0-fabd-43a6-8d81-789330c687d7`
  (from `Beenda1/Hanzala-Sarfraz#3`).

### 1.7 Re-verification (2026-10-10)

Same-process fetch + download re-run against `openclaw-config#13`:
`html+json` comments list (0.4s) → 6 signed URLs → **all 6 downloaded 200
within 0.96s total**; the CSV-as-PNG asset came back byte-exact
(magic bytes `id,name,expected`, served as `image/png`). Confirms the
"fetch and download in the same operation" rule in §1.3 is sufficient —
no timing hazard at task-setup latency. Plain-link comment
(6093798908) again produced zero signed URLs, reconfirming the §1.3
critical limitation.
