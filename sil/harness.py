"""Software-in-the-loop campaign runner. Standard library only.

Written from the plain-English design in specs/SMALL_CAMPAIGN.md. It deliberately
imports nothing from ota_verifier or the TLA+ model, so its behaviour is measured,
not inherited.

ECUs are separate OS processes with file-backed flash. Power loss kills them. The
Coordinator holds its campaign state in a durable file and is rebuilt from that file
after power loss. Properties are judged by observe(), which reads bytes on disk and
ignores what the coordinator believes.
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

AGENT = Path(__file__).resolve().parent / 'ecu_agent.py'
sys.path.insert(0, str(AGENT.parent))
from ecu_agent import durable_write, payload  # noqa: E402

GOOD_HASH = {version: hashlib.sha256(payload(version)).hexdigest() for version in (1, 2)}
ENDED = ('committed', 'aborted')


@dataclass(frozen=True)
class Setup:
    """A campaign, a design and a schedule."""
    ecus: tuple[str, ...]  # Dependencies come first in this order.
    edges: tuple[tuple[str, str], ...]  # (dependent, dependency)
    design: str  # none, LocalRollback, EarlyErase, SkipVerify
    policy: str  # batch, rolling or late_confirm


class Vehicle:
    """The ECU processes and their flash folders."""

    def __init__(self, root: Path, setup: Setup) -> None:
        self.root = root
        self.setup = setup
        self.processes: dict[str, subprocess.Popen[str]] = {}
        for ecu in setup.ecus:
            folder = root / ecu
            folder.mkdir()
            (folder / 'slotA.img').write_bytes(payload(1))
            durable_write(folder / 'slotA.meta', json.dumps({'version': 1}).encode())
            durable_write(folder / 'boot.json', json.dumps({'active': 'A'}).encode())
        self.start()

    def start(self) -> None:
        for ecu in self.setup.ecus:
            process = subprocess.Popen([sys.executable, '-I', '-S', str(AGENT), str(self.root / ecu)],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
            self.processes[ecu] = process
        for process in self.processes.values():
            assert json.loads(process.stdout.readline())['ready']

    def send(self, ecu: str, **command: object) -> dict:
        process = self.processes[ecu]
        process.stdin.write(json.dumps(command) + '\n')
        process.stdin.flush()
        return json.loads(process.stdout.readline())

    def cut_power(self) -> None:
        """Kill every ECU process at once, then restart them from what is on disk."""
        self.stop()
        self.start()

    def stop(self) -> None:
        for process in self.processes.values():
            process.kill()
        for process in self.processes.values():
            process.wait()
            process.stdin.close()
            process.stdout.close()
        self.processes = {}


class Coordinator:
    """Follows the campaign design. Its state survives power loss through a durable file."""

    def __init__(self, path: Path, setup: Setup) -> None:
        self.path = path
        self.setup = setup
        if path.is_file():
            self.state = json.loads(path.read_text(encoding='utf-8'))
        else:
            self.state = {'campaign': 'run', 'culprit': [], 'stage': {ecu: 'idle' for ecu in setup.ecus},
                          'version': {ecu: 1 for ecu in setup.ecus}}
            self.save()

    def save(self) -> None:
        durable_write(self.path, json.dumps(self.state).encode())

    def stage(self, ecu: str) -> str:
        return self.state['stage'][ecu]

    def set_stage(self, ecu: str, stage: str) -> None:
        self.state['stage'][ecu] = stage

    def fail(self, ecu: str) -> None:
        self.state['campaign'] = 'rollback'
        self.state['culprit'] = sorted({*self.state['culprit'], ecu})

    def dependencies_on_v2(self, ecu: str) -> bool:
        return all(self.state['version'][dependency] == 2
                   for dependent, dependency in self.setup.edges if dependent == ecu)

    def dependents_on_v1(self, ecu: str) -> bool:
        return all(self.state['version'][dependent] == 1
                   for dependent, dependency in self.setup.edges if dependency == ecu)

    def rollback_candidates(self, vehicle: Vehicle) -> list[str]:
        """ECUs that may revert now, later ECUs first."""
        local = self.setup.design == 'LocalRollback'
        scope = self.state['culprit'] if local else self.setup.ecus
        return [ecu for ecu in reversed(self.setup.ecus)
                if ecu in scope and self.state['version'][ecu] == 2
                and (local or self.dependents_on_v1(ecu)) and vehicle.send(ecu, cmd='can_rollback')['ok']]

    def rollback_finished(self) -> bool:
        scope = self.state['culprit'] if self.setup.design == 'LocalRollback' else self.setup.ecus
        return all(self.state['version'][ecu] == 1 for ecu in scope)

    def run_step_order(self) -> list[tuple[str, str]]:
        """The (action, ecu) priority of each schedule while the campaign runs."""
        ecus = self.setup.ecus
        if self.setup.policy == 'batch':
            return ([('Verify', ecu) for ecu in ecus] + [('Download', ecu) for ecu in ecus]
                    + [('Confirm', ecu) for ecu in ecus] + [('Activate', ecu) for ecu in ecus])
        if self.setup.policy == 'late_confirm':
            return ([('Verify', ecu) for ecu in ecus] + [('Download', ecu) for ecu in ecus]
                    + [('Activate', ecu) for ecu in ecus] + [('Confirm', ecu) for ecu in ecus])
        return [(action, ecu) for ecu in ecus for action in ('Confirm', 'Activate', 'Verify', 'Download')]

    def possible(self, action: str, ecu: str) -> bool:
        stage = self.stage(ecu)
        return {'Download': stage == 'idle', 'Verify': stage == 'downloaded', 'Confirm': stage == 'trial',
                'Activate': stage == 'verified' and self.dependencies_on_v2(ecu)}[action]

    def next_step(self, vehicle: Vehicle) -> tuple[str, str] | None:
        """Choose the next nominal step, or None if the campaign cannot proceed."""
        campaign = self.state['campaign']
        if campaign == 'run':
            for action, ecu in self.run_step_order():
                if self.possible(action, ecu):
                    return action, ecu
            if all(self.stage(ecu) == 'healthy' for ecu in self.setup.ecus):
                return 'Commit', ''
            return None
        if campaign == 'rollback':
            candidates = self.rollback_candidates(vehicle)
            if candidates:
                return 'Rollback', candidates[0]
            if self.rollback_finished():
                return 'FinishRollback', ''
        return None

    def execute(self, step: tuple[str, str], vehicle: Vehicle, corrupt_next: str = '') -> str:
        """Perform one step and return its logged name."""
        action, ecu = step
        design = self.setup.design
        name = action
        if action == 'Download':
            vehicle.send(ecu, cmd='download', version=2, corrupt=ecu == corrupt_next)
            self.set_stage(ecu, 'downloaded')
        elif action == 'Verify':
            if vehicle.send(ecu, cmd='verify', version=2, skip=design == 'SkipVerify')['ok']:
                self.set_stage(ecu, 'verified')
            else:
                self.set_stage(ecu, 'failed')
                self.fail(ecu)
                name = 'VerifyReject'
        elif action == 'Activate':
            vehicle.send(ecu, cmd='activate', erase_old=design == 'EarlyErase')
            self.state['version'][ecu] = 2
            self.set_stage(ecu, 'trial')
        elif action == 'Confirm':
            self.set_stage(ecu, 'healthy')
        elif action == 'Commit':
            self.state['campaign'] = 'committed'
        elif action == 'Rollback':
            vehicle.send(ecu, cmd='rollback')
            self.state['version'][ecu] = 1
            self.set_stage(ecu, 'reverted')
        elif action == 'FinishRollback':
            self.state['campaign'] = 'aborted'
        self.save()
        return name


def observe(root: Path, setup: Setup, campaign: str) -> tuple[set[str], dict[str, int]]:
    """Judge S1-S4 from the bytes on disk alone."""
    running: dict[str, int] = {}
    corrupt: set[str] = set()
    spare: dict[str, int] = {}
    for ecu in setup.ecus:
        folder = root / ecu
        active = json.loads((folder / 'boot.json').read_text(encoding='utf-8'))['active']
        other = 'B' if active == 'A' else 'A'
        running[ecu] = json.loads((folder / f'slot{active}.meta').read_text(encoding='utf-8'))['version']
        digest = hashlib.sha256((folder / f'slot{active}.img').read_bytes()).hexdigest()
        if digest != GOOD_HASH[running[ecu]]:
            corrupt.add(ecu)
        meta = folder / f'slot{other}.meta'
        spare[ecu] = json.loads(meta.read_text(encoding='utf-8'))['version'] if meta.is_file() else 0
    violated = set()
    if any(running[a] == 2 and running[b] != 2 for a, b in setup.edges):
        violated.add('S1')
    if campaign != 'committed' and any(running[ecu] == 2 and spare[ecu] != 1 for ecu in setup.ecus):
        violated.add('S2')
    if campaign in ENDED and len(set(running.values())) != 1:
        violated.add('S3')
    if corrupt:
        violated.add('S4')
    return violated, running


@dataclass
class Run:
    """What one execution did and what was observed."""
    actions: list[list[str]] = field(default_factory=list)
    violated: set[str] = field(default_factory=set)
    campaign: str = ''
    running: dict[str, int] = field(default_factory=dict)


def applicable(fault: dict, coordinator: Coordinator, step: tuple[str, str] | None) -> bool:
    """Whether a scheduled fault can happen now; otherwise it is skipped."""
    campaign = coordinator.state['campaign']
    kind, ecu = fault['kind'], fault['ecu']
    if kind in ('PowerLoss', 'PowerCutMidDownload'):
        return campaign in ('run', 'rollback') and (kind == 'PowerLoss' or (step is not None and step[0] == 'Download'))
    if campaign != 'run':
        return False
    return coordinator.stage(ecu) == ('trial' if kind == 'TrialFail' else 'idle')


def power_loss(coordinator: Coordinator, vehicle: Vehicle, path: Path, setup: Setup) -> Coordinator:
    """Cut power, then rebuild the coordinator from its durable file alone."""
    vehicle.cut_power()
    restarted = Coordinator(path, setup)
    for ecu in setup.ecus:
        if restarted.stage(ecu) == 'downloaded':
            restarted.set_stage(ecu, 'idle')
    restarted.state['campaign'] = 'rollback'
    restarted.save()
    return restarted


def inject(fault: dict, coordinator: Coordinator, vehicle: Vehicle, path: Path, setup: Setup,
           step: tuple[str, str] | None) -> tuple[Coordinator, list[str]]:
    """Apply a fault and return the coordinator, which power loss replaces, and the log entry."""
    kind, ecu = fault['kind'], fault['ecu']
    if kind == 'PowerLoss':
        return power_loss(coordinator, vehicle, path, setup), ['PowerLoss', '']
    if kind == 'PowerCutMidDownload':
        process = vehicle.processes[step[1]]
        process.stdin.write(json.dumps({'cmd': 'download', 'version': 2, 'pause_half': True}) + '\n')
        process.stdin.flush()
        assert json.loads(process.stdout.readline())['half']
        return power_loss(coordinator, vehicle, path, setup), ['PowerLoss', '']
    if kind == 'DownloadCorrupt':
        coordinator.execute(('Download', ecu), vehicle, ecu)
        return coordinator, ['DownloadCorrupt', ecu]
    coordinator.set_stage(ecu, 'failed')
    coordinator.fail(ecu)
    coordinator.save()
    return coordinator, [kind, ecu]


def execute(setup: Setup, faults: list[dict], max_ticks: int = 2000) -> Run:
    """Run one campaign with a fault script, observing the disk after every step."""
    root = Path(tempfile.mkdtemp(prefix='sil-'))
    path = root / 'campaign.json'
    vehicle = Vehicle(root, setup)
    coordinator = Coordinator(path, setup)
    run = Run()
    try:
        for tick in range(max_ticks):
            step = coordinator.next_step(vehicle)
            due = [fault for fault in faults if fault['tick'] == tick and applicable(fault, coordinator, step)]
            if due:
                coordinator, entry = inject(due[0], coordinator, vehicle, path, setup, step)
            elif step is None:
                break
            else:
                entry = [coordinator.execute(step, vehicle), step[1]]
            run.actions.append(entry)
            violated, run.running = observe(root, setup, coordinator.state['campaign'])
            run.violated |= violated
        run.campaign = coordinator.state['campaign']
        if run.campaign not in ENDED:
            run.violated.add('L1')
    finally:
        vehicle.stop()
        shutil.rmtree(root, ignore_errors=True)
    return run
