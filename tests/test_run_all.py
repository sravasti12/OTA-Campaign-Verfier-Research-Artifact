"""Runner and tool-pin behaviour that protects the honesty of recorded results."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
import pytest

ROOT = Path(__file__).resolve().parent.parent


def load(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


run_all = load(ROOT / 'run_all.py')
fetch_tools = load(ROOT / 'tools' / 'fetch_tools.py')


@pytest.mark.parametrize(('line', 'expected'), [
    ('4 states generated, 4 distinct states found, 0 states left on queue.', (4, 4)),
    ('1,234 states generated, 1,000 distinct states found, 0 states left on queue.', (1234, 1000)),
    ('no summary here', None),
])
def test_parse_tlc_summary(line: str, expected: tuple[int, int] | None) -> None:
    assert run_all.parse_tlc(line) == expected


def manifest_status(tmp_path: Path, *statuses: str) -> str:
    stages = [run_all.Stage(f's{index}', status) for index, status in enumerate(statuses)]
    return run_all.write_manifest(tmp_path, 'smoke', stages)


def test_skipped_stage_never_reports_passed(tmp_path: Path) -> None:
    assert manifest_status(tmp_path, 'passed', 'skipped') == 'incomplete'


def test_failure_outranks_skip(tmp_path: Path) -> None:
    assert manifest_status(tmp_path, 'skipped', 'failed') == 'failed'


def test_manifest_hashes_artifacts_and_records_commit(tmp_path: Path) -> None:
    (tmp_path / 'out.log').write_text('x', encoding='utf-8')
    (tmp_path / 'tlc-holds-states').mkdir()
    (tmp_path / 'tlc-holds-states' / 'scratch').write_text('x', encoding='utf-8')
    assert manifest_status(tmp_path, 'passed') == 'passed'
    manifest = json.loads((tmp_path / 'manifest.json').read_text(encoding='utf-8'))
    assert set(manifest['artifacts_sha256']) == {'out.log'}
    assert manifest['environment']['seed'] == 42
    assert manifest['environment']['commit']


def test_missing_tlc_is_a_failure_only_when_required(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_all, 'java_version', lambda: None)
    assert run_all.stage_tlc(tmp_path, require=False)[0].status == 'skipped'
    assert run_all.stage_tlc(tmp_path, require=True)[0].status == 'failed'


def test_existing_run_folder_is_never_reused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run_all, 'ROOT', tmp_path)
    monkeypatch.setattr(run_all, 'git', lambda *args: 'abc')
    class Frozen:
        @staticmethod
        def now(zone: object) -> 'Frozen':
            return Frozen()
        def strftime(self, pattern: str) -> str:
            return 'same'
    monkeypatch.setattr(run_all, 'datetime', Frozen)
    run_all.new_run_dir('smoke')
    with pytest.raises(FileExistsError):
        run_all.new_run_dir('smoke')


def test_verify_detects_wrong_and_missing_files(tmp_path: Path) -> None:
    good = tmp_path / 'tool.jar'
    good.write_bytes(b'tool')
    pin = {'sha256': fetch_tools.sha256(good)}
    assert fetch_tools.verify(good, pin) is None
    good.write_bytes(b'tampered')
    assert 'expected' in fetch_tools.verify(good, pin)
    assert 'missing' in fetch_tools.verify(tmp_path / 'absent.jar', pin)


def test_fetch_refuses_a_download_with_the_wrong_checksum(tmp_path: Path) -> None:
    source = tmp_path / 'source.jar'
    source.write_bytes(b'unexpected')
    pin = {'path': 'bin/tool.jar', 'url': source.as_uri(), 'sha256': '0' * 64}
    with pytest.raises(RuntimeError, match='Refusing'):
        fetch_tools.fetch('tool', pin, tmp_path)
    assert not (tmp_path / 'bin' / 'tool.jar').exists()
    assert not (tmp_path / 'bin' / 'tool.jar.part').exists()


def test_tool_pin_is_complete() -> None:
    pin = fetch_tools.load_pins()['tla2tools']
    assert len(pin['sha256']) == 64
    assert pin['url'].endswith(f'/{pin["version"]}/tla2tools.jar')


def test_run_output_does_not_make_a_clean_checkout_dirty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def git(*args: str) -> None:
        subprocess.run(('git', '-c', 'user.name=t', '-c', 'user.email=t@example.invalid', *args),
                       cwd=tmp_path, check=True, capture_output=True)
    git('init')
    (tmp_path / 'tracked.txt').write_text('x', encoding='utf-8')
    git('add', '.')
    git('commit', '-m', 'init')
    monkeypatch.setattr(run_all, 'ROOT', tmp_path)
    (tmp_path / 'results' / 'raw' / 'e0').mkdir(parents=True)
    (tmp_path / 'results' / 'raw' / 'e0' / 'out.log').write_text('x', encoding='utf-8')
    assert run_all.environment()['dirty_files'] == []
    (tmp_path / 'tracked.txt').write_text('changed', encoding='utf-8')
    assert run_all.environment()['dirty_files'] != []
