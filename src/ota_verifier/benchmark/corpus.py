"""Frozen, ground-truth-first corpus loading and explicit regeneration."""
from importlib.resources import files
from typing import Literal
from ..data.generate import SyntheticCase, generate_case
from ..llm.evidence import canonical_json, content_hash, source_segments
from ..llm.models import DocumentRequest, ExtractedConstraint, ExtractionDraft, SourceDocument
from ..models import Campaign, Constraint, DowngradeAuthorization, ECU, ECUState, Image, Mutex, Order, PlanningOptions, Precondition, Record, Requires, VehicleState

CORPUS_VERSION = 'ota-benchmark-v1'
CORPUS_SEED = 42
# Pinned after generating the reviewed v1 artifact; changes require a new version.
CORPUS_SHA256 = '7a8a5008b3005a870f377b0bf7ea536c51b48dfc6a9a3419ed167f770d713ff1'


class CoreCase(Record):
    """A labeled deterministic campaign and its explicitly bounded expectations."""
    id: str
    tags: tuple[str, ...]
    campaign: Campaign
    options: PlanningOptions
    expected_planning: Literal['feasible', 'infeasible']
    expected_makespan_ms: int | None
    expected_baseline: Literal['passed', 'violations', 'not_run']
    expected_rollback_unavailable: bool


class Corpus(Record):
    """Disjoint wording splits plus deterministic scenario labels."""
    version: Literal['ota-benchmark-v1'] = CORPUS_VERSION
    seed: int = CORPUS_SEED
    development: tuple[SyntheticCase, ...]
    heldout: tuple[SyntheticCase, ...]
    core: tuple[CoreCase, ...]


def corpus_hash(corpus: Corpus) -> str:
    """Hash parsed canonical content, independent of platform line endings."""
    return content_hash(canonical_json(corpus.model_dump(mode='json')))


def load_corpus() -> Corpus:
    """Load the packaged frozen artifact and reject unversioned edits."""
    raw = files('ota_verifier.data').joinpath('benchmark_v1.json').read_text(encoding='utf-8-sig')
    corpus = Corpus.model_validate_json(raw)
    if corpus_hash(corpus) != CORPUS_SHA256:
        raise ValueError('Frozen benchmark corpus hash mismatch; do not silently rewrite labels')
    ids = [case.id for case in (*corpus.development, *corpus.heldout, *corpus.core)]
    if len(ids) != len(set(ids)):
        raise ValueError('Benchmark case IDs must be unique across splits')
    return corpus


def _heldout(scenario: str, seed: int) -> SyntheticCase:
    base = generate_case(scenario, seed)
    sentences: list[str] = []
    rules = []
    for rule in base.truth_campaign.constraints:
        if isinstance(rule, Requires):
            text = f'A {rule.ecu} image matching {rule.version_spec} may run only if {rule.needs} matches {rule.needs_version_spec}.'
        elif isinstance(rule, Mutex):
            text = f'The flash-write windows for {rule.ecus[0]} and {rule.ecus[1]} shall be disjoint.'
        elif isinstance(rule, Precondition):
            text = f'Before starting {rule.ecu}: ignition must be {rule.ignition}; battery charge must be no less than {rule.minimum_battery_percent:g}%.'
        else:
            text = f'Starting {rule.after} is permitted only once {rule.before} has completed its write and activation.'
        sentences.append(text)
        rules.append(rule)
    if base.expected_blocked:
        text = ('Prefer doing gateway earlier when appropriate.' if scenario == 'ambiguous' else
                'Do not begin the gateway write without an available garage Wi-Fi link.')
        sentences = [text]
    document = SourceDocument(id=f'heldout-{seed}', text='Held-out simulation wording.\nCosmetic log changes only.\n' + '\n'.join(sentences))
    segments = {segment.text: segment for segment in source_segments(document)}
    sourced = tuple(type(rule)(**rule.model_dump(exclude={'source_document_id', 'source_text'}),
        source_document_id=document.id, source_text=text) for rule, text in zip(rules, sentences, strict=True)) if scenario != 'unsupported' else ()
    truth = Campaign(**base.truth_campaign.model_dump(exclude={'constraints'}), constraints=sourced)
    request = DocumentRequest(campaign=base.request.campaign, documents=(document,))
    entries = tuple(ExtractedConstraint(constraint=rule, evidence=segments[rule.source_text].evidence)
                    for rule in sourced) if not base.expected_blocked else ()
    issues = tuple(issue.model_copy(update={'evidence': segments[sentences[0]].evidence, 'source_text': sentences[0]})
                   for issue in base.reference_draft.issues)
    verdict = base.reference_verdict.model_copy(update={
        'reviewed_document_ids': (document.id,), 'reviewed_constraint_ids': tuple(entry.constraint.id for entry in entries),
        'issues': tuple(issue.model_copy(update={'evidence': segments[sentences[0]].evidence, 'source_text': sentences[0]})
                        for issue in base.reference_verdict.issues)})
    return SyntheticCase(id=f'heldout-{scenario}-{seed}', scenario=scenario, request=request,
        truth_campaign=truth, expected_blocked=base.expected_blocked,
        reference_draft=ExtractionDraft(constraints=entries, issues=issues), reference_verdict=verdict)


def build_corpus() -> Corpus:
    """Construct v1 labels before rendering; normal evaluation loads the frozen file."""
    scenarios = ('clear', 'dependency_only', 'order_conflict', 'intermediate_trap', 'ambiguous', 'unsupported')
    development = tuple(generate_case(name, CORPUS_SEED + index) for index, name in enumerate(scenarios))
    heldout = tuple(_heldout(name, CORPUS_SEED + 100 + index) for index, name in enumerate(scenarios))
    ecus = tuple(ECU(id=name, current_version='1', target_version='2', flash_minutes=duration)
                 for name, duration in (('a', 2.0), ('b', 1.0), ('c', 2.0)))
    state = VehicleState(ecus=tuple(ECUState(ecu_id=ecu.id, slot_a=Image(version='1'), slot_b=None, active_slot='A') for ecu in ecus), battery_percent=80, ignition='off')
    source = {'source_document_id': 'core-spec', 'source_text': 'Explicit synthetic ground-truth constraint.'}
    dependency = Requires(id='b-needs-a', ecu='b', version_spec='>=2', needs='a', needs_version_spec='>=2', **source)
    rows: list[CoreCase] = []
    def add(identifier: str, tags: tuple[str, ...], rules: tuple[Constraint, ...] = (), *, parallel: int = 2,
            deadline: int | None = None, optimum: int | None = 180000, authorize: bool = False,
            no_updates: bool = False, low_battery: bool = False) -> None:
        inventory = tuple(ecu.model_copy(update={'target_version': '1'}) for ecu in ecus) if no_updates else ecus
        permissions = tuple(DowngradeAuthorization(ecu_id=ecu.id, version='1', authorized_by='synthetic-label', reason='Explicit original-version recovery permission') for ecu in ecus) if authorize else ()
        campaign = Campaign(id=identifier, ecus=inventory, initial_state=state.model_copy(update={'battery_percent': 10.0}) if low_battery else state,
                            constraints=rules, downgrade_authorizations=permissions)
        rows.append(CoreCase(id=identifier, tags=tags, campaign=campaign,
            options=PlanningOptions(max_parallel=parallel, deadline_ms=deadline),
            expected_planning='infeasible' if optimum is None else 'feasible', expected_makespan_ms=optimum,
            expected_baseline='not_run' if optimum is None else 'passed' if no_updates else 'violations',
            expected_rollback_unavailable=optimum is not None and not no_updates and not authorize))
    add('core-parallel', ('parallel', 'compatible_intermediate'), (dependency,))
    add('core-serial', ('concurrency_limit',), (dependency,), parallel=1, optimum=300000)
    add('core-deadline', ('deadline', 'infeasible'), (dependency,), deadline=120000, optimum=None)
    add('core-intermediate-trap', ('dependency_cycle', 'incompatible_intermediate', 'infeasible'),
        (dependency, Requires(id='a-needs-b', ecu='a', version_spec='>=2', needs='b', needs_version_spec='>=2', **source)), optimum=None)
    add('core-stable-cycle', ('dependency_cycle', 'compatible_intermediate'),
        (Requires(id='stable-a', ecu='a', version_spec='>=1', needs='b', needs_version_spec='>=1', **source),
         Requires(id='stable-b', ecu='b', version_spec='>=1', needs='a', needs_version_spec='>=1', **source)))
    add('core-order-cycle', ('order_cycle', 'infeasible'),
        (Order(id='a-first', before='a', after='b', **source), Order(id='b-first', before='b', after='a', **source)), optimum=None)
    add('core-mutex', ('mutex',), (Mutex(id='channel', ecus=('a', 'c'), **source),), optimum=240000)
    add('core-precondition', ('precondition', 'infeasible'),
        (Precondition(id='charge', ecu='a', ignition='off', minimum_battery_percent=30, **source),), low_battery=True, optimum=None)
    add('core-rollback-trap', ('rollback_trap', 'unauthorized_rollback'), (dependency,))
    add('core-authorized-recovery', ('authorized_rollback', 'baseline_boot_failure'), (dependency,), authorize=True)
    add('core-no-updates', ('zero_fault_coverage',), (), optimum=0, no_updates=True)
    return Corpus(development=development, heldout=heldout, core=tuple(rows))
