"""Ground-truth-first synthetic document cases; no LLM calls or solver use."""
import argparse
from pathlib import Path
import random
from typing import Literal
from pydantic import model_validator
from ..models import Campaign, Constraint, ECU, ECUState, Image, Mutex, Order, Precondition, Record, Requires, VehicleState
from ..llm.evidence import source_segments
from ..llm.models import (DocumentRequest, ExtractedConstraint, ExtractionDraft, ExtractionIssue,
                          FaithfulnessVerdict, SourceDocument, VerificationIssue)

Scenario = Literal['clear', 'dependency_only', 'order_conflict', 'intermediate_trap', 'ambiguous', 'unsupported']
SCENARIOS: tuple[Scenario, ...] = ('clear', 'dependency_only', 'order_conflict', 'intermediate_trap', 'ambiguous', 'unsupported')


class SyntheticCase(Record):
    """Gold labels and canned reference output; only request is sent to the LLM."""
    id: str
    scenario: Scenario
    request: DocumentRequest
    truth_campaign: Campaign
    expected_blocked: bool
    reference_draft: ExtractionDraft
    reference_verdict: FaithfulnessVerdict

    @model_validator(mode='after')
    def matching_inventory(self) -> 'SyntheticCase':
        """Keep gold labels separate while retaining identical authoritative inventory."""
        if self.request.campaign.model_dump(exclude={'constraints'}) != self.truth_campaign.model_dump(exclude={'constraints'}):
            raise ValueError('Ground truth and request inventory disagree')
        return self


def _rules(scenario: Scenario) -> tuple[Constraint, ...]:
    common = dict(source_document_id='unrendered', source_text='unrendered')
    dependency = Requires(id='brake-needs-gateway', ecu='brake', version_spec='>=2', needs='gateway', needs_version_spec='>=2', **common)
    if scenario == 'clear':
        return (dependency, Mutex(id='shared-channel', ecus=('gateway', 'brake'), **common),
                Precondition(id='parked-charged', ecu='gateway', ignition='off', minimum_battery_percent=30, **common))
    if scenario == 'dependency_only':
        return (dependency,)
    if scenario == 'order_conflict':
        return (Order(id='gateway-first', before='gateway', after='brake', **common),
                Order(id='brake-first', before='brake', after='gateway', **common))
    if scenario == 'intermediate_trap':
        return (dependency, Requires(id='gateway-needs-brake', ecu='gateway', version_spec='>=2',
                                    needs='brake', needs_version_spec='>=2', **common))
    if scenario == 'ambiguous':
        # Hidden intended order exists, but the intentionally vague rendering does
        # not justify guessing it. Correct behavior is to request clarification.
        return (Order(id='intended-gateway-first', before='gateway', after='brake', **common),)
    return ()  # Unsupported Wi-Fi condition is represented by expected_blocked.


def _render(rule: Constraint, rng: random.Random) -> str:
    if isinstance(rule, Requires):
        if rng.randrange(2):
            return f'{rule.ecu} at versions {rule.version_spec} requires {rule.needs} at versions {rule.needs_version_spec}.'
        return f'When {rule.ecu} runs {rule.version_spec}, {rule.needs} must run {rule.needs_version_spec}.'
    if isinstance(rule, Mutex):
        return f'Do not flash {rule.ecus[0]} and {rule.ecus[1]} at the same time.'
    if isinstance(rule, Order):
        return f'{rule.before} must finish flashing and activate before {rule.after} starts flashing.'
    return f'Flashing {rule.ecu} requires ignition {rule.ignition} and battery at least {rule.minimum_battery_percent:g} percent.'


def generate_case(scenario: Scenario = 'clear', seed: int = 0) -> SyntheticCase:
    """Choose formal rules first, then render noisy text with exact source spans."""
    if scenario not in SCENARIOS:
        raise ValueError('Unknown synthetic scenario')
    rng = random.Random(seed)
    rules = _rules(scenario)
    case_id = f'{scenario}-{seed}'
    release_id, guide_id = f'release-{seed}', f'guide-{seed}'
    assignments = [(rule, guide_id if isinstance(rule, (Mutex, Precondition)) else release_id,
                    _render(rule, rng)) for rule in rules]
    review_text = ('Update gateway first where required.' if scenario == 'ambiguous' else
                   'Flashing gateway requires a reliable garage Wi-Fi connection.' if scenario == 'unsupported' else None)
    if scenario == 'ambiguous':
        assignments = [(rule, release_id, review_text) for rule in rules]
    release_lines = [f'Synthetic release record {seed}.', 'Display theme and log wording were refreshed.']
    guide_lines = ['Synthetic ECU installation guide.', 'Retain these notes with the campaign record.']
    for _, document_id, sentence in assignments:
        (release_lines if document_id == release_id else guide_lines).append(sentence)
    if scenario == 'unsupported':
        guide_lines.append(review_text)
    # Whitespace changes do not change gold semantics; indices refer to exact text.
    separator = rng.choice(['\n', '\n\n', '\n  '])
    documents = (SourceDocument(id=release_id, text=separator.join(release_lines)),
                 SourceDocument(id=guide_id, text=separator.join(guide_lines)))
    durations = {'gateway': 3.0, 'brake': 1.0, 'infotainment': float(rng.randint(2, 4))}
    inventory = Campaign(id=case_id,
        ecus=tuple(ECU(id=name, current_version='1', target_version='2', flash_minutes=duration)
                   for name, duration in durations.items()),
        initial_state=VehicleState(ecus=tuple(ECUState(ecu_id=name, slot_a=Image(version='1'),
            slot_b=None, active_slot='A') for name in durations), battery_percent=80, ignition='off'))
    request = DocumentRequest(campaign=inventory, documents=documents)
    sourced: list[Constraint] = []
    extracted: list[ExtractedConstraint] = []
    for rule, document_id, sentence in assignments:
        document = next(document for document in documents if document.id == document_id)
        segment = next(segment for segment in source_segments(document) if segment.text == sentence)
        actual = type(rule)(**rule.model_dump(exclude={'source_document_id', 'source_text'}),
                            source_document_id=document_id, source_text=sentence)
        sourced.append(actual)
        if scenario != 'ambiguous':
            extracted.append(ExtractedConstraint(constraint=actual, evidence=segment.evidence))
    extraction_issues: tuple[ExtractionIssue, ...] = ()
    verification_issues: tuple[VerificationIssue, ...] = ()
    blocked = scenario in ('ambiguous', 'unsupported')
    if blocked:
        segment = next(segment for document in documents for segment in source_segments(document) if segment.text == review_text)
        kind = 'ambiguous_requirement' if scenario == 'ambiguous' else 'unsupported_requirement'
        message = 'Clarify the intended order' if scenario == 'ambiguous' else 'Wi-Fi is outside the supported precondition model'
        extraction_issues = (ExtractionIssue(kind=kind, evidence=segment.evidence, source_text=segment.text, message=message),)
        verification_issues = (VerificationIssue(kind=kind, constraint_id=None, evidence=segment.evidence,
                                                source_text=segment.text, message=message),)
    truth = Campaign(id=inventory.id, ecus=inventory.ecus, initial_state=inventory.initial_state, constraints=tuple(sourced))
    draft = ExtractionDraft(constraints=tuple(extracted), issues=extraction_issues)
    verdict = FaithfulnessVerdict(faithful=not blocked,
        reviewed_constraint_ids=tuple(entry.constraint.id for entry in extracted),
        reviewed_document_ids=tuple(document.id for document in documents), issues=verification_issues)
    return SyntheticCase(id=case_id, scenario=scenario, request=request, truth_campaign=truth,
                         expected_blocked=blocked, reference_draft=draft, reference_verdict=verdict)


def generate_cases(seed: int = 0, count: int = 6) -> tuple[SyntheticCase, ...]:
    """Generate reproducible cases cycling through six labeled scenarios."""
    if count <= 0:
        raise ValueError('Synthetic case count must be positive')
    return tuple(generate_case(SCENARIOS[index % len(SCENARIOS)], seed + index) for index in range(count))


def main(argv: list[str] | None = None) -> int:
    """Write separate source-only request files and labeled benchmark case files."""
    parser = argparse.ArgumentParser(description='Generate synthetic OTA documents from ground truth')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=0)
    parser.add_argument('--count', type=int, default=6)
    args = parser.parse_args(argv)
    if args.count <= 0:
        parser.error('--count must be positive')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for case in generate_cases(args.seed, args.count):
        for suffix, record in (('case', case), ('request', case.request)):
            target = args.output_dir / f'{case.id}.{suffix}.json'
            if target.exists():
                raise FileExistsError(f'Refusing to overwrite {target}')
            target.write_text(record.model_dump_json(indent=2) + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
