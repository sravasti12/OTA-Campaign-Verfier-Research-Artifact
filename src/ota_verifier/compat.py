"""Single source of truth for active-version dependency compatibility."""
from collections.abc import Callable
from typing import TypeVar
from .models import Campaign, Requires, VehicleState, Violation
from .versions import matches

Truth = TypeVar('Truth')


def requirement_holds(
    constraint: Requires,
    version_matches: Callable[[str, str], Truth],
    implies: Callable[[Truth, Truth], Truth],
) -> Truth:
    """Express one dependency using concrete or symbolic truth operations.

    Version matching is delegated, but trigger/dependency meaning is defined
    here for both the concrete checker and the solver encoding.
    """
    return implies(version_matches(constraint.ecu, constraint.version_spec),
                   version_matches(constraint.needs, constraint.needs_version_spec))


def check_compatibility(campaign: Campaign, state: VehicleState) -> tuple[Violation, ...]:
    """Return every violated requires constraint in a complete runtime state.

    Bootability, preconditions, ordering, and downgrade policy are independent
    concerns. An empty result asserts only active-version compatibility.
    """
    installed = {ecu.ecu_id: ecu.active_image.version for ecu in state.ecus}
    if set(installed) != {ecu.id for ecu in campaign.ecus}:
        raise ValueError('State must cover exactly the campaign ECUs')
    findings: list[Violation] = []
    for constraint in campaign.constraints:
        if not isinstance(constraint, Requires):
            continue
        holds = requirement_holds(
            constraint, lambda ecu, spec: matches(installed[ecu], spec),
            lambda trigger, dependency: not trigger or dependency,
        )
        if not holds:
            findings.append(Violation(
                code='incompatible_versions', ecu_ids=(constraint.ecu, constraint.needs),
                message=f'{constraint.ecu}@{installed[constraint.ecu]} requires '
                        f'{constraint.needs}@{constraint.needs_version_spec}; '
                        f'observed {installed[constraint.needs]}',
                constraint_id=constraint.id, source_document_id=constraint.source_document_id,
                source_text=constraint.source_text, actual_version=installed[constraint.needs],
                expected_version_spec=constraint.needs_version_spec,
            ))
    return tuple(findings)
