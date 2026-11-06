"""Campaigns, schedules and fault scripts shared by the E5 prediction and SIL stages.

Scripts are derived from the written schedule, not from running either side.
"""
from ota_verifier.formal.campaign_gen import ecu_names, edges_of, generate

DESIGNS = ('none', 'LocalRollback', 'EarlyErase', 'SkipVerify')
# batch: download all, then activate and confirm each ECU in turn.
# rolling: finish each ECU before starting the next.
# late_confirm: download all, activate all, then confirm all, so trial periods overlap.
POLICIES = ('batch', 'rolling', 'late_confirm')
DOUBLE_FAULT_MAX_ECUS = 5
SECOND_FAULT_DELAYS = (1, 3)


def campaigns() -> dict[str, dict]:
    """The E0 campaign and generated campaigns from E3. ECUs are listed dependencies first."""
    chosen = {'small': {'ecus': ['gateway', 'brake', 'infotainment'], 'edges': [['brake', 'gateway']]}}
    for size, seed in ((5, 1), (5, 2), (5, 3), (10, 1)):
        chosen[f'n{size}_s{seed}'] = {'ecus': list(ecu_names(size)), 'edges': [list(edge) for edge in edges_of(generate(size, seed))]}
    return chosen


def nominal_steps(ecus: list[str], policy: str) -> list[tuple[str, str]]:
    """The fault-free schedule."""
    if policy == 'batch':
        steps = [(action, ecu) for ecu in ecus for action in ('Download', 'Verify')]
        steps += [(action, ecu) for ecu in ecus for action in ('Activate', 'Confirm')]
    elif policy == 'late_confirm':
        steps = [(action, ecu) for ecu in ecus for action in ('Download', 'Verify')]
        steps += [('Activate', ecu) for ecu in ecus] + [('Confirm', ecu) for ecu in ecus]
    else:
        steps = [(action, ecu) for ecu in ecus for action in ('Download', 'Verify', 'Activate', 'Confirm')]
    return [*steps, ('Commit', '')]


def priority(ecus: list[str], policy: str) -> list[tuple[str, str]]:
    """The model's priority list: the first enabled step runs."""
    if policy == 'batch':
        run = [(action, ecu) for ecu in ecus for action in ('Verify', 'VerifyReject')]
        run += [('Download', ecu) for ecu in ecus] + [('Confirm', ecu) for ecu in ecus] + [('Activate', ecu) for ecu in ecus]
    elif policy == 'late_confirm':
        run = [(action, ecu) for ecu in ecus for action in ('Verify', 'VerifyReject')]
        run += [('Download', ecu) for ecu in ecus] + [('Activate', ecu) for ecu in ecus] + [('Confirm', ecu) for ecu in ecus]
    else:
        run = [(action, ecu) for ecu in ecus for action in ('Confirm', 'Activate', 'Verify', 'VerifyReject', 'Download')]
    return [*run, ('Commit', ''), *(('Rollback', ecu) for ecu in reversed(ecus)), ('FinishRollback', '')]


def fault_scripts(ecus: list[str], policy: str) -> list[list[dict]]:
    """No fault, every applicable single fault at every step, and a later power loss on top."""
    single = []
    for tick, (action, ecu) in enumerate(nominal_steps(ecus, policy)):
        single.append({'tick': tick, 'kind': 'PowerLoss', 'ecu': ''})
        if action == 'Download':
            single += [{'tick': tick, 'kind': kind, 'ecu': ecu}
                       for kind in ('DownloadFail', 'DownloadCorrupt', 'PowerCutMidDownload')]
        if action == 'Confirm':
            single.append({'tick': tick, 'kind': 'TrialFail', 'ecu': ecu})
    scripts: list[list[dict]] = [[], *([fault] for fault in single)]
    if len(ecus) <= DOUBLE_FAULT_MAX_ECUS:
        scripts += [[fault, {'tick': fault['tick'] + delay, 'kind': 'PowerLoss', 'ecu': ''}]
                    for fault in single for delay in SECOND_FAULT_DELAYS]
    return scripts


def model_faults(script: list[dict]) -> list[dict]:
    """The model has one kind of power loss; a cut during a write is PowerLoss at that step."""
    return [{**fault, 'kind': 'PowerLoss', 'ecu': ''} if fault['kind'] == 'PowerCutMidDownload' else fault for fault in script]
