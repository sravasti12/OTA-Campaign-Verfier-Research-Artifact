"""Seeded synthetic workloads with constructive or analytic ground truth."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import random
from typing import Any

from ota_verifier.compat import check_compatibility
from ota_verifier.models import (Campaign, ECUState, Image, Order, Plan, PlanningOptions,
                                 PlanStep, Precondition, VehicleState)
from ota_verifier.policy import version_change_allowed
from ota_verifier.scheduling import constraint_ecus, validate_plan
from ota_verifier.versions import parse_version

FAMILIES = ('independent', 'sparse', 'dense', 'mixed_versions', 'resource', 'chain',
            'cycle', 'mutex_order', 'environment', 'downgrade')
SIZES = (10, 30, 50, 100)
SEEDS = (11, 29, 47)


def canonical(value: Any) -> str:
    """Serialize evidence deterministically without platform newline conversion."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value: Any) -> str:
    """Hash canonical data, not formatting or platform-dependent line endings."""
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def milliseconds(minutes: float) -> int:
    """Independently compute rounded-up model durations for witness construction."""
    from decimal import Decimal, ROUND_CEILING
    return int((Decimal(str(minutes)) * 60000).to_integral_value(rounding=ROUND_CEILING))


def project(state: VehicleState, identifier: str, version: str) -> VehicleState:
    """Construct an activation observation without production activation helpers."""
    changed = []
    for ecu in state.ecus:
        if ecu.ecu_id != identifier:
            changed.append(ecu)
        else:
            image = Image(version=version)
            changed.append(ECUState(ecu_id=identifier, active_slot='B' if ecu.active_slot == 'A' else 'A',
                slot_a=image if ecu.active_slot == 'B' else ecu.slot_a,
                slot_b=image if ecu.active_slot == 'A' else ecu.slot_b))
    return VehicleState(ecus=tuple(changed), battery_percent=state.battery_percent, ignition=state.ignition)


def sequential_plan(campaign: Campaign, options: PlanningOptions, order: tuple[str, ...]) -> Plan:
    """Materialize a declared witness with independently constructed state transitions."""
    configs = {ecu.id: ecu for ecu in campaign.ecus}
    states = [campaign.initial_state]
    steps = []
    elapsed = 0
    for identifier in order:
        ecu = configs[identifier]
        if parse_version(ecu.current_version) == parse_version(ecu.target_version):
            continue
        active = next(item.active_slot for item in states[-1].ecus if item.ecu_id == identifier)
        end = elapsed + milliseconds(ecu.flash_minutes)
        steps.append(PlanStep(ecu_id=identifier, from_version=ecu.current_version, to_version=ecu.target_version,
            write_slot='B' if active == 'A' else 'A', start_ms=elapsed, end_ms=end,
            activation_index=len(steps)+1,
            constraint_ids=tuple(rule.id for rule in campaign.constraints if identifier in constraint_ecus(rule))))
        states.append(project(states[-1], identifier, ecu.target_version))
        elapsed = end
    return Plan(campaign_id=campaign.id, steps=tuple(steps), states=tuple(states),
                makespan_ms=elapsed, optimal=False, options=options)


@dataclass(frozen=True)
class Workload:
    """Frozen generated input and gold explanation, never derived from solver output."""
    campaign: Campaign
    options: PlanningOptions
    metadata: dict[str, Any]
    witness_order: tuple[str, ...]
    certificate: dict[str, Any]

    def payload(self) -> dict[str, Any]:
        """Export schema-valid input plus explicit synthetic provenance and gold."""
        return {'format': 'scalability-workload-v1', 'campaign': self.campaign.model_dump(mode='json'),
                'options': self.options.model_dump(mode='json'), 'metadata': self.metadata,
                'witness_order': self.witness_order, 'certificate': self.certificate}


def generate(family: str, size: int, seed: int, *, variant: str = 'primary', timeout_ms: int = 10000) -> Workload:
    """Generate a reproducible topology, then verify its independent gold label."""
    if family not in FAMILIES or size < 2:
        raise ValueError('Unknown family or fewer than two ECUs')
    variants = {'primary', 'benign_cycle', 'order_chain', 'tight_deadline', 'relaxed_deadline',
                'allowed_environment', 'authorized_downgrade', 'half_noop', 'rounding'}
    if variant not in variants or (variant != 'primary' and (family, variant) not in {
        ('cycle', 'benign_cycle'), ('chain', 'order_chain'), ('mutex_order', 'tight_deadline'),
        ('mutex_order', 'relaxed_deadline'), ('environment', 'allowed_environment'),
        ('downgrade', 'authorized_downgrade'), ('independent', 'half_noop'), ('independent', 'rounding')}):
        raise ValueError('Variant does not belong to this workload family')
    rng = random.Random(seed)
    names = [f'ecu{i:03d}' for i in range(size)]
    order = names.copy()
    rng.shuffle(order)
    durations = {key: float(rng.choice((1, 2, 5))) for key in names}
    if variant == 'rounding':
        durations[names[0]] = 0.00001
    current = {key: '1' for key in names}
    target = {key: '2' for key in names}
    authorizations: list[dict[str, str]] = []
    if family == 'mixed_versions':
        for key in order[::3]:
            current[key], target[key] = '2', '1'
            authorizations.append(dict(ecu_id=key, version='1', authorized_by='synthetic-generator', reason='Explicit mixed-version fixture permission'))
    if family == 'downgrade':
        current[names[0]], target[names[0]] = '2', '1'
        if variant == 'authorized_downgrade':
            authorizations.append(dict(ecu_id=names[0], version='1', authorized_by='synthetic-generator', reason='Paired authorized control'))
    if variant == 'half_noop':
        for key in names[::2]:
            target[key] = current[key]
    rules: list[dict[str, Any]] = []

    def add(kind: str, **fields: Any) -> None:
        index = len(rules)
        rules.append(dict(type=kind, id=f'r{index:05d}', source_document_id='synthetic-ground-truth',
            source_text=f'Synthetic benchmark requirement {index}: {canonical(fields)}.', **fields))

    if family in ('sparse', 'dense', 'resource'):
        probability = 0.5 if family == 'dense' else 0.05
        for i, key in enumerate(order):
            for peer in order[:i]:
                if rng.random() < probability:
                    add('requires', ecu=key, version_spec='>=2', needs=peer, needs_version_spec='>=2')
    if family == 'mixed_versions':
        for i, key in enumerate(order):
            if target[key] == '2' and i:
                peer = order[i-1]
                add('requires', ecu=key, version_spec='>=2', needs=peer, needs_version_spec='=='+target[peer])
            elif target[key] == '1' and i+1 < size:
                peer = order[i+1]
                add('requires', ecu=key, version_spec='==2', needs=peer, needs_version_spec='=='+current[peer])
    if family == 'chain':
        for a, b in zip(order, order[1:]):
            add('requires', ecu=b, version_spec='>=2', needs=a, needs_version_spec='>=2')
            if variant == 'order_chain':
                add('order', before=a, after=b)
    if family == 'cycle':
        threshold = '>=1' if variant == 'benign_cycle' else '>=2'
        for a, b in ((names[0], names[1]), (names[1], names[0])):
            add('requires', ecu=a, version_spec=threshold, needs=b, needs_version_spec=threshold)
    if family == 'mutex_order':
        for offset in range(0, size, 5):
            group = order[offset:offset+5]
            if len(group) > 1:
                add('mutex', ecus=group)
        for offset in range(0, size-1, 3):
            add('order', before=order[offset], after=order[offset+1])
    if family == 'environment':
        add('precondition', ecu=names[0], ignition='off' if variant == 'allowed_environment' else 'on', minimum_battery_percent=50.0)
    capacity = (2 if seed < 30 else 4) if family == 'resource' else 4 if family == 'mutex_order' else None
    deadline = (max(milliseconds(durations[key]) for key in names)-1 if variant == 'tight_deadline'
                else sum(milliseconds(durations[key]) for key in names) if variant == 'relaxed_deadline' else None)
    data = dict(id=f'{family}-n{size}-s{seed}-{variant}', ecus=[dict(id=key, current_version=current[key],
        target_version=target[key], flash_minutes=durations[key]) for key in names],
        initial_state=dict(ecus=[dict(ecu_id=key, slot_a=dict(version=current[key], valid=True), slot_b=None,
            active_slot='A') for key in names], battery_percent=80.0, ignition='off'),
        constraints=rules, downgrade_authorizations=authorizations)
    campaign = Campaign.model_validate_json(canonical(data))
    options = PlanningOptions(max_parallel=capacity, deadline_ms=deadline, timeout_ms=timeout_ms)
    kind = ('activation_cycle' if family == 'cycle' and variant == 'primary' else
            'fixed_environment' if family == 'environment' and variant == 'primary' else
            'unauthorized_downgrade' if family == 'downgrade' and variant == 'primary' else
            'deadline_lower_bound' if variant == 'tight_deadline' else 'compatible_sequential_witness')
    certificate = {'kind': kind, 'expected': 'feasible' if kind == 'compatible_sequential_witness' else 'infeasible'}
    if kind == 'activation_cycle':
        certificate['cycle_ecus'] = names[:2]
    requires = sum(rule['type'] == 'requires' for rule in rules)
    metadata = {'origin': 'synthetic', 'family': family, 'variant': variant, 'network_size': size,
        'changed_ecus': sum(current[key] != target[key] for key in names), 'seed': seed,
        'constraint_counts': dict(Counter(rule['type'] for rule in rules)), 'constraints_total': len(rules),
        'requires_edges': requires, 'directed_density': requires / (size*(size-1)),
        'mutex_group_sizes': [len(rule['ecus']) for rule in rules if rule['type'] == 'mutex'],
        'channel_capacity': capacity, 'solver_seed': 0, 'solver_timeout_ms': timeout_ms}
    workload = Workload(campaign, options, metadata, tuple(order), certificate)
    verify_gold(workload)
    return workload


def verify_gold(workload: Workload) -> None:
    """Check constructive/analytic ground truth without consulting Z3."""
    campaign, options, certificate = workload.campaign, workload.options, workload.certificate
    if check_compatibility(campaign, campaign.initial_state):
        raise ValueError('Gold must not start in an incompatible state')
    kind = certificate['kind']
    if kind == 'compatible_sequential_witness':
        plan = sequential_plan(campaign, options, workload.witness_order)
        if validate_plan(campaign, plan):
            raise ValueError('Constructed feasible witness is invalid')
    elif kind == 'activation_cycle':
        a, b = certificate['cycle_ecus']
        if not all(check_compatibility(campaign, project(campaign.initial_state, key, '2')) for key in (a, b)):
            raise ValueError('Claimed cycle permits a first activation')
        final = project(project(campaign.initial_state, a, '2'), b, '2')
        if check_compatibility(campaign, final):
            raise ValueError('Cycle control must have compatible endpoints')
    elif kind == 'fixed_environment':
        if not any(isinstance(rule, Precondition) and (rule.ignition != campaign.initial_state.ignition
                   or rule.minimum_battery_percent > campaign.initial_state.battery_percent) for rule in campaign.constraints):
            raise ValueError('No environmental contradiction')
    elif kind == 'unauthorized_downgrade':
        if all(version_change_allowed(campaign, ecu.id, ecu.current_version, ecu.target_version) for ecu in campaign.ecus):
            raise ValueError('No unauthorized downgrade')
    elif kind == 'deadline_lower_bound':
        if options.deadline_ms is None or options.deadline_ms >= max(milliseconds(ecu.flash_minutes) for ecu in campaign.ecus):
            raise ValueError('Deadline is not below the longest write')
    else:
        raise ValueError('Unknown gold certificate')


def baseline(campaign: Campaign, options: PlanningOptions) -> dict[str, Any]:
    """Greedily select safe sequential updates; failure is not an infeasibility proof."""
    remaining = {ecu.id: ecu for ecu in campaign.ecus if parse_version(ecu.current_version) != parse_version(ecu.target_version)}
    order: list[str] = []
    state = campaign.initial_state
    if check_compatibility(campaign, state) or any(not ecu.active_image.valid for ecu in state.ecus):
        return {'status': 'NO_BASELINE_SCHEDULE', 'reason': 'Invalid initial state', 'plan': None}
    elapsed = 0
    while remaining:
        chosen = None
        for key, ecu in sorted(remaining.items()):
            if any(isinstance(rule, Order) and rule.after == key and rule.before in remaining for rule in campaign.constraints):
                continue
            if any(isinstance(rule, Precondition) and rule.ecu == key and (
                rule.ignition != state.ignition or rule.minimum_battery_percent > state.battery_percent) for rule in campaign.constraints):
                continue
            if not version_change_allowed(campaign, key, ecu.current_version, ecu.target_version):
                continue
            if options.deadline_ms is not None and elapsed + milliseconds(ecu.flash_minutes) > options.deadline_ms:
                continue
            if not check_compatibility(campaign, project(state, key, ecu.target_version)):
                chosen = key
                break
        if chosen is None:
            return {'status': 'NO_BASELINE_SCHEDULE', 'reason': 'Greedy search exhausted eligible choices; no infeasibility proof', 'plan': None}
        ecu = remaining.pop(chosen)
        elapsed += milliseconds(ecu.flash_minutes)
        state = project(state, chosen, ecu.target_version)
        order.append(chosen)
    plan = sequential_plan(campaign, options, tuple(order))
    if validate_plan(campaign, plan):
        raise RuntimeError('Baseline produced an invalid plan')
    return {'status': 'feasible', 'reason': None, 'plan': plan}
