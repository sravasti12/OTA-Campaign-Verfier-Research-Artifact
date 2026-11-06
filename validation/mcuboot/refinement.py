"""Evidence-backed policy review without rewriting Phase 1C observations or simulator behavior."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from differential import (HERE, OUT, PIN, SCENARIOS, compare, read_reference,
                          reference_outcome, run_simulator, sha256)

REFINED = HERE / 'refinement_evidence'
LOGGER = logging.getLogger(__name__)


def verify_evidence(report_path: Path) -> dict[str, str]:
    """Verify every declared native/environment/Python artifact before reviewing it."""
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if (report['reference_commit'] != PIN or report['strategy'] != 'scratch'
            or set(report['features']) != {'sig-rsa', 'validate-primary-slot'}):
        raise ValueError('Wrong reference identity')
    root = report_path.parent.resolve()
    expected = {'reference.log': report['reference_log_sha256'],
                'environment.txt': report['environment_sha256']}
    for row in report['scenarios']:
        name = row['evidence']['simulator']
        if name in expected:
            raise ValueError('Duplicate evidence path')
        expected[name] = row['evidence']['simulator_sha256']
    for name, value in expected.items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or sha256(path) != value:
            raise ValueError(f'Evidence hash/path mismatch: {name}')
    return expected | {report_path.name: sha256(report_path)}


def intentional_policy_review(row: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    """Recognize only the exact observed policy distinction, not an entire scenario label."""
    native = row['mcuboot_actual']
    simulated = row['simulator_actual']
    observation = simulated['observation']
    result = trace['result']
    original = trace['campaign']['ecus'][0]['current_version']
    target = trace['campaign']['ecus'][0]['target_version']
    events = result['trace']
    if row['id'] == 'unauthorized_revert':
        blocker_codes = {item['code'] for item in result['guard_blockers'] + result['recovery']['blockers']}
        proven = (native['boot_ok'] and native['selected_valid'] and native['selected_version'] == original
                  and observation['selected_version'] is None and not observation['available']
                  and observation['retained_effective_version'] == target
                  and not trace['campaign']['downgrade_authorizations']
                  and result['recovery']['status'] == 'unavailable'
                  and 'unauthorized_downgrade' in blocker_codes)
        reason = 'Native automatic revert is outside the project ECU/version authorization policy.'
        evidence = {'authorization_present': bool(trace['campaign']['downgrade_authorizations']),
                    'blocker_codes': sorted(blocker_codes), 'recovery_status': result['recovery']['status']}
    elif row['id'] == 'post_confirm_campaign_recovery':
        reboots = [event for event in events if event['stage'] == 'reboot']
        rebooted_target = any(event['snapshot']['state']['ecus'][0][
            'slot_' + event['snapshot']['state']['ecus'][0]['active_slot'].lower()]['version'] == target
            for event in reboots)
        authorized = any(item['ecu_id'] == 'ecu' and item['version'] == original
                         for item in trace['campaign']['downgrade_authorizations'])
        proven = (native['boot_ok'] and native['selected_valid'] and native['selected_version'] == target and native['confirmed']
                  and observation['selected_version'] == original and observation['available']
                  and observation['selected_valid'] and observation['confirmed']
                  and authorized and rebooted_target and result['recovery']['status'] == 'available')
        reason = 'Immediate confirmed-image reboot agrees; subsequent campaign recovery restores the authorized original.'
        evidence = {'rebooted_target_before_campaign_recovery': rebooted_target,
                    'original_restore_authorized': authorized, 'recovery_status': result['recovery']['status']}
    else:
        raise ValueError('No reviewed policy exception for this scenario')
    return {'disposition': 'INTENTIONAL_POLICY_DIFFERENCE' if proven else 'UNEXPECTED_CONTRADICTION',
            'policy_evidence_verified': bool(proven), 'reason': reason,
            'evidence': evidence, 'requires_investigation': not proven}


def layer_review(row: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    """Report mechanism scope separately from endpoint agreement and campaign policy."""
    case = next(case for case in SCENARIOS if case.id == row['id'])
    observed = compare(case, row['mcuboot_actual'], row['simulator_actual']['observation'])
    differences = [item['name'] for item in observed['properties'] if item['status'] == 'MISMATCH']
    result: dict[str, Any] = {
        'endpoint_properties': observed['properties'],
        'mechanism_equivalence': 'NOT_ESTABLISHED',
        'campaign_policy': 'NOT_EXERCISED' if not case.fault else 'PROJECT_POLICY_RETAINED',
        'requires_investigation': bool(observed.get('unexpected_contradiction')),
        'disposition': 'BOUNDED_ENDPOINT_AGREEMENT' if observed['status'] == 'MATCH'
                       else 'UNSUPPORTED_COMPARISON' if observed['status'] == 'UNSUPPORTED'
                       else 'UNEXPECTED_CONTRADICTION',
    }
    if case.id in ('unauthorized_revert', 'post_confirm_campaign_recovery'):
        result.update(intentional_policy_review(row, trace))
        # A new difference in a different property is not covered by the reviewed exception.
        allowed = {'selected_version', 'selected_valid'} if case.id == 'unauthorized_revert' else {'selected_version'}
        if set(differences) - allowed:
            result.update(disposition='UNEXPECTED_CONTRADICTION', requires_investigation=True)
        result['campaign_policy'] = 'DISTINCT_FROM_BOOTLOADER_MECHANISM'
    if case.id == 'post_confirm_campaign_recovery':
        result['aligned_checkpoint'] = {
            'native': 'reset_1', 'project': 'reboot before recover_begin',
            'target_reboot_observed': result['evidence']['rebooted_target_before_campaign_recovery'],
            'note': 'This checkpoint does not replace the original final-state MISMATCH.'}
    if case.category.startswith('unsupported'):
        result['unsupported_reason'] = case.limit
        result['mechanism_equivalence'] = 'UNSUPPORTED'
    if case.id == 'failed_trial':
        native_trial = next(item for item in row['mcuboot_observations'] if item['checkpoint'] == 'first_boot')
        target = trace['campaign']['ecus'][0]['target_version']
        exposed = any(event['snapshot']['state']['ecus'][0][
            'slot_' + event['snapshot']['state']['ecus'][0]['active_slot'].lower()]['version'] == target
            for event in trace['result']['trace'])
        result['exposure_difference'] = {'native_trial_selected': native_trial['slots'][0]['version'],
                                         'project_ever_effective_candidate': exposed,
                                         'application_crash_executed': False}
    return result


def build_refinement(output: Path = REFINED, baseline_path: Path | None = None) -> dict[str, Any]:
    """Verify preserved C evidence, rerun Python scenarios, and issue a separate review report."""
    baseline_path = baseline_path or OUT / 'comparison.json'
    source = baseline_path.parent
    before = verify_evidence(baseline_path)
    baseline = json.loads(baseline_path.read_text(encoding='utf-8'))
    native_records = read_reference(source / 'reference.log')
    if {row['id'] for row in baseline['scenarios']} != {case.id for case in SCENARIOS}:
        raise ValueError('Unexpected baseline scenarios')
    output.mkdir(exist_ok=True, parents=True)
    rows = []
    for old in baseline['scenarios']:
        if reference_outcome(native_records[old['id']]) != old['mcuboot_actual']:
            raise ValueError('Normalized reference outcome differs from actual C transcript')
        trace_path = source / old['evidence']['simulator']
        original_trace = json.loads(trace_path.read_text(encoding='utf-8'))
        fresh_path = output / f"{old['id']}-simulator.json"
        case = next(case for case in SCENARIOS if case.id == old['id'])
        fresh = run_simulator(case, fresh_path)
        fresh_trace = json.loads(fresh_path.read_text(encoding='utf-8'))
        if original_trace['campaign'] != fresh_trace['campaign']:
            raise ValueError('Comparison campaign inputs changed since Phase 1C')
        if fresh['observation'] != old['simulator_actual']['observation']:
            raise ValueError(f"Python observation changed since Phase 1C: {case.id}")
        review = layer_review(old, fresh_trace)
        rows.append({'id': old['id'], 'original_status': old['comparison']['status'],
                     'original_comparison': old['comparison'], 'review': review,
                     'original_evidence': old['evidence'],
                     'fresh_simulator': {'path': fresh_path.name, 'sha256': sha256(fresh_path)},
                     'original_input_unchanged': original_trace['campaign'] == fresh_trace['campaign']})
    if verify_evidence(baseline_path) != before:
        raise ValueError('Phase 1C evidence changed during refinement')
    return {'schema_version': 1, 'phase': '1D', 'reference_commit': PIN,
            'phase_1c_directory': Path(os.path.relpath(source, output)).as_posix(),
            'native_execution': 'Retained actual Phase 1C execution; no new native scenarios claimed',
            'phase_1c_evidence_sha256': before, 'original_summary': baseline['summary'],
            'production_behavior_changed': False,
            'unexpected_contradictions': sum(row['review']['requires_investigation'] for row in rows),
            'scenarios': rows}


def main() -> int:
    """Write a separate refinement report without replacing original mismatch evidence."""
    report = build_refinement()
    (REFINED / 'review.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    LOGGER.info('Reviewed %s scenarios; unexpected contradictions: %s', len(report['scenarios']),
                report['unexpected_contradictions'])
    return 1 if report['unexpected_contradictions'] else 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
