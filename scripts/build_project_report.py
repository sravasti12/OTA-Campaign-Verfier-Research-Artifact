"""Generate the illustrated project report using offline HTML and Chromium."""
from html import escape
import json
from pathlib import Path
import re
import sys
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def p(text: str) -> str:
    """Wrap authored technical prose."""
    return f'<p>{text}</p>'


def table(headers: list[str], rows: list[tuple[str, ...]]) -> str:
    """Produce a printable table with repeating headers."""
    return '<table><thead><tr>' + ''.join(f'<th>{x}</th>' for x in headers) + '</tr></thead><tbody>' + ''.join(
        '<tr>' + ''.join(f'<td>{x}</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table>'


def ul(*items: str) -> str:
    """Render parallel observations."""
    return '<ul>' + ''.join(f'<li>{x}</li>' for x in items) + '</ul>'


def code(text: str) -> str:
    """Escape source examples."""
    return '<pre>' + escape(text) + '</pre>'


def note(title: str, text: str) -> str:
    """Highlight a modeling or decision boundary."""
    return f'<aside><b>{title}</b><br>{text}</aside>'


def figure(name: str, caption: str) -> str:
    """Use real repository screenshots rather than illustrative UI imitations."""
    return f'<figure><img src="assets/{name}"><figcaption>{caption}</figcaption></figure>'


def architecture() -> str:
    """Draw a native vector diagram with LLM and deterministic lanes."""
    nodes = [
        ('Authoritative inventory + documents', 'ECUs, versions, slots, environment, permissions', '#eaf0f5'),
        ('LLM extraction', 'Strict JSON; no planning or permission changes', '#fff1cc'),
        ('Code validation + LLM faithfulness check', 'Schema, references, exact source spans, second judgment', '#fff1cc'),
        ('Deterministic Z3 planning + replay', 'Timing, order, resources, every intermediate state', '#e0f4ef'),
        ('Deterministic fault + recovery analysis', 'A/B sweeps, invariants, optional guarded comparison', '#e0f4ef'),
        ('Evidence + advisory explanation', 'Code-derived facts; LLM prose or deterministic fallback', '#fff1cc'),
        ('Explicit human review', 'Selected policy, revision, snapshot hash, decision', '#e7eafa')]
    svg=['<svg viewBox="0 0 760 630" class="architecture" xmlns="http://www.w3.org/2000/svg">']
    for index,(title,detail,color) in enumerate(nodes):
        y=20+index*86
        svg.append(f'<rect x="20" y="{y}" width="475" height="65" rx="9" fill="{color}" stroke="#adbec8"/>')
        svg.append(f'<text x="35" y="{y+26}" font-size="16" font-weight="700">{escape(title)}</text><text x="35" y="{y+48}" font-size="12.2">{escape(detail)}</text>')
        if index<6:
            svg.append(f'<path d="M255 {y+65}v18m-5 -5l5 5 5 -5" stroke="#557180" fill="none"/>')
    for y,title,lines in [
        (110,'Shared domain rules',['compat.py: requires','versions.py: numeric specs','policy.py: exact authorization']),
        (290,'Optional persistence',['SQLite checkpoints','Response receipts + revisions','Atomic decision provenance']),
        (470,'Optional shared access',['OIDC issuer/subject','Server-controlled roles','Credentials outside graph state'])]:
        svg.append(f'<rect x="518" y="{y}" width="227" height="120" rx="9" fill="#f1f5f8" stroke="#c2d0d9"/><text x="532" y="{y+25}" font-size="14" font-weight="700">{title}</text>')
        for offset,line in enumerate(lines):
            svg.append(f'<text x="532" y="{y+52+22*offset}" font-size="12">{escape(line)}</text>')
    return ''.join(svg)+'</svg>'


def boot_diagram() -> str:
    """Show effective-version and confirmation boundaries."""
    stages=[('Confirmed image','Known original selection'),('Write inactive slot','Erase, write, then verify'),('Trial candidate','Reboot; availability explicit'),
            ('Health succeeds','Candidate becomes effective'),('Atomic confirmation','Durable confirmed-slot update')]
    svg=['<svg viewBox="0 0 760 360" class="boot" xmlns="http://www.w3.org/2000/svg">']
    for index,(title,detail) in enumerate(stages):
        y=12+67*index
        svg.append(f'<rect x="25" y="{y}" width="450" height="51" rx="8" fill="#e0f4ef" stroke="#adbec8"/><text x="40" y="{y+22}" font-size="15" font-weight="700">{title}</text><text x="40" y="{y+40}" font-size="12">{detail}</text>')
        if index<4:
            svg.append(f'<path d="M250 {y+51}v14m-4 -4l4 4 4 -4" stroke="#557180" fill="none"/>')
    svg.append('<rect x="500" y="155" width="240" height="145" rx="9" fill="#fff1cc"/><text x="515" y="181" font-size="14" font-weight="700">Failure / fallback boundary</text><text x="515" y="207" font-size="12">Never-effective failed trial:</text><text x="515" y="228" font-size="12">retain the current version.</text><text x="515" y="254" font-size="12">After successful exposure:</text><text x="515" y="275" font-size="12">older fallback needs permission.</text>')
    return ''.join(svg)+'</svg>'


def report_pages(evidence: dict) -> list[tuple[str, str, str]]:
    """Describe the repository while preserving evidence and simulation limits."""
    pages=[]
    def add(section: str, title: str, body: str) -> None:
        pages.append((section,title,body))
    add('TECHNICAL REPORT / 6 NOVEMBER 2026','OTA Campaign<br>Verifier',
        '<div class="subtitle">Project description, system architecture<br>and engineering evidence</div><div class="cover-rule"></div>'
        +p('A portfolio simulation for software-defined vehicle update campaigns: extract requirements, verify their evidence, plan compatible transitions, stress-test recovery, and pause for human review.')
        +'<div class="cover-grid"><div><b>Deterministic core</b><br>Python · Pydantic · Z3</div><div><b>Workflow and UI</b><br>LangGraph · Streamlit</div><div><b>Evidence and operations</b><br>SQLite · pytest · OIDC</div><div><b>LLM boundary</b><br>Extract · Verify · Explain</div></div>'
        +note('SIMULATION ONLY','Results apply to the modeled states, faults, and assumptions. No vehicle integration or certification evidence is produced.')
        +p('<a href="https://ota-campaign-verifier.streamlit.app/">ota-campaign-verifier.streamlit.app</a>')
        +'<p class="small">Prepared from local source and recorded synthetic release evidence. Full-suite figures are historical measurements, not a new test run performed during PDF generation.</p>')
    add('01 / PURPOSE','The engineering problem',
        p('An over-the-air campaign changes a collection of ECUs rather than one isolated program. A target configuration can satisfy every version dependency even when no compatible intermediate activation order exists. A nominally feasible plan can also encounter power loss, an invalid image, or a rollback authorization barrier.')
        +p('OTA Campaign Verifier investigates those differences in a bounded simulation. Its central question is whether a campaign can move through compatible states and retain an authorized route to original images after each defined single fault. The result is inspectable evidence, not merely a final pass/fail label.')
        +table(['Input','Analysis product'],[
            ('Release notes and ECU documents','Formal constraints linked to exact source text, plus extraction findings.'),
            ('Authoritative inventory and environment','Validated versions, slots, battery, ignition, and explicit downgrade permissions.'),
            ('Scheduling options and selected policy','A concrete parallel schedule, source-linked contradiction, or honest unknown.'),
            ('Fault and recovery assumptions','Complete modeled sweeps, historical invariant findings, and rollback evidence.'),
            ('Human decision','A policy-, revision-, and hash-bound simulation-proposal record.')])
        +note('Industry relevance','The project demonstrates traceability, reproducible scheduling decisions, fault investigation, and review integrity. It does not claim measured effectiveness or adoption by a vehicle manufacturer.')
        +'<h3>Reading map</h3>'+table(['Pages','Focus'],[
            ('3–7','Scope, architecture, module boundaries, domain data, and compatibility.'),
            ('8–11','Extraction, parallel planning, fault injection, guarded boot, and recovery.'),
            ('12–15','Review orchestration, persistence, access, and evaluation evidence.'),
            ('16–20','Worked demonstrations, operation, limitations, and source guide.')]))
    add('02 / SCOPE','Explicit modeling assumptions',
        p('Each ECU supplies one current and one target version. A changed ECU has one direct inactive-slot write and activation. Bridge releases, repeated updates, and atomic multi-ECU activation are outside the repertoire. These simplifications make the meaning of a solver or simulation result reviewable.')
        +table(['Concern','Defined behavior'],[
            ('Timing','Write durations round upward to integer milliseconds. Baseline activation is instantaneous at write completion; equal-time activations have unique indices.'),
            ('Environment','Battery and ignition remain at initial values. Waiting cannot repair a failed precondition.'),
            ('Resources','Concurrency counts independent write channels. Shared bandwidth, power, thermal dynamics, and stochastic flash speed are not modeled.'),
            ('Fault scope','Exactly one injected cause per run, swept over applicable ECU/stage/boundary combinations.'),
            ('Recovery goal','Restore original active images through compatible, valid, authorized slot transitions.'),
            ('Guarded timing','Trial, reboot, and confirmation have no elapsed-time model. Integrity, health, and availability are distinct.'),
            ('Integration','No vehicle adapter, bootloader flashing interface, or fleet execution endpoint.')])
        +'<h3>Four invariant questions</h3>'+ul(
            'Does every active boot selection reference a valid image?',
            'Are effective installed versions compatible after faults and at checked transitions?',
            'Is installation or fallback to an older effective version explicitly authorized?',
            'Does a failed step retain a defined compatible rollback path to original images?')
        +note('Do not overread a pass','A finite search bound can produce unknown. A feasible nominal schedule does not establish fault tolerance. A no-op campaign has zero injected update-fault cases.'))
    add('03 / ARCHITECTURE','System and trust boundaries',
        architecture()
        +p('Yellow blocks contain the only permitted model uses. Green blocks make compatibility, planning, fault, recovery, and invariant decisions in code. Invalid extraction skips planning; infeasible or unknown planning skips flash simulation and retains its diagnostic evidence.')
        +p('Shared domain rules connect symbolic planning to concrete replay and invariant checking. Optional persistence retains evidence; optional access control governs workflow operations. Neither can change a constraint or convert a failing assessment into a pass.'))
    add('04 / IMPLEMENTATION MAP','Where responsibilities live',
        table(['Module / area','Responsibility'],[
            ('<code>models.py</code>','Strict immutable ECU, campaign, constraint, plan, and violation records; reference validation.'),
            ('<code>compat.py</code>, <code>versions.py</code>','One requires-state rule and validated numeric version specifications.'),
            ('<code>planner.py</code>, <code>scheduling.py</code>','Z3 feasibility/optimization, conflict shrinking, concrete schedule/state validation.'),
            ('<code>ab.py</code>, <code>simulator.py</code>, <code>invariants.py</code>','Baseline slot transitions, fault sweeps, and retained invariant findings.'),
            ('<code>policy.py</code>, <code>recovery.py</code>','Exact downgrade permissions and bounded paths to original images.'),
            ('<code>boot_models.py</code>, <code>boot.py</code>, <code>boot_recovery.py</code>, <code>guarded_simulator.py</code>','Guarded boot metadata, health/availability, recovery, and confirmation faults.'),
            ('<code>boot_comparison.py</code>','Same-plan fault pairing, guarded-only coverage, improvements, and regressions.'),
            ('<code>llm/</code>','Provider boundary, extraction, source/schema checks, faithfulness, and grounded explanation.'),
            ('<code>graph.py</code>, <code>workflow_models.py</code>, <code>evidence.py</code>','Conditional orchestration, snapshots, facts, and human-review gate.'),
            ('<code>persistence/</code>, <code>access.py</code>, <code>shared.py</code>','Durable checkpoints/receipts, transactional decisions, operations, and authorization.'),
            ('<code>review_app.py</code>, <code>public_demo.py</code>, <code>app/</code>','Local/shared workspace and bounded public Streamlit entry points.'),
            ('<code>data/</code>, <code>evaluation.py</code>, <code>benchmark/</code>, <code>release_validation.py</code>, <code>tests/</code>','Synthetic truth, scoring, exhaustive oracles, release rehearsal, and regressions.')])
        +p('Public functions use type hints and docstrings. Clients and API keys remain outside graph state. Validation failures are explicit, and the deterministic core runs without model services or credentials.'))
    add('05 / DOMAIN DATA','Campaigns and source-linked constraints',
        p('Static configuration and runtime observation are separate. ECU records hold identity, current/target versions, and flash duration. ECUState holds slot A, slot B, and active selection. Each image has a version and a modeled validity flag. VehicleState adds battery and ignition.')
        +table(['Type','Meaning','Example'],[
            ('requires','Matching trigger versions require matching peer versions.','Brake ≥2 requires gateway ≥2.'),
            ('mutex','Named ECUs must not overlap write intervals.','Gateway and brake share a channel.'),
            ('precondition','The changed ECU needs the specified ignition and minimum battery.','Ignition off; battery at least 30%.'),
            ('order','The earlier ECU finishes and activates before the later write starts.','Gateway before brake.')])
        +p('Each constraint retains its ID, document ID, and original sentence. Extraction additionally cites a half-open character span in the immutable document. Code checks exact source segments and references instead of trusting a model-created sentence.')
        +code('Requires(\n    id="brake-needs-gateway",\n    ecu="brake", version_spec=">=2",\n    needs="gateway", needs_version_spec=">=2",\n    source_document_id="release-0",\n    source_text="brake at versions >=2 requires gateway at versions >=2."\n)')
        +p('A Plan retains write intervals, activation indices, slots, and the initial plus each nominal activation state. Simulation reports add actual intermediate slot contents, faults, findings, and recovery. Violations carry typed codes with ECU and source context.')
        +note('Authority separation','Documents cannot change the inventory or grant downgrade permission. Authorization is explicit ECU/version input, never an inferred approval extracted from release-note prose.'))
    add('06 / COMPATIBILITY','A valid destination is insufficient',
        p('A state is valid exactly when every applicable requires rule holds. Each is an implication: when an ECU matches its trigger version specification, the peer must match its required specification. All implications must hold together.')
        +code('for each requires rule r:\n    matches(state[r.ecu], r.version_spec)\n        implies matches(state[r.needs], r.needs_version_spec)')
        +p('compat.py defines the meaning once. The planner uses the shared rule for symbolic observations; concrete replay, invariants, and recovery check real states against the same definition. This prevents scheduling and fault checking from adopting inconsistent dependency semantics.')
        +table(['Observation','Gateway','Brake','Result'],[
            ('Initial','1','1','Compatible; ≥2 triggers inactive.'),
            ('Activate gateway first','2','1','Invalid: gateway ≥2 needs brake ≥2.'),
            ('Activate brake first','1','2','Invalid: brake ≥2 needs gateway ≥2.'),
            ('Desired final state','2','2','Compatible, but no allowed first activation reaches it.')])
        +p('Overlapping writes do not solve this trap. Writing inactive slots leaves effective versions unchanged; activations still execute one ECU at a time. With no atomic multi-ECU activation or bridge release, infeasibility is the correct result.')
        +'<h3>Versions and authorization</h3>'+p('Versions/specifications are parsed numerically. An older destination requires permission matching both ECU and destination version. Merely storing an older inactive image does not authorize installation. Fallback after successful newer exposure is still a downgrade.')
        +note('Unavailable is not absent','Guarded outages retain last effective versions for compatibility observations. Dependency availability is an additional operational check; it cannot erase a version implication.'))
    add('07 / LLM BOUNDARY','Extract, verify, and explain',
        p('One abstraction, llm/client.py, supports Ollama, Gemini, or Groq selected through LLM_PROVIDER. Role-specific models are configurable. Keys come from environment/.env settings and are excluded from serialized evidence. There is no silent provider substitution.')
        +table(['Stage','Control','Failure behavior'],[
            ('Extraction','Strict supported JSON; authoritative inventory and exact source segments; no hidden benchmark truth.','Malformed, unsupported, or ambiguous output blocks handoff.'),
            ('Schema/evidence','Reject invalid fields, references, specs, duplicate JSON keys, or citation spans.','No planning campaign while unresolved findings remain.'),
            ('Faithfulness','Separate model call reviews completeness/direction and records coverage IDs and issues.','Unfaithful or incomplete coverage blocks progression.'),
            ('Explanation','Code-generated facts and typed outcomes; advisory text must cite them and retain mandatory summaries.','Rejected/unavailable prose falls back to deterministic summaries.')])
        +p('Separate calls, even with different models, do not guarantee independence or correctness. Evaluation perturbations deliberately make both scripted passes omit or misstate a rule to expose correlated false acceptance.')
        +'<h3>Call evidence</h3>'+ul(
            'Origin (fixture/live), provider/model, role, prompt version, request hash, sanitized request/response, and finish reason.',
            'Raw JSON is retained; parsing does not silently repair malformed output or treat truncation as success.',
            'Fixture responses remain explicitly labeled. Their scores are harness checks, not live-model accuracy.')
        +note('Hard design rule','Models never decide compatibility, schedule writes, inject faults, search recovery, assess invariants, select review policies, or approve proposals.'))
    add('08 / PLANNING','Parallel scheduling with Z3',
        p('The planner assigns integer start/end times and a unique activation index to each changed ECU. It enforces duration, channel capacity, mutex, order, environment, image validity, exact downgrade permissions, and version requirements. Initial and every ordered post-activation state must be compatible.')
        +table(['Rule','Meaning'],[
            ('Overlap','Nonpreemptive half-open write intervals; an end can equal another start without overlap.'),
            ('Activation','At write completion; equal-time transitions execute in unique index order.'),
            ('Order','Before ECU completes and activates before after ECU starts writing, not just before its activation.'),
            ('No-op ECU','Equal numeric current/target versions need no flash step but remain in compatibility observations.'),
            ('Objective','Minimize makespan; prefer earlier starts/activation indices where the remaining budget permits tie-breaking.'),
            ('Validation','Concrete schedule checks and state replay validate every published feasible plan.')])
        +'<h3>Results remain distinct</h3>'+ul(
            '<b>Feasible:</b> validated nominal plan; optimal separately indicates whether minimum duration was proved.',
            '<b>Infeasible:</b> proved contradiction with source and/or explicit resource/policy groups.',
            '<b>Unknown:</b> feasibility not established within budget; never a proof of impossibility.')
        +p('Conflict shrinking seeks a subset-minimal core: removing any reported group makes that subset satisfiable relative to the fixed transition model. It is not necessarily a minimum-cardinality conflict. Budget-limited shrinking preserves the proved core without falsely claiming minimality.')
        +note('Budget precision','Feasibility, shrinking, optimization, and tie-breaking share a solver budget. Concrete replay/serialization can take additional time. A feasible plan may have unproved optimality and still says nothing by itself about recovery.'))
    add('09 / FAULT ANALYSIS','A/B simulation and invariants',
        p('The baseline simulator records actual slot contents and flash events. The previous active image continues running during inactive-slot erase/write/verify. Activation changes selection; faults can leave incomplete or invalid images that stay visible in the trace.')
        +table(['Fault','Applicable injection point / effect'],[
            ('Power loss','Before and after erase, write, verify, activate, and boot: ten cases per ECU. All writes in progress are affected, not only the addressed ECU.'),
            ('Write corruption','After write; the candidate cannot be treated as a verified valid target.'),
            ('Verification failure','Before verify; the unverified target is not activated.'),
            ('Activation failure','Before activation; the intended switch fails under defined baseline semantics.'),
            ('Boot failure','Before boot; baseline can expose an invalid active image, producing a historical violation.')])
        +p('The sweep contains <b>14 single-fault cases per planned ECU</b>. Reports validate expected coverage, unique causes, campaign identity, nominal completion, and consistency between findings and assessment. A truncated sweep cannot be labeled passed.')
        +table(['Invariant','Checked property'],[
            ('bootable_image','An active boot selection references an image marked valid.'),
            ('compatible_versions','Effective installed versions satisfy the shared requires rule.'),
            ('authorized_downgrade','Older effective installations/fallbacks have exact explicit permission.'),
            ('rollback_path','A failed step has a proved compatible route to original images, or reports a violation/unknown as appropriate.')])
        +p('Each finding retains the invariant, typed violation, ECU/source information, and trace index. Trace snapshots show time, flash stage, active slots, image validity, and simultaneous write activity. Reviewers can therefore inspect the transition behind a failure.')
        +note('History is retained','Recovery never erases an earlier invalid-image or incompatible-state finding. A fault-induced abort can preserve all modeled invariants; execution status and invariant assessment remain separate.'))
    add('10 / GUARDED BOOT','Trial health and authorized recovery',
        boot_diagram()
        +p('The guarded policy separates integrity, boot health, availability, and durable confirmed-slot metadata. A candidate becomes effective only after its boot-health check succeeds. A failed never-effective trial retains the current version; fallback after successful newer exposure still checks downgrade authorization.')
        +p('Confirmation is atomic in this model. Confirmed selection, observed health, and attempt count survive power loss; volatile runtime/candidate selection does not. Two confirmation power-loss boundaries increase guarded coverage to <b>16 cases per changed ECU</b>.')
        +p('Recovery searches known stored images and legal slot/runtime transitions to restore the original running confirmed configuration. Baseline recovery uses bounded breadth-first state search. Guarded recovery additionally respects health, confirmed metadata, trial limits, and peer availability. A search cap yields unknown, not an invented path.')
        +note('Guarded is not universally better','Mutually dependent unavailable ECUs can prevent guarded reboot even when versions are compatible. Such availability regressions stay visible. A healthy candidate does not guarantee that every peer can restart.'))
    add('11 / WORKFLOW & REVIEW','From analysis to a human decision',
        p('LangGraph builds the conditional pipeline with StateGraph, nodes/edges, a checkpointer, and interrupt_before=["human_review"]. Normal stages are extract → plan → simulate → optional compare_policies → explain → prepare_review → human_review. Blocked extraction and nonfeasible planning route to explanation/evidence without executing later analysis stages.')
        +p('State is serialized data. Provider clients and keys are injected outside checkpoints. A process lock serializes workflow planning because Z3’s default context is shared. The human-review service checks run, revision, snapshot hash, eligibility, and idempotency.')
        +table(['Review mode','Eligibility source','Schema'],[
            ('Legacy selection omitted','Original baseline gate; an enabled guarded comparison must also pass.','workflow-v1 / review-bundle-v1'),
            ('Explicit baseline-v1','Complete passing baseline nominal and fault evidence. A comparator cannot approve a failing baseline.','workflow-v2 / review-bundle-v2'),
            ('Explicit guarded-trial-v1','Complete passing guarded nominal and fault evidence, including confirmation cases. Baseline failures remain retained.','workflow-v2 / review-bundle-v2')])
        +p('The snapshot includes inputs, extraction, planning, simulation/comparison, facts, explanation, and rules. Its hash also binds run and revision. Changing source, policy, options, or permissions needs a new analysis revision. Prior decisions remain in history but no longer apply to the new proposal.')
        +ul('Approve is unavailable for blocked, infeasible, unknown, violating, or incomplete selected-policy evidence.',
            'Review with findings and reject do not change the deterministic assessment.',
            'Explanation text cannot choose a policy or create approval.',
            'The release demo and recovery rehearsal intentionally end with no human decision.')
        +note('Exact scope','Approval is a simulation-proposal record. It grants no downgrade permission and triggers no vehicle execution.'))
    add('12 / DURABILITY','Restart-safe evidence and decisions',
        p('WorkflowService uses in-memory checkpoints by default. PersistentWorkflowService optionally stores registry, immutable revisions, public client recipes, model-response receipts, snapshots/decisions, and LangGraph checkpoints in one local SQLite database. WAL, full synchronous writes, and short transactions support local durability.')
        +table(['Interruption boundary','Required behavior'],[
            ('Before a request','Commit request intent before contacting a provider. No SQL transaction spans a network call.'),
            ('Response saved; node not checkpointed','Replay the exact saved response instead of calling the provider again.'),
            ('Inflight or uncertain outcome','Stop automatic retry: the provider might have completed remotely. An explicit new revision is required.'),
            ('Decision committed; graph checkpoint lagging','SQL decision stays authoritative. Reopening shows it without duplicate approval.'),
            ('Uncommitted SQL decision','Rollback leaves no invented completed review.'),
            ('Changed runtime or corrupted evidence','Refuse incompatible execution/new decisions; supported completed history remains readable.')])
        +p('Request, input, recipe, snapshot, and version hashes detect accidental edits. Reconstruction recipes retain public settings or labeled fixture payloads, never API keys. A resumed uncached live role checks current public settings and reads credentials outside checkpoint state.')
        +'<h3>Operational lifecycle</h3>'+ul(
            'Explicit v1-to-v2 migration first makes a verified backup, then adds operational metadata transactionally.',
            'SQLite backup snapshots WAL commits. Restore verifies structure, hashes, registry, checkpoints, decisions, and provenance into a new path.',
            'Reviewed runs can be archived read-only without deleting receipts or history. Existing destinations are not overwritten.',
            'OS locks serialize single-host graph mutations and release on process death.')
        +note('Limits','No exactly-once remote-provider guarantee, multi-host SQLite support, signed audit proof, or automatic destructive purge is claimed.'))
    add('13 / ACCESS & HOSTING','Three operating surfaces',
        table(['Surface','Capabilities','Trust / lifetime'],[
            ('Local workspace','Editable source, fixture/live clients, scheduling options, optional durable library, self-reported review.','Trusted local operator; memory or explicit SQLite.'),
            ('Shared single-host mode','Streamlit-verified OIDC issuer/subject and server allowlist with reader, analyst, reviewer, admin grants.','Protected configuration; checks per operation and again at review commit.'),
            ('Public portfolio demo','Predefined synthetic cases, policy choice, 1–3 write channels, evidence download, session review.','No provider settings, uploads, arbitrary editor, or filesystem library. Eight analyses per session.')])
        +p('Shared review overrides typed names with authenticated identity. Role provenance commits atomically with the SQL decision. Readers cannot analyze/review; analysts cannot review without an additional grant. Unknown, revoked, and expired accounts are denied. Host operators with source/database access remain trusted.')
        +p('Authenticated portable exports use persistent-review-v2 and bind issuer/subject provenance to matching decisions. Historical self-reported names are never relabeled authenticated. Export IDs content-address the full envelope; they are not signatures.')
        +'<h3>Published demo URL</h3>'+p('<a href="https://ota-campaign-verifier.streamlit.app/">https://ota-campaign-verifier.streamlit.app/</a>')
        +p('The repository records this user-provided Streamlit Community Cloud URL. A previous check returned HTTP 200, but automated interactive rendering was not verified. This report performs no new uptime or live-SSO check.')
        +p('Public entry: app/public_demo.py. Local/shared entry: app/streamlit_app.py. Root requirements.txt installs the src-layout package. Actual secrets, .env, virtual environments, local state, and runtime databases are excluded from publication.')
        +note('Separate claims','Public demo availability does not establish passing remote CI or the separate shared-mode OIDC login/role/logout checks. Session-only review is not durable authenticated approval.'))
    result=evidence['test_results']
    add('14 / EVALUATION','What the evidence measures',
        p('Synthetic cases are ground truth first and messy text second. A frozen corpus adds separate development/held-out wording templates, canonical hashes, and required-abstention labels. Hidden gold enters scoring, never extraction/verification prompts.')
        +table(['Measure','Definition / interpretation'],[
            ('Per-type precision/recall','Normalized semantic multisets, accumulated per case. IDs/wording ignored; duplicates, omissions, and extra meanings are errors.'),
            ('Exact source spans','Match meaning plus document and offsets. Accuracy conditions on semantic matches; precision/recall penalize extra/missing constraints too.'),
            ('Schema rejection','Invalid strict JSON/schema among received extraction responses. Transport failures and citation failures are distinct.'),
            ('Faithfulness false acceptance','Faithful judgments on bad drafts / reviewed bad drafts. Empty denominators are null, not perfect accuracy.'),
            ('Downstream effects','False acceptance/infeasibility, unknowns, missed fault violations, and underlying case evidence.'),
            ('Reproducibility','Corpus, prompts/configuration, runtime/code fingerprints, raw outputs, and latency. Semantic digest excludes timing.')])
        +p('An independent bounded oracle enumerates starts/activation orders without Z3 or production schedule validation; compat.py intentionally remains shared. Scope: at most three monotonic 1-to-2/no-op ECUs, one/two-minute writes, integral-minute deadlines. Metamorphic tests check reordering, ID changes, capacity/deadline relaxation, and permission effects.')
        +table(['Recorded local observation','Qualification'],[
            (f"{result['tests']} passed; {result['failures']} failures; {result['errors']} errors",'Release full suite: Windows / Python 3.14.4; 14 upstream/cache warnings.'),
            ('11/11 deterministic checks; 252 core fault cases','Frozen reference benchmark.'),
            ('12 extraction fixtures: 8 ready, 4 abstentions','Canned-response regression, not live-model performance.'),
            ('Windows/Linux, Python 3.11–3.14 CI matrix','Configured; no passing remote result asserted by the release record.')])
        +'<p class="small">Source: docs/release-evidence.json and eval/baseline_v1.json. Later targeted UI/hosting tests are separate. PDF generation does not rerun or imply a newer full-suite result.</p>')
    add('15 / DEMONSTRATION A','Parallel writes, ordered activation',
        figure('parallel-plan.png','Actual Streamlit UI • synthetic fixture • baseline policy • no human decision recorded.')
        +p('The UI fixture performs six ECU-minutes of writing in four simulated minutes with two channels. Infotainment overlaps gateway; brake waits for its dependency. The initial and every activation state are compatible. The overall baseline assessment still contains fault violations, separating nominal planning from resilience.')
        +note('Do not mix fixtures','examples/parallel_campaign.json is a separate input: nine ECU-minutes with five-minute makespan. The four-minute result here belongs to the recorded UI/release example, not every parallel campaign.'))
    add('16 / DEMONSTRATION B','Why the solver rejects a route',
        figure('intermediate-conflict.png','Actual Streamlit UI • original source sentences • proved subset-minimal dependency conflict.')
        +p('Both target versions are compatible together, but each new version requires the other ECU already updated. Either first activation violates a dependency. Since one-at-a-time activation is part of this model, there is no feasible route.')
        +p('Both source rules and IDs remain visible. Removing either rule makes the reported subset satisfiable relative to the fixed model. The tool does not silently drop a requirement or invent atomic activation to manufacture a successful plan.'))
    add('17 / DEMONSTRATION C','Guarded improvement, baseline retained',
        figure('guarded-recovery.png','Actual Streamlit UI • explicit guarded selection • retained baseline violations • human review pending.')
        +p('Authorized rollback compares 42 shared fault causes and adds six confirmation faults, giving 48 guarded cases. Its guarded sweep passes under the stated assumptions; the baseline keeps its violations. Three paired boot-failure outcomes improve; this example has no paired regressions.')
        +p('Original-version permissions are explicit synthetic input. Removing them or adding dependency-availability cycles can block guarded recovery. The result supports only the selected policy and modeled assumptions, not a blanket claim about OTA updates.'))
    add('18 / OPERATING GUIDE','Run, inspect, and preserve evidence',
        '<h3>Install and start the local workspace</h3>'
        +code('python -m venv .venv\n.\\.venv\\Scripts\\python -m pip install -e ".[dev]"\n.\\.venv\\Scripts\\python -m streamlit run app/streamlit_app.py')
        +p('Load example replaces draft source/inventory and matching fixture selection. A pre-render callback confirms loading and opens the editor. Chosen policy/limits stay; analysis does not run automatically. Analyze revision explicitly before reviewing changed inputs.')
        +'<h3>Inspect deterministic planning and testing</h3>'
        +code('.\\.venv\\Scripts\\python -m ota_verifier.cli examples/parallel_campaign.json --max-parallel 2\n.\\.venv\\Scripts\\python -m ota_verifier.benchmark.runner --mode core --fail-on-findings\n.\\.venv\\Scripts\\python -m pytest -q')
        +'<h3>Create a fresh release evidence pack</h3>'
        +code('.\\.venv\\Scripts\\python -m ota_verifier.release_validation --output runs/my-release')
        +p('The builder checks three demo stories and rehearses migration, pause/resume, exact response reuse, live-WAL backup, and equality after restore. JSON reports, databases/manifests, and a SHA256 artifact index go to a new directory. No human approval is fabricated. Local checks can pass while external release gates stay pending.')
        +'<h3>Preserve a durable workspace</h3>'
        +code('.\\.venv\\Scripts\\python -m ota_verifier.persistence.operations verify .ota_state/reviews.sqlite\n.\\.venv\\Scripts\\python -m ota_verifier.persistence.operations backup .ota_state/reviews.sqlite --destination .ota_state/backup.sqlite')
        +p('Restore into a new path. Shared mode additionally needs explicit migration, protected OIDC settings, and a server allowlist. Do not publish credentials or use a free public session as a persistent evidence archive.'))
    add('19 / LIMITS & SOURCE GUIDE','Interpretation and future work',
        p('Conclusions depend on correct extraction, supplied inventories, bounded transitions, and complete modeled coverage. Two model calls can agree on the same error. Schema validity is not semantic truth; human review and independent evaluation remain necessary.')
        +ul('Not modeled: real signing/attestation, bootloader/hardware flashing, watchdog timing, torn confirmation metadata, multiple independent faults in a run, bandwidth/power/thermal behavior, bridge releases, or fleet execution.',
            'Tests, approval records, screenshots, and a public URL do not establish vehicle behavior or certification.',
            'Hashes detect accidental changes, not a hostile host rewriting data and hashes. Source/model evidence and backups are plaintext.',
            'Remote CI and genuine shared-mode OIDC checks remain pending in recorded release evidence; HTTP success is not end-to-end workflow validation.')
        +'<h3>Useful next work</h3>'
        +p('Complete external CI and identity checks first, then evaluate independently reviewed representative documents. Resource-aware timing, bounded availability, bridge-release proposals, and fleet simulation are possible extensions after their semantics and regression criteria are defined; they are not presented as implemented.')
        +'<h3>Repository reading guide</h3>'
        +table(['Source','Purpose'],[
            ('README.md; docs/architecture.md','Overview, measured examples, and system boundaries.'),
            ('docs/phase4.md–phase6.md','Extraction, workflow, guarded boot, and comparisons.'),
            ('docs/phase7.md–phase10.md','Persistence, metrics, policy-specific reviews, shared access, operations.'),
            ('docs/phase11.md; docs/release-evidence.json','Recorded release artifacts, measurements, and external gates.'),
            ('docs/deploy_free.md; docs/demo_walkthrough.md','Hosting URL, bounded demo, and walkthrough.'),
            ('src/ota_verifier/; tests/; eval/','Implementation, exhaustive/regression checks, and baselines.')])
        +'<p class="small">Glossary: ECU = electronic control unit; OTA = over-the-air; SDV = software-defined vehicle; A/B = alternate image slots; SAT/UNSAT = satisfiable/unsatisfiable; OIDC = OpenID Connect; WAL = write-ahead log. Prepared 6 November 2026 from local source and recorded synthetic evidence.</p>')
    return pages


CSS = """
@page{size:A4;margin:16mm 15mm 20mm}
*{box-sizing:border-box}body{margin:0;color:#193041;font:10pt/1.43 Arial,Helvetica,sans-serif}
.sheet{break-after:page}.sheet:last-child{break-after:auto}
.eyebrow{font-size:8pt;letter-spacing:1.4px;color:#087f8c;font-weight:700;margin-bottom:10px}
h1{font-size:27pt;line-height:1.12;letter-spacing:-.7px;color:#142334;margin:0 0 18px}
h3{font-size:12pt;color:#087f8c;margin:17px 0 7px}p{margin:0 0 11px}a{color:#087f8c;text-decoration:none}
code{font:8.3pt Consolas,monospace;overflow-wrap:anywhere}
pre{font:8pt/1.5 Consolas,monospace;background:#f0f4f7;border-left:3px solid #087f8c;padding:11px;white-space:pre-wrap;overflow-wrap:anywhere;margin:9px 0 12px}
table{border-collapse:collapse;width:100%;font-size:8.7pt;margin:10px 0 14px}th{text-align:left;background:#153b49;color:white;font-weight:600;padding:8px}td{vertical-align:top;padding:8px;border-bottom:1px solid #d9e2e8}tr:nth-child(even)td{background:#f4f7f9}tr{break-inside:avoid}
ul{padding-left:18px;margin:7px 0 12px}li{margin-bottom:7px}aside{background:#e7f4f1;border-left:4px solid #087f8c;padding:12px;margin:14px 0;font-size:9.4pt;break-inside:avoid}
figure{margin:12px 0 16px;break-inside:avoid}figure img{width:100%;border:1px solid #d5dfe7;border-radius:6px}figcaption{font-size:8pt;color:#526b7a;margin-top:7px}
.small{font-size:8.2pt;color:#526b7a}.architecture{width:100%;height:535px}svg text{font-family:Arial,Helvetica,sans-serif;fill:#193041}.boot{width:100%;height:285px}
.cover h1{font-size:49pt;margin-top:45px;line-height:1.03}.subtitle{font-size:21pt;line-height:1.3;color:#456578;margin:26px 0}.cover-rule{width:100%;height:7px;background:#087f8c;margin:30px 0}
.cover-grid{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin:28px 0}.cover-grid div{background:#f0f4f7;border-radius:7px;padding:16px;font-size:10pt}.cover-grid b{color:#087f8c}.cover aside{margin-top:35px}
"""


def build() -> tuple[Path, Path, int]:
    """Render offline, reject overflow, and create a tagged, page-numbered PDF."""
    evidence=json.loads((ROOT/'docs/release-evidence.json').read_text(encoding='utf-8-sig'))
    content=report_pages(evidence)
    html=ROOT/'docs/OTA_Campaign_Verifier_Project_Report.html'
    pdf=ROOT/'docs/OTA_Campaign_Verifier_Project_Report.pdf'
    sections=''.join(f'<section class="sheet {"cover" if i==0 else ""}"><div class="eyebrow">{label}</div><h1>{title}</h1>{body}</section>' for i,(label,title,body) in enumerate(content))
    html.write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><title>OTA Campaign Verifier - Project and Architecture Report</title><style>'+CSS+'</style></head><body>'+sections+'</body></html>',encoding='utf-8')
    with sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        page=browser.new_page(viewport={'width':800,'height':1100})
        page.route('http**/*',lambda route:route.abort())
        page.goto(html.as_uri(),wait_until='load')
        page.emulate_media(media='print')
        page.evaluate('document.fonts.ready')
        overflow=page.locator('.sheet').evaluate_all('(nodes)=>nodes.map((n,i)=>({page:i+1,height:n.getBoundingClientRect().height})).filter(x=>x.height>986)')
        if overflow:
            browser.close()
            raise RuntimeError('A4 content overflow: '+json.dumps(overflow))
        page.pdf(path=str(pdf),prefer_css_page_size=True,print_background=True,display_header_footer=True,
            header_template='<div></div>',
            footer_template='<div style="font:8px Arial;color:#607887;width:100%;margin:0 16mm;display:flex;justify-content:space-between"><span>OTA CAMPAIGN VERIFIER · SIMULATION · 6 NOV 2026</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
            tagged=True,outline=True)
        page.emulate_media(media='screen')
        (ROOT/'runs').mkdir(exist_ok=True)
        page.locator('.sheet').first.screenshot(path=str(ROOT/'runs/project-report-cover.png'))
        browser.close()
    data=pdf.read_bytes()
    count=len(re.findall(rb'/Type\s*/Page\b',data))
    if not data.startswith(b'%PDF-') or count!=len(content):
        raise RuntimeError(f'Unexpected PDF page count {count}; expected {len(content)}')
    return html,pdf,count


if __name__=='__main__':
    html,pdf,count=build()
    sys.stdout.write(json.dumps({'html':str(html),'pdf':str(pdf),'pages':count,'bytes':pdf.stat().st_size},indent=2)+'\n')
