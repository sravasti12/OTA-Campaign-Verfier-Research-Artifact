"""Offline release evidence: three portfolio demos and a restart/restore rehearsal."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from .benchmark.runner import run_benchmark
from .boot_models import GuardedOptions
from .compat import check_compatibility
from .graph import WorkflowService
from .llm.evidence import canonical_json, content_hash
from .models import ECUState, FeasibleResult, Image, PlanningOptions, VehicleState
from .persistence.operations import backup_workspace, migrate_workspace, restore_workspace, verify_database
from .persistence.service import PersistentWorkflowService
from .workflow_examples import example_input, fixture_dependencies
from .workflow_models import PolicySelection, ReviewBundle, WorkflowInput, approval_eligible


def _input(example: str, guarded: bool = False) -> WorkflowInput:
    request, _ = example_input(example)
    return WorkflowInput(request=request, planning_options=PlanningOptions(max_parallel=2),
        selected_policy=PolicySelection(id='guarded-trial-v1', guarded_options=GuardedOptions())
                        if guarded else PolicySelection(id='baseline-v1'))


def demo_summary(name: str, bundle: ReviewBundle) -> dict[str, Any]:
    """Check each story against actual evidence, never convert findings into approval."""
    artifacts = bundle.snapshot.artifacts
    result = artifacts.planning
    summary: dict[str, Any] = {'id': name, 'analysis': artifacts.status,
        'review_state': bundle.review_state, 'snapshot_hash': bundle.snapshot_hash,
        'approval_eligible': approval_eligible(bundle.snapshot)}
    passed = bundle.current_decision is None and bundle.review_state == 'awaiting_review'
    if name == 'parallel' and isinstance(result, FeasibleResult):
        steps = result.plan.steps
        overlaps = any(a.start_ms < b.end_ms and b.start_ms < a.end_ms
            for index, a in enumerate(steps) for b in steps[index + 1:])
        compatible = all(not check_compatibility(artifacts.extraction.campaign, state) for state in result.plan.states)
        summary.update(makespan_ms=result.plan.makespan_ms, total_write_ms=sum(step.end_ms - step.start_ms for step in steps),
            overlapping_writes=overlaps, every_activation_compatible=compatible)
        passed &= overlaps and compatible and result.plan.optimal
    elif name == 'intermediate_conflict' and result is not None and result.status == 'infeasible':
        campaign = artifacts.extraction.campaign
        assert campaign is not None
        final = VehicleState(ecus=tuple(ECUState(ecu_id=ecu.id, slot_a=Image(version=ecu.target_version), slot_b=None,
            active_slot='A') for ecu in campaign.ecus), battery_percent=campaign.initial_state.battery_percent,
            ignition=campaign.initial_state.ignition)
        final_compatible = not check_compatibility(campaign, final)
        summary.update(final_versions_compatible=final_compatible, subset_minimal=result.conflict.subset_minimal,
            conflict_ids=[item.id for item in result.conflict.items])
        passed &= final_compatible and result.conflict.subset_minimal and bool(result.conflict.items)
    elif name == 'guarded_recovery' and artifacts.comparison is not None:
        comparison = artifacts.comparison
        summary.update(baseline=comparison.baseline.assessment, guarded=comparison.guarded.assessment,
            shared_cases=len(comparison.shared_cases), guarded_cases=len(comparison.guarded.cases),
            confirmation_cases=len(comparison.guarded_only_indices), improvements=comparison.improved_cases,
            regressions=comparison.regressed_cases)
        passed &= (comparison.baseline.assessment == 'violations' and comparison.guarded.assessment == 'passed'
            and len(comparison.guarded.cases) == comparison.guarded.expected_fault_cases > 0
            and bool(comparison.guarded_only_indices) and approval_eligible(bundle.snapshot))
    else:
        passed = False
    summary['checks_passed'] = bool(passed)
    return summary


def _write(path: Path, value: Any) -> None:
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def recovery_rehearsal(directory: Path) -> dict[str, Any]:
    """Rehearse migration, interrupted resume, WAL backup, and fresh-process-state reading.

    Service instances are closed and recreated. Abrupt termination and genuine
    separate-process crash recovery remain exercised by the persistence tests.
    No human decision is manufactured by this release rehearsal.
    """
    directory.mkdir()
    source = directory / 'workspace.sqlite'
    with PersistentWorkflowService(source):
        pass
    migrate_workspace(source, directory / 'pre-migration.sqlite')
    incoming = _input('authorized_rollback', guarded=True)
    _, case = example_input('authorized_rollback')
    with PersistentWorkflowService(source) as service:
        service.begin(incoming, fixture_dependencies(case), run_id='release-rehearsal', pause_after='extract')
        with service.store.connect() as connection:
            before = {row['purpose']: row['call_json'] for row in connection.execute('SELECT * FROM ota_receipts')}
    with PersistentWorkflowService(source) as service:
        bundle = service.resume('release-rehearsal')
        with service.store.connect() as connection:
            after = {row['purpose']: row['call_json'] for row in connection.execute('SELECT * FROM ota_receipts')}
        receipts_reused = len(before) == 2 and all(after.get(role) == raw for role, raw in before.items()) and len(after) == 3
        exported = service.export(bundle.run_id)
        backup_workspace(source, directory / 'backup.sqlite')  # Source connection is deliberately still open.
    restored_path = directory / 'restored.sqlite'
    verified = restore_workspace(directory / 'backup.sqlite', restored_path)
    with PersistentWorkflowService(restored_path) as restored:
        identical = restored.export(bundle.run_id) == exported
        waiting = restored.get(bundle.run_id).review_state == 'awaiting_review'
    _write(directory / 'review.json', exported.model_dump(mode='json'))
    return {'receipts_reused': receipts_reused, 'restored_export_identical': identical,
        'human_review_still_required': waiting, 'storage_schema': verified['storage_schema'],
        'checks_passed': receipts_reused and identical and waiting and verified['storage_schema'] == 2,
        'verification': verify_database(restored_path)}


def build_release_pack(output: Path) -> dict[str, Any]:
    """Create fresh, fixture-labeled evidence; external release gates stay pending."""
    output.mkdir(parents=True, exist_ok=False)
    benchmark = run_benchmark(split='all')
    _write(output / 'benchmark.json', benchmark.model_dump(mode='json'))
    demos = []
    for name, example, guarded in (('parallel', 'clear', False),
            ('intermediate_conflict', 'intermediate_trap', False), ('guarded_recovery', 'authorized_rollback', True)):
        _, case = example_input(example)
        bundle = WorkflowService().start(_input(example, guarded), fixture_dependencies(case), run_id=f'demo-{name}')
        _write(output / f'{name}.json', bundle.model_dump(mode='json'))
        demos.append(demo_summary(name, bundle))
    rehearsal = recovery_rehearsal(output / 'recovery')
    report = {'format_version': 'release-validation-v1', 'scope': 'SIMULATION / offline scripted fixtures',
        'created_at_utc': datetime.now(UTC).isoformat(), 'runtime': benchmark.runtime.model_dump(mode='json'),
        'release_tool_sha256': content_hash(Path(__file__).read_text(encoding='utf-8-sig')),
        'benchmark_semantic_digest': benchmark.semantic_digest,
        'benchmark_checks_passed': benchmark.checks_passed, 'demos': demos, 'recovery_rehearsal': rehearsal,
        'local_checks_passed': benchmark.checks_passed and all(demo['checks_passed'] for demo in demos) and rehearsal['checks_passed'],
        'release_ready': False, 'pending_external_checks': ['remote_windows_linux_ci_matrix', 'live_oidc_login_roles_logout'],
        'test_suite': 'Run pytest separately; this report does not claim that the complete suite ran.',
        'limitations': ['Fixture accuracy is not live-model accuracy.', 'No live OIDC callback or network deployment was exercised.',
            'No automatic human approval, vehicle execution, or certification evidence is produced.']}
    _write(output / 'release-validation.json', report)
    index = {str(path.relative_to(output)).replace('\\', '/'): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.rglob('*')) if path.is_file()}
    _write(output / 'artifact-index.json', {'algorithm': 'sha256', 'files': index})
    return report


def main(argv: list[str] | None = None) -> int:
    """Run local release checks into a new directory and report external gates honestly."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_release_pack(args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Cannot create release evidence ({type(error).__name__}); use a new writable directory.\n')
    sys.stdout.write(json.dumps(report, indent=2) + '\n')
    return 0 if report['local_checks_passed'] else 4


if __name__ == '__main__':
    raise SystemExit(main())
