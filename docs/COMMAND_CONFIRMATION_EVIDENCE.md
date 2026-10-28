# Command confirmation evidence register — Phase 5

Decision: **UNVERIFIED**. Keep Phase 4's strict sequence/entity matching and
reservations. Synthetic tests establish client behavior, not Lilith behavior.
This file is an evidence register, not authorization to capture or send traffic.

Phase 6: no additional authorized evidence was supplied. The gate remains
closed in code; admin observation grants cannot enable automatic/manual
game-changing actions. No new capture or game call was made.

## Sources inspected on 2026-09-27

- Phase 4 PR #3 head `c45d1bfdac98c0dfe5591a1a514d27c145184c98`, its diff,
  `PHASE4_HANDOFF.md`, and `PHASE3_MIGRATION.md`.
- Repository tree at that exact head: no tracked capture, PCAP, JSONL or
  sanitized trace files.
- Existing local `service/app/core/warpath/logs/warpath_protocol_*.jsonl`:
  five files, each with one capture-start and one capture-stop marker;
  **zero upstream messages and zero downstream messages**. No payloads or
  secret values were copied into this document or the PR. Their marker-only
  shape is also produced by `test_api_diagnostics.py`; provenance is not
  assumed from filenames or timestamps.
- Protobuf definitions and targeted observation/send handlers expose
  `msg_seq_id`; source comments describe earlier live reply shapes. Neither
  field existence nor comments establish matching request/reply IDs or causal
  ordering. Phase 4's echoed synthetic replies are explicitly excluded from
  upstream evidence.

No usable authorized sanitized captures were available in the repository or
working copy. No live game requests, captures, emails or production access were
performed. Absence here does not mean the operator has no captures elsewhere.

| Required upstream fact | Evidence available | Decision |
|---|---|---|
| Mine-search result echoes the originating search request ID | None | Unverified |
| Gather result echoes the request ID and identifies the requested truck/mine | Reply shape only, no paired capture | Unverified |
| Collection reply echoes the request ID and identifies its building | Reply shape only, no paired capture | Unverified |
| A list requested after confirmed dispatch provides a usable later idle observation | No paired ordered trace or authoritative ordering contract | Unverified |
| Duplicate/delayed replies cannot be confused with a later attempt | Synthetic client tests only | Client protection tested; upstream behavior unverified |

## Acceptable future evidence

An authorized operator may supply **already captured, reviewed and sanitized**
evidence in a later session. New captures/game interactions require separate
explicit authorization. Supply a manifest with source/client version,
connection boundaries, acquisition date, authorized purpose, sanitization
method and reviewer, plus a checksum for each sanitized artifact. Do not
include user credentials, cookies, verification codes or production DB dumps.

Use a strict allowlist of decoded action metadata: ordered frame index,
direction, relative monotonic time, action/reply kind, request/reply sequence,
consistent pseudonyms for building/truck/mine IDs, state, required-verification
flag, and explicit field presence. Preserve equality relationships and the
special idle mine ID zero. Preserve reconnect boundaries and whether a field
was absent; replacing absent values with zero destroys evidence. Remove
player identity, emails, device metadata, tokens, session information,
coordinates, raw payloads/base64 and unrelated messages. Keep raw sources
restricted outside the repository under the operator's retention policy.

Review multiple independently paired actions, overlapping building requests,
heartbeats/unrelated replies, late/duplicate responses when present, and
requests before/after vehicle state transitions. Document contrary examples
and gaps. One matching sample does not establish universal echo/ordering
semantics. An evidence review must explicitly decide which exact action kinds
and client versions are supported; do not silently generalize to recall,
scout, armies or other protocol paths.

Existing admin debug downloads are **not automatically sanitized evidence**:
`_record_protocol_debug` records downstream messages only; its key-name
redaction is not an allowlist and conversion/parse failures can include
`raw_base64`. It cannot establish upstream/downstream pairing by itself.
Keep diagnostics admin-only and never send an unreviewed capture to a customer,
PR, issue or chat. This phase adds no recorder or capture/export endpoint.

If actual sequence semantics differ, preserve conservative uncertainty and
request a separately reviewed correlation/recovery design. Do not restore
counter/FIFO/first-reply confirmation or release reservations on elapsed time.
There is no claim of durable exactly-once execution or public-launch readiness.
