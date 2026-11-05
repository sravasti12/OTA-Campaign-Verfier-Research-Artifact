"""Report schemas must reject incomplete coverage and unsupported success claims."""
import json
import pytest
from pydantic import ValidationError
from ota_verifier.simulation_models import RecoveryResult, RecoveryStep, SimulationOptions, SimulationResult, StressReport
from ota_verifier.simulator import simulate_plan, stress_test
from test_planner import campaign_data, feasible, load_campaign


@pytest.mark.parametrize('mutation', ['count', 'missing_case', 'duplicate', 'wrong_ecu', 'wrong_campaign', 'false_pass'])
def test_stress_report_rejects_false_coverage_or_verdict(mutation: str) -> None:
    data = campaign_data((1,))
    report = stress_test(load_campaign(data), feasible(data))
    raw = json.loads(report.model_dump_json())
    if mutation == 'count':
        raw['expected_fault_cases'] = 0
        raw['cases'] = []
    elif mutation == 'missing_case':
        raw['cases'].pop()
    elif mutation == 'duplicate':
        raw['cases'][1] = raw['cases'][0]
    elif mutation == 'wrong_ecu':
        raw['cases'][0]['fault']['ecu_id'] = 'unknown'
    elif mutation == 'wrong_campaign':
        raw['campaign_id'] = 'other'
    elif mutation == 'false_pass':
        raw['assessment'] = 'passed'
    with pytest.raises(ValidationError):
        StressReport.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize('mutation', ['missing_fault', 'false_pass', 'trace_reference', 'omitted_rollback_violation'])
def test_simulation_report_rejects_false_success(mutation: str) -> None:
    data = campaign_data((1,))
    report = stress_test(load_campaign(data), feasible(data))
    case = next(case for case in report.cases if case.recovery.status == 'unavailable')
    raw = json.loads(case.model_dump_json())
    if mutation == 'missing_fault':
        raw['fault'] = None
    elif mutation == 'false_pass':
        raw['assessment'] = 'passed'
    elif mutation == 'trace_reference':
        raw['findings'][0]['trace_index'] = len(raw['trace'])
    elif mutation == 'omitted_rollback_violation':
        raw['findings'] = []
        raw['assessment'] = 'passed'
    with pytest.raises(ValidationError):
        SimulationResult.model_validate_json(json.dumps(raw))


def test_recovery_schema_rejects_wrong_path_shape_and_noop_action() -> None:
    campaign = load_campaign(campaign_data())
    with pytest.raises(ValidationError):
        RecoveryResult(status='available', states=(campaign.initial_state, campaign.initial_state),
                       examined_states=1, reason='Inconsistent')
    with pytest.raises(ValidationError):
        RecoveryStep(ecu_id='a', from_slot='A', to_slot='A', from_version='1', to_version='1')
    with pytest.raises(ValidationError):
        SimulationOptions(max_recovery_states=0)
