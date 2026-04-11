# PM Workshop

## Source Map

- `README.md` is the product and architecture anchor.
- `CHANGELOG.md` is the release-facing truth.
- `DOCS/BUILD_LOG.md` is the strongest implementation history anchor for PM cold start.
- `SECURITY.md` defines the standing security posture and reporting path.
- Recent git history is needed here because workflow, security, and formatting commits are moving faster than the longer-form docs.

## Last Logged Anchor

The strongest local anchor is `DOCS/BUILD_LOG.md`, which records the dashboard, pipeline, QC, and security hardening arc through mid-February 2026.

Current local state from docs:

- Core pipeline is implemented across CLI and dashboard.
- Security posture is explicit and project-specific, including path validation and dependency audit expectations.
- The roadmap is not empty, but the more recent git history shows the repo has already moved beyond some of the older roadmap framing.

## Git Delta Since Last Log

Recent git history after the strongest log anchors shows three main streams of change:

1. Security and maintenance hardening
- `0c12133` `chore: finalized formatting and security audit synchronization`
- `0bb84f3` merge for Werkzeug security fix
- `e099d6e` dependency security bump

2. Project structure and documentation movement
- `db176b7` added `Chapter01_Scene01` project and updated build documentation
- `e2ac374` restructured project directories and updated build documentation

3. Product and ingest stability
- `c37e0dd` fixed SSML leak, markdown-in-TTS behavior, Windows encoding, and ingest safety
- `5073007` completed DOXASCOPE pilot work and Arabic/LUFS best-practice updates

PM read on the delta:

- This repo is still active enough that git history is a better short-term signal than changelog cadence alone.
- Security and path-handling work is now a major part of the repo story, not just background maintenance.
- Build history and git history need to stay connected, because the repo has both product evolution and automation/security noise.

## Current PM Read

`Audio-Formation` is healthy but higher-attention than `tiny-museum` or `motionplate` because it has active security-oriented PR flow on top of real product work.

What matters most right now:

- The repo has working local project memory, but it is split across `CHANGELOG.md`, `DOCS/BUILD_LOG.md`, and git history.
- The open GitHub queue is dominated by Sentinel-created security PRs, so PM should treat GitHub oversight here as an active review surface, not just maintenance logging.
- The local docs are strong enough for cold start, but they should be refreshed from real actions rather than broad summary rewrites.

## GitHub Oversight Snapshot

Source: latest PM sweep snapshot plus the repo's current remote (`socialawy/AudioFormation`).

Open PRs:

- `#51` Sentinel `[HIGH]` Fix DoS vulnerability in `SafeStaticFiles` from path manipulation
  - classification: `review-now`
  - shape: agent-created security PR with code changes
- `#50` Sentinel `[CRITICAL/HIGH]` Fix path validation bypass in `SafeStaticFiles`
  - classification: `review-now`
  - shape: agent-created security PR with code changes
- `#49` Sentinel `[HIGH]` Fix error in `SafeStaticFiles` validation
  - classification: `review-now`
  - shape: agent-created security PR with code changes

Recent merged PRs:

- `#48` Sentinel `[CRITICAL]` fix for path traversal in the mix endpoint
- `#47` Dependabot dependency bump
- `#9` older Werkzeug security bump

PM interpretation:

- This is the clearest example so far of a repo where GitHub security review is part of normal PM work.
- The open queue looks like a layered follow-up sequence around static-file and path-validation hardening.
- These should likely be handled as a grouped security review pass, not as isolated housekeeping items.

### Cluster Review Update

Grouped review of PRs `#49`, `#50`, and `#51`:

- `#49` and `#50` are near-duplicate Sentinel PRs.
  - both change the same `SafeStaticFiles` line in `src/audioformation/server/app.py`
  - both add only a Sentinel journal entry plus the one-line fix
  - neither meaningfully broadens verification
- `#51` appears to supersede them operationally.
  - includes the same core `Path(path.lower())` fix
  - also carries wider test and formatting updates around the same security event
  - gives the repo a better single artifact for the security cluster than keeping three overlapping PRs open

PM recommendation:

- treat `#49` and `#50` as duplicate/overlapping findings
- review `#51` as the candidate keeper for the cluster
- after explicit review, close the redundant PRs and write one local history note instead of logging all three as distinct work items

## Action Candidates

- Review PRs `#49` to `#51` together as one security cluster focused on `SafeStaticFiles` and path validation.
- Prefer `#51` as the single review target unless a closer code read shows the extra formatting/test churn is undesirable.
- Log the outcome of that cluster back into `DOCS/BUILD_LOG.md` or the repo's preferred security/build history file once reviewed.
- Avoid broad doc refresh until the security queue is resolved, because the current live story is still moving.
- Keep PM in report-first mode here unless a deliberate decision is made to have co-pm write regular project updates automatically.

## Next PM Write Targets

- First write target: `DOCS/BUILD_LOG.md`
- Secondary write target: `CHANGELOG.md` if any reviewed PR materially changes shipped behavior
- Optional write target: `SECURITY.md` only if the review changes policy or supported reporting guidance

## Ghost Injection Candidate

`Audio-Formation` cold start should begin from three anchors: `DOCS/BUILD_LOG.md`, `CHANGELOG.md`, and the latest git/security PR delta. Current PM state: active repo with real product history, but immediate attention is concentrated in Sentinel-created path-validation and static-file security PRs (#49-#51). Preferred PM action is grouped security review first, then write back into local build history using repo-native terminology.
