# Three-minute offline demonstration

All examples are synthetic. Choose **Offline fixtures**; scores and screenshots
from this walkthrough are not live-model measurements. Keep **Human decision** at
**Awaiting review** throughout the demonstration.

Start from `ota_verifier`:

```powershell
.\.venv\Scripts\python -m streamlit run app/streamlit_app.py
```

## 0:00–0:50 — Parallel writing with intermediate compatibility

Load **Parallel update campaign**, choose **Baseline policy**, use a concurrent
write limit of 2, and select **Analyze revision**. Open **Plan**.

Point to the overlapping write intervals and ordered activations. Compare total
write time with the measured campaign duration. The initial state and each
activation state remain compatible. The overall baseline stress assessment still
contains violations: nominal feasibility does not imply successful fault recovery.
Do not describe the nominal plan as an approved or deployment-ready campaign.

## 0:50–1:30 — A compatible destination with no compatible route

Load **Impossible intermediate versions**, keep the baseline selection, and
analyze a new revision. Open **Plan**.

Both target versions satisfy their final dependencies, but activating either ECU
first violates the other dependency. Atomic multi-ECU activation is outside the
model. Show the source-linked subset-minimal conflict. This is the key campaign
problem a final-version checklist would miss.

## 1:30–2:40 — Guarded recovery without hiding baseline failures

Load **Authorized rollback comparison**, choose **Guarded trial boot policy**, and
analyze. Open **Faults**.

Show baseline **violations** beside guarded **passed**. The example includes
explicit synthetic permissions to return to original versions. Show 42 paired
cases, 48 guarded cases, and 6 confirmation cases. Trace a boot failure and its
recovery, noting image integrity, boot health, availability, and the confirmed
slot as separate observations. Missing downgrade permissions and availability
cycles still block recovery in other tested scenarios.

## 2:40–3:00 — Human review remains a separate action

Open **Review** and identify the selected policy, exact snapshot hash, required
assumptions, and retained baseline findings. Explain that the guarded proposal is
eligible for human review, while no decision has yet been recorded. Changing
policy or trial options requires a new revision and invalidates applicability of
an earlier decision. Do not click **Record decision** merely to finish a demo.

## Reproduce machine-readable evidence

```powershell
.\.venv\Scripts\python -m ota_verifier.release_validation --output runs/my-release
```

This checks the three stories, runs the frozen fixture benchmark, and rehearses
migration, interrupted resumption, live-WAL backup, and restore. The output
includes full review bundles, the benchmark, recovery databases, a validation
report, and a SHA256 artifact index. The output directory must be new.
`local_checks_passed` can be true while `release_ready` remains false: remote CI
and genuine OIDC login/role/logout checks are external release gates.

## Browser capture

The optional capture script drives a fresh loopback-only Streamlit process with
synthetic fixtures. It saves actual screenshots and a silent WebM screen
recording. It never records a human approval or opens real shared-workspace data.
Use the timed narrative above as voiceover; the automated video runs faster.

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev,presentation]"
.\.venv\Scripts\python -m playwright install chromium
.\.venv\Scripts\python scripts/capture_demo.py --output runs/my-browser-demo
```

The capture output directory must be new. A capture failure keeps its log and
partial artifacts for inspection. Browser media is presentation evidence, not a
replacement for the deterministic tests or live authentication validation.
