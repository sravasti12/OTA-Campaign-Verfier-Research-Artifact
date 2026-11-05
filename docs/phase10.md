# Phase 10: single-host shared review and operational hardening

The user-selected scope is one trusted host, Streamlit, SQLite on a local disk,
and configurable identity-provider login. The default offline local demo remains
available. This phase does not deploy a public service or integrate a vehicle.
No further numbered phases are planned.

## Modes and trust boundary

`OTA_ACCESS_MODE=local` is the default unauthenticated portfolio demo. Its reviewer
names are self-reported. `OTA_ACCESS_MODE=shared` gates the app before source
inputs, library entries, or evidence are displayed. Invalid mode values fail
closed. Mode and workspace configuration come from the host environment, never
from browser widgets. Do not expose local mode as a shared authenticated service.

Shared mode uses Streamlit's native OIDC login, which verifies identity and
manages its identity cookie. Authorization is implemented separately in the
server allowlist. See the primary [Streamlit authentication guide](https://docs.streamlit.io/develop/concepts/connections/authentication)
and [login configuration reference](https://docs.streamlit.io/develop/api-reference/user/st.login).
No custom JWT parser, password store, or browser-supplied roles are used.

Exact OIDC issuer and subject identify accounts; names, email domains, and token
role claims do not grant access. The host allowlist is reread on every service
operation, and review authorization is rechecked immediately before commit.
Token `iat` and `exp` claims are required. Access also expires after the configured
maximum age since token issuance, independently of Streamlit's longer cookie
lifetime. Sign out and back in to renew a stale identity. Removing/disabling an
account revokes subsequent operations, including existing sessions.

| Server allowlist role | Read/history/export | Analyze/revise/resume | Record human decision |
| --- | --- | --- | --- |
| reader | Yes | No | No |
| analyst | Yes | Yes | No |
| reviewer | Yes | No | Yes |
| admin | Yes | Yes | Yes |

An account can have multiple roles. Access is workspace-wide; this is not a
multi-tenant or per-campaign ACL. The UI disables unauthorized actions, but the
shared service enforces permissions even if a control is bypassed. A reviewer
cannot manufacture their identity through the form. The canonical issuer/subject
identity replaces the form name; its grants and timestamp are stored atomically
with the decision. Stale hashes, wrong revisions, failing policy evidence, and
competing decisions remain subject to the existing transactional gate.

Python code and maintenance commands run by the host operator are trusted.
Someone with filesystem/database/source access can bypass application controls;
this feature is not a Python sandbox or tamper-resistant audit system. Browser
admin role does not itself grant access to host maintenance commands. Host
maintenance actors are recorded as entered, separately from OIDC review identity.

## Configure shared review

From `ota_verifier`, install the optional login dependencies:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev,shared]"
```

1. Stop the app before migrating an existing workspace or changing its access
   mode. If no workspace exists yet, open the local app's persistent library once
   to initialize `.ota_state/reviews.sqlite`, then stop the app.
2. Register an OIDC application with your chosen provider. Use immutable `iss`
   and `sub` values for accounts. Configure the exact callback URL; the provided
   local-development example uses `http://localhost:8501/oauth2callback`.
3. Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`. Fill in the
   provider discovery URL, client ID/secret, and a strong random cookie secret.
   Do not use the placeholder values. The real secrets file is Git-ignored.
4. Copy `examples/access_policy.example.json` to `.ota_state/access.json`.
   Replace the placeholder issuer/subject, choose roles, and explicitly enable
   the account. The example is disabled and grants only reader rights. Its
   `database_path` is relative to the policy file's directory, so `reviews.sqlite`
   resolves to `.ota_state/reviews.sqlite` in this arrangement.
5. Restrict the secrets, allowlist, database, backup directory, and parent
   directories to the service account and trusted host administrators using OS
   filesystem permissions. This repository does not change your Windows ACLs.

Explicitly migrate the workspace, retaining a verified pre-migration backup:

```powershell
.\.venv\Scripts\python -m ota_verifier.persistence.operations migrate .ota_state/reviews.sqlite --destination .ota_state/pre-v2-backup.sqlite
```

Set **process environment variables** before launching the server:

```powershell
$env:OTA_ACCESS_MODE = "shared"
$env:OTA_ACCESS_CONFIG = (Resolve-Path .ota_state/access.json).Path
.\.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

These access variables are deliberately not read from a browser or the LLM
`.env` loader. OIDC secrets use Streamlit's secrets management. LLM keys continue
to use the existing `.env`/environment abstraction and are not login credentials.

Visit `http://localhost:8501`, sign in, and open the saved run library. Its
workspace cannot be changed through shared-mode controls. If existing analysis
was created under an older implementation/storage fingerprint, an analyst must
create a fresh revision before a reviewer records a new decision. Previously
completed evidence and decisions remain readable.

The checked-in server still binds to loopback. Multiple browser sessions on one
host are supported by the shared application and SQLite execution lock. An actual
network deployment, TLS termination, proxy configuration, provider account
provisioning, and public hosting have not been exercised here. Do not describe
this as a tested public deployment. Multi-host operation needs a different
transactional database/worker architecture; do not share this SQLite file over a
network filesystem. Live provider login must be tested with your configuration;
this phase's automated login tests mock Streamlit-verified claims.

## Migration and evidence provenance

Ordinary opening supports schemas 1 and 2 but never upgrades a v1 workspace.
Shared mode requires schema 2. The migration:

* verifies SQLite integrity, foreign keys, content hashes, and checkpoint evidence;
* captures a consistent, verified v1 backup and manifest;
* creates authenticated-review, retention, and migration metadata in one SQL
  transaction, then advances the schema version;
* retains existing revision input, snapshots, decisions, and checkpoints verbatim.

Failure rolls back all schema changes. Unknown schemas and missing v2 operational
tables fail explicitly. Stop the server for migration; the execution lock also
serializes it against application mutations. There is no automatic down-migration;
restore the separately verified v1 backup to a new path if needed.

Policy-specific `review-bundle-v2` and legacy `review-bundle-v1` rules are unchanged.
An authenticated portable export uses `persistent-review-v2`, containing matching
OIDC provenance for the relevant retained decisions. An export without authenticated
records keeps `persistent-review-v1` and its prior serialized shape. Provenance is
validated against decision identity, revision, and timestamp. Historical local
names are never relabeled as authenticated.

`export_id` is a SHA256 content identifier over the canonical complete export.
The ID is displayed in persistent history and shared review. The snapshot hash
still binds the human decision; the export ID additionally includes decision
history and authentication metadata, so it changes when a decision is added.
Neither identifier is a signature or proof against a malicious host operator.
No authentication cookie, ID token, access token, API key, or client secret is
added to workflow checkpoints or portable evidence.

## Backup, restore, and retention

Maintenance commands run on the trusted host, not as browser-selected shell
operations. The installed `ota-workspace` command is equivalent to this module:

```powershell
.\.venv\Scripts\python -m ota_verifier.persistence.operations verify .ota_state/reviews.sqlite
.\.venv\Scripts\python -m ota_verifier.persistence.operations backup .ota_state/reviews.sqlite --destination .ota_state/review-backup.sqlite
.\.venv\Scripts\python -m ota_verifier.persistence.operations restore .ota_state/review-backup.sqlite --destination .ota_state/restored.sqlite
```

Every destination must be new. Backups use SQLite's backup API under the same
execution lock as graph mutations; this captures committed WAL data without
copying an inconsistent main file. A sidecar `.manifest.json` contains its file
hash and verification counts. Keep the database and its manifest together and
protect both with filesystem permissions. Partial failed outputs lack a valid
manifest and must not be used as backups. An incomplete destination is left for
operator inspection; no existing file is removed or overwritten.

Restore checks the manifest/file hash, SQLite structure, revision hashes,
receipt hashes, published checkpoint/snapshot linkage, decision eligibility,
authenticated provenance, and revision registry. It copies into a new database
and verifies again. Committed review decisions, authentication metadata, archives,
and pending checkpoints are retained. Ready evidence opens without model calls.
An inflight/uncertain model request remains uncertain; restoring never silently
retries it. A pending checkpoint still needs a matching runtime fingerprint to
resume. Back up before runtime upgrades and test restore on a separate path.
Stop the service before cutover; point the protected allowlist to the restored
path and restart after verification. Never overwrite a running workspace.

Archive a completely analyzed and reviewed run without deleting its evidence:

```powershell
.\.venv\Scripts\python -m ota_verifier.persistence.operations archive .ota_state/reviews.sqlite --run-id RUN_ID --actor HOST_OPERATOR --reason "Retain completed review"
```

Archiving requires schema 2, a current complete snapshot, a recorded decision,
and nonempty actor/reason. The run stays readable/exportable with all revisions,
receipts, and history. Review, revision, and resume mutations are blocked.
Backups/restores retain the archive marker. There is no automatic deletion,
retention expiry, unarchive, or database compaction in this phase. Define any
future purge/legal-hold policy explicitly before adding destructive operations.

## Verification and limits

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_operations_access.py tests/test_shared_app.py
.\.venv\Scripts\python -m pytest -q
```

Offline tests cover role matrices, issuer/subject mismatch, absent/expired
sessions, role injection, revocation, stale approvals, simultaneous authenticated
decisions, atomic provenance rollback, explicit migration rollback, live-WAL
backup, verified restore, interrupted resumption, archive preservation,
no-overwrite behavior, export identifiers, provenance corruption, anonymous UI,
and reviewer/read-only UI. Existing local-mode and deterministic tests remain.
No live OIDC login or live LLM call is claimed from these mocked integration tests.

Backups and source/model evidence are plaintext. Availability, disaster recovery
for lost backup files, external provider uptime, rate limiting, Internet-scale
denial-of-service protection, authenticated OS maintenance, and tamper-resistant
external audit storage are outside this local simulation milestone. The project
makes no vehicle, production deployment, or certification guarantees.
