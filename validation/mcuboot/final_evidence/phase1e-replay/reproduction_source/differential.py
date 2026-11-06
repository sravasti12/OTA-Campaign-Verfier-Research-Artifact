"""Independent observation comparison; never implements MCUboot boot decisions."""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import subprocess
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from ota_verifier.boot import boot_metadata, guarded_boot, power_loss
from ota_verifier.boot_models import GuardedFaultSpec, GuardedSnapshot
from ota_verifier.guarded_simulator import simulate_guarded
from ota_verifier.models import Campaign, FeasibleResult
from ota_verifier.planner import plan_campaign
from ota_verifier.versions import parse_version

PIN = '6d3b3d2c38ab20c242e5b9abb04d050086383eb2'
HERE = Path(__file__).resolve().parent
OUT = HERE / 'differential_evidence'
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Scenario:
    """Declared stimuli and comparison limits, independent of measured outcomes."""
    id: str
    expected: str
    fault: tuple[str, str, str] | None = None
    sample: str = 'final'
    authorization: bool = True
    category: str = 'comparable_endpoint'
    limit: str = ''


SCENARIOS = (
    Scenario('test_upgrade', 'Candidate selected, not yet confirmed.', sample='boot'),
    Scenario('confirmed_reboot', 'Confirmed candidate remains selected after reset.', sample='reset'),
    Scenario('unconfirmed_revert', 'Original selected after unconfirmed reset.', ('power_loss', 'confirm', 'before')),
    Scenario('unauthorized_revert', 'MCUboot reverts; project may block an unauthorized downgrade.',
             ('power_loss', 'confirm', 'before'), authorization=False, category='intentional_policy_difference'),
    Scenario('invalid_signature', 'MCUboot rejects bad signature; project represents verification rejection only.',
             ('verification_failure', 'verify', 'before'), category='unsupported_mechanism',
             limit='Project has no signature parser, key or cryptographic verifier.'),
    Scenario('payload_corruption', 'Corrupted candidate rejected; original retained.', ('write_corruption', 'write', 'after')),
    Scenario('swap_power_loss', 'Reference resumes interrupted swap; project has no swap journal.',
             ('power_loss', 'activate', 'before'), category='unsupported_boundary',
             limit='Reference cuts before flash operation 7; logical activate-before is only a coarse counterpart.'),
    Scenario('interrupted_revert', 'Reference resumes interrupted revert to original.',
             ('power_loss', 'confirm', 'before'), category='unsupported_boundary',
             limit='Project has no fault injection inside recovery actions or scratch journal.'),
    Scenario('failed_trial', 'Original selected after external reset without confirmation.',
             ('boot_failure', 'boot', 'before'), category='unsupported_mechanism',
             limit='Reference models missing confirmation/reset, not runtime health failure. Project gates health before exposure.'),
    Scenario('repeated_resets', 'Original remains selected through three unconfirmed-path resets.',
             ('power_loss', 'confirm', 'before'), sample='repeated'),
    Scenario('known_good_recovery', 'Good original remains available when candidate payload is invalid.',
             ('write_corruption', 'write', 'after')),
    Scenario('post_confirm_campaign_recovery', 'MCUboot retains candidate; project recovery aims for campaign original.',
             ('power_loss', 'confirm', 'after'), category='intentional_orchestration_difference'),
)


def read_reference(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Require an actual completed native test transcript and complete scenarios."""
    text = path.read_text(encoding='utf-8')
    if 'test result: ok. 1 passed; 0 failed' not in text:
        raise ValueError('Reference test failed or did not execute exactly one scenario-driver test')
    grouped: dict[str, list[dict[str, Any]]] = {}
    for line in text.splitlines():
        if 'DIFF_JSON ' not in line:
            continue
        record = json.loads(line.split('DIFF_JSON ', 1)[1])
        records = grouped.setdefault(record['scenario'], [])
        if any(old['checkpoint'] == record['checkpoint'] for old in records):
            raise ValueError('Duplicate reference checkpoint')
        if len(record['slots']) != 2:
            raise ValueError('Reference observation requires both image slots')
        records.append(record)
    if set(grouped) != {case.id for case in SCENARIOS}:
        raise ValueError('Missing or unexpected reference scenarios')
    for case in SCENARIOS:
        records = grouped[case.id]
        if records[0]['checkpoint'] != 'initial' or not any(item['checkpoint'] == 'first_boot' for item in records):
            raise ValueError('Missing initial state or real boot observation')
        terminal = ('reset_3' if case.id == 'repeated_resets' else 'first_boot'
                    if case.id in ('test_upgrade', 'invalid_signature', 'payload_corruption',
                                   'known_good_recovery', 'swap_power_loss') else 'reset_1')
        if records[-1]['checkpoint'] != terminal:
            raise ValueError('Missing terminal reset/boot observation')
        if case.id in ('swap_power_loss', 'interrupted_revert'):
            if not any(item['checkpoint'] == 'cut' and item['interrupted'] for item in records):
                raise ValueError('Requested reference power cut was not observed')
    return grouped


def make_campaign(authorized: bool) -> Campaign:
    """Create a one-ECU project input with explicitly scoped rollback permission."""
    data: dict[str, Any] = {
        'id': 'mcuboot-differential',
        'ecus': [{'id': 'ecu', 'current_version': '0.0.1.0', 'target_version': '1.0.1.1', 'flash_minutes': 1.0}],
        'initial_state': {'ecus': [{'ecu_id': 'ecu', 'slot_a': {'version': '0.0.1.0', 'valid': True},
                                   'slot_b': None, 'active_slot': 'A'}], 'battery_percent': 80.0, 'ignition': 'off'},
        'constraints': [],
        'downgrade_authorizations': ([{'ecu_id': 'ecu', 'version': '0.0.1.0',
            'authorized_by': 'validation-fixture', 'reason': 'Explicit permission for reference rollback comparison'}]
            if authorized else []),
    }
    return Campaign.model_validate_json(json.dumps(data))


def observe_simulator(snapshot: GuardedSnapshot) -> dict[str, Any]:
    """Read effective image and boot metadata without deciding recovery behavior."""
    ecu = snapshot.state.ecus[0]
    metadata = boot_metadata(snapshot, 'ecu')
    return {'selected_version': ecu.active_image.version if metadata.available else None,
            'retained_effective_version': ecu.active_image.version,
            'selected_valid': ecu.active_image.valid if metadata.available else None,
            'confirmed': metadata.confirmed_slot == ecu.active_slot if metadata.available else None,
            'available': metadata.available, 'active_slot': ecu.active_slot,
            'metadata': metadata.model_dump(mode='json')}


def run_simulator(case: Scenario, output: Path) -> dict[str, Any]:
    """Execute the existing planner/simulator and, where specified, public reboot primitives."""
    campaign = make_campaign(case.authorization)
    planned = plan_campaign(campaign)
    if not isinstance(planned, FeasibleResult):
        raise RuntimeError(f'Fixture could not be planned: {planned}')
    fault = (GuardedFaultSpec(ecu_id='ecu', kind=case.fault[0], stage=case.fault[1], when=case.fault[2])
             if case.fault else None)
    result = simulate_guarded(campaign, planned.plan, fault)
    snapshot = (next(event.snapshot for event in result.trace if event.stage == 'boot')
                if case.sample == 'boot' else result.trace[-1].snapshot)
    checkpoints = [{'checkpoint': 'selected_campaign_trace', 'observation': observe_simulator(snapshot)}]
    if case.sample in ('reset', 'repeated'):
        for index in range(1 if case.sample == 'reset' else 2):
            offline = power_loss(snapshot)
            slot = boot_metadata(offline, 'ecu').confirmed_slot
            candidate, blockers = guarded_boot(campaign, offline, 'ecu', slot, confirm=True)
            checkpoints.append({'checkpoint': f'primitive_reset_{index+1}',
                                'blockers': [item.model_dump(mode='json') for item in blockers],
                                'observation': observe_simulator(candidate or offline)})
            snapshot = candidate or offline
    payload = {'campaign': campaign.model_dump(mode='json'), 'plan': planned.plan.model_dump(mode='json'),
               'fault': fault.model_dump(mode='json') if fault else None,
               'result': result.model_dump(mode='json'), 'checkpoints': checkpoints}
    output.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    return {'initial': campaign.initial_state.model_dump(mode='json'),
            'input': {'fault': payload['fault'], 'authorization': case.authorization, 'sample': case.sample,
                      'reset_driver': 'public power_loss/guarded_boot primitives' if case.sample in ('reset', 'repeated') else None},
            'observation': observe_simulator(snapshot), 'assessment': result.assessment,
            'recovery': result.recovery.model_dump(mode='json') if result.recovery else None,
            'checkpoints': checkpoints}


def reference_outcome(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Normalize observed C output; never substitute an expected firmware version."""
    last = records[-1]
    selected = last['boot_ok'] and not last['interrupted']
    return {'selected_version': last['slots'][0]['version'] if selected else None,
            'selected_valid': (last['original_present_primary'] or last['candidate_present_primary']) if selected else None,
            'confirmed': last['slots'][0]['image_ok_raw'] == 1 if selected else None,
            'boot_ok': last['boot_ok'], 'checkpoint': last['checkpoint']}


def compare(case: Scenario, native: dict[str, Any], simulated: dict[str, Any]) -> dict[str, Any]:
    """Compare measured properties, preserving unsupported scope and contradictions."""
    if not native['boot_ok']:
        return {'status': 'INCONCLUSIVE', 'category': 'reference_boot_did_not_succeed', 'properties': []}
    names = ['selected_version', 'selected_valid']
    if case.id in ('test_upgrade', 'confirmed_reboot', 'post_confirm_campaign_recovery'):
        names.append('confirmed')
    properties: list[dict[str, Any]] = []
    for name in names:
        left, right = native[name], simulated[name]
        same = (parse_version(left) == parse_version(right)
                if name == 'selected_version' and left is not None and right is not None else left == right)
        properties.append({'name': name, 'mcuboot': left, 'simulator': right, 'status': 'MATCH' if same else 'MISMATCH'})
    differences = any(item['status'] == 'MISMATCH' for item in properties)
    unsupported = case.category.startswith('unsupported')
    return {'status': 'UNSUPPORTED' if unsupported else 'MISMATCH' if differences else 'MATCH',
            'category': case.category if unsupported or differences else 'bounded_endpoint_agreement',
            'unexpected_contradiction': differences and case.category == 'comparable_endpoint',
            'properties': properties, 'limit': case.limit}


def sha256(path: Path) -> str:
    """Hash evidence bytes for traceability."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_report(simulator_output: Path = OUT, reference_directory: Path = OUT) -> dict[str, Any]:
    """Read authentic native observations and execute every Python comparison input."""
    records = read_reference(reference_directory / 'reference.log')
    environment = (reference_directory / 'environment.txt').read_text(encoding='utf-8')
    if PIN not in environment or sha256(HERE / 'Cargo.lock') not in environment:
        raise ValueError('Reference environment does not attest the pinned commit and dependency lock')
    rows = []
    for case in SCENARIOS:
        trace = simulator_output / f'{case.id}-simulator.json'
        simulated = run_simulator(case, trace)
        native = reference_outcome(records[case.id])
        expected_native = ('1.0.1.1' if case.id in ('test_upgrade', 'confirmed_reboot', 'swap_power_loss',
                                                 'post_confirm_campaign_recovery') else '0.0.1.0')
        comparison = compare(case, native, simulated['observation'])
        comparison['expected_reference_version'] = expected_native
        comparison['reference_expectation_met'] = (native['selected_version'] is not None
            and parse_version(native['selected_version']) == parse_version(expected_native))
        if native['boot_ok'] and not comparison['reference_expectation_met']:
            comparison.update(status='MISMATCH', category='unexpected_reference_outcome', unexpected_contradiction=True)
        rows.append({'id': case.id, 'scenario': asdict(case), 'expected': case.expected,
                     'mcuboot_initial': records[case.id][0],
                     'mcuboot_input': {'geometry': 'k64f, align=8, erased=ff',
                         'stimuli': [item['checkpoint'] for item in records[case.id]],
                         'cut_operation': 7 if case.id in ('swap_power_loss', 'interrupted_revert') else None},
                     'mcuboot_observations': records[case.id], 'mcuboot_actual': native,
                     'simulator_actual': simulated, 'comparison': comparison,
                     'evidence': {'reference': 'reference.log', 'simulator': trace.name,
                                  'simulator_sha256': sha256(trace)}})
    return {'schema_version': 1, 'generated_utc': datetime.now(timezone.utc).isoformat(),
            'reference_commit': PIN, 'features': ['sig-rsa', 'validate-primary-slot'],
            'strategy': 'scratch', 'simulator_policy': 'guarded-trial-v1',
            'scope': 'C bootutil with simulated flash versus existing guarded simulator; no hardware execution',
            'reference_log_sha256': sha256(reference_directory / 'reference.log'),
            'environment_sha256': sha256(reference_directory / 'environment.txt'),
            'summary': dict(Counter(row['comparison']['status'] for row in rows)), 'scenarios': rows}


def main() -> int:
    """Execute native code by default, then write a reproducible comparison report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--distribution', default='Ubuntu-24.04')
    parser.add_argument('--reuse-reference', action='store_true', help='Analyze saved real logs; no fresh native execution')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    # Remove stale report before a new attempt; a failed run must not look successful.
    report_path = OUT / 'comparison.json'
    report_path.unlink(missing_ok=True)
    if not args.reuse_reference:
        script = (HERE / 'run-differential.sh').as_posix()
        linux = subprocess.run(['wsl', '-d', args.distribution, '--', 'wslpath', '-a', script],
                               check=True, capture_output=True, text=True).stdout.strip()
        subprocess.run(['wsl', '-d', args.distribution, '--', 'bash', linux], check=True)
    report = build_report()
    report['reference_reused'] = args.reuse_reference
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    LOGGER.info('Differential results: %s', report['summary'])
    if any(row['comparison']['status'] == 'INCONCLUSIVE' for row in report['scenarios']):
        return 2
    return 1 if any(row['comparison'].get('unexpected_contradiction') for row in report['scenarios']) else 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
