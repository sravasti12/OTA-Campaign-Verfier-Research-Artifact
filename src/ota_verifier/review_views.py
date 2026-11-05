"""Pure presentation mappings for the review screen; no model or solver calls."""
from typing import Any
from .models import VehicleState
from .workflow_models import ReviewBundle, WorkflowInput

ANALYSIS_LABELS = {
    'extraction_blocked': 'Extraction blocked', 'planning_infeasible': 'Planning infeasible',
    'planning_unknown': 'Planning inconclusive', 'simulation_passed': 'Simulation passed',
    'simulation_violations': 'Simulation violations', 'simulation_inconclusive': 'Simulation inconclusive',
}
REVIEW_LABELS = {'awaiting_review': 'Awaiting review', 'approved': 'Proposal approved',
                 'rejected': 'Proposal rejected', 'reviewed_with_findings': 'Reviewed with findings',
                 'invalidated': 'Previous decision invalidated'}


def vehicle_rows(state: VehicleState) -> list[dict[str, Any]]:
    """Present both slot contents without hiding invalid inactive images."""
    return [{'ECU': ecu.ecu_id, 'Active slot': ecu.active_slot,
             'Active version': ecu.active_image.version, 'Active image valid': ecu.active_image.valid,
             'A version': ecu.slot_a.version if ecu.slot_a else 'empty',
             'A valid': ecu.slot_a.valid if ecu.slot_a else False,
             'B version': ecu.slot_b.version if ecu.slot_b else 'empty',
             'B valid': ecu.slot_b.valid if ecu.slot_b else False} for ecu in state.ecus]


def inputs_current(bundle: ReviewBundle, incoming: WorkflowInput | None) -> bool:
    """Unanalyzed edits must not be treated as covered by an existing review."""
    return incoming is not None and incoming == bundle.snapshot.artifacts.input


def decision_labels(bundle: ReviewBundle) -> tuple[str, ...]:
    """Expose approval only when the server-side policy permits it."""
    from .workflow_models import approval_eligible
    ordinary = ('Review with findings', 'Reject proposal')
    return ('Approve simulation proposal', *ordinary) if approval_eligible(bundle.snapshot) else ordinary
