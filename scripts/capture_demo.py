"""Capture actual offline Streamlit demos in a dedicated headless browser/process."""
import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import urlopen
from playwright.sync_api import Page, expect, sync_playwright
from ota_verifier.workflow_examples import example_input

ROOT = Path(__file__).resolve().parents[1]


def _idle(page: Page) -> None:
    # Let the widget message reach Streamlit, then wait for its actual run state.
    page.wait_for_timeout(350)
    expect(page.get_by_test_id('stApp')).to_have_attribute('data-test-script-state', 'notRunning', timeout=60000)


def _select(page: Page, label: str, value: str) -> None:
    page.get_by_role('combobox', name=label, exact=True).click()
    page.get_by_role('option', name=value, exact=True).click()
    _idle(page)


def _analyze(page: Page, example: str, policy: str, revision: int) -> None:
    _select(page, 'Example campaign', example)
    page.get_by_role('button', name='Load example', exact=True).click()
    _idle(page)
    key = {'Parallel update campaign': 'clear', 'Impossible intermediate versions': 'intermediate_trap',
           'Authorized rollback comparison': 'authorized_rollback'}[example]
    expected = example_input(key)[0].model_dump_json(indent=2)
    expect(page.get_by_label('Source-only request JSON', exact=True)).to_have_value(expected, timeout=20000)
    _select(page, 'Policy to review', policy)
    expect(page.get_by_label('Source-only request JSON', exact=True)).to_have_value(expected)
    page.get_by_role('button', name='Analyze revision', exact=True).click()
    _idle(page)
    metric = page.locator('[data-testid="stMetric"]').filter(has=page.get_by_text('Revision', exact=True))
    expect(metric.locator('[data-testid="stMetricValue"]')).to_have_text(str(revision), timeout=60000)
    expect(page.get_by_role('tab', name='Review', exact=True)).to_have_count(1, timeout=20000)
    expect(page.get_by_role('tab', name='Review', exact=True)).to_be_visible()
    expect(page.get_by_text('Awaiting review', exact=True)).to_be_visible()


def _capture(page: Page, output: Path, name: str, tab: str) -> None:
    page.get_by_role('tab', name=tab, exact=True).click()
    page.locator('[data-testid="stMain"]').evaluate('(element) => element.scrollTo(0, 0)')
    expect(page.locator('[data-testid="stSkeletonElement"]:visible')).to_have_count(0, timeout=30000)
    if name == 'parallel-plan.png':
        expect(page.get_by_test_id('stVegaLiteChart').locator('svg, canvas').first).to_be_visible(timeout=30000)
    page.evaluate('document.fonts.ready')
    page.wait_for_timeout(1800)  # Deliberate reading time in the screen recording.
    page.screenshot(path=str(output / name))


def capture(output: Path) -> dict[str, object]:
    """Own a synthetic local server, capture three cases, and stop only that process."""
    output.mkdir(parents=True, exist_ok=False)
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    environment = {**os.environ, 'OTA_ACCESS_MODE': 'local', 'LANGSMITH_TRACING': 'false',
                   'LANGCHAIN_TRACING_V2': 'false'}
    errors: list[str] = []
    with (output / 'server.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, '-m', 'streamlit', 'run', 'app/streamlit_app.py',
            '--server.address=127.0.0.1', f'--server.port={port}', '--server.headless=true',
            '--browser.gatherUsageStats=false'], cwd=ROOT, env=environment, stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            deadline = time.monotonic() + 40
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Dedicated demo server exited; inspect server.log')
                try:
                    with urlopen(url + '/_stcore/health', timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError('Dedicated demo server did not become healthy')
                time.sleep(0.2)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(viewport={'width': 1500, 'height': 1080},
                    record_video_dir=str(output), record_video_size={'width': 1500, 'height': 1080})
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.route('**/*', lambda route: route.continue_() if route.request.url.startswith(url + '/')
                           else route.abort())
                try:
                    page.goto(url, wait_until='domcontentloaded')
                    expect(page.get_by_role('heading', name='OTA Campaign Verifier', exact=True)).to_be_visible(timeout=40000)
                    page.get_by_text('Edit source documents and inventory', exact=True).click()
                    _analyze(page, 'Parallel update campaign', 'Baseline policy', 1)
                    _capture(page, output, 'parallel-plan.png', 'Plan')
                    _analyze(page, 'Impossible intermediate versions', 'Baseline policy', 2)
                    _capture(page, output, 'intermediate-conflict.png', 'Plan')
                    expect(page.get_by_text('No nominal schedule satisfies the modeled constraints.', exact=True)).to_be_visible()
                    _analyze(page, 'Authorized rollback comparison', 'Guarded trial boot policy', 3)
                    _capture(page, output, 'guarded-recovery.png', 'Faults')
                    expect(page.get_by_text('42 paired cases', exact=False)).to_be_visible()
                    _capture(page, output, 'human-review.png', 'Review')
                    expect(page.get_by_role('button', name='Record decision', exact=True)).to_be_visible()
                    expect(page.get_by_text('Awaiting review', exact=True)).to_be_visible()
                    if errors:
                        raise RuntimeError('Browser errors occurred; capture is not validated')
                except BaseException:
                    page.screenshot(path=str(output / 'capture-failure.png'))
                    raise
                finally:
                    context.close()
                    video = page.video.path() if page.video else None
                    browser.close()
                if video:
                    shutil.move(video, output / 'demo.webm')
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    assets = ('parallel-plan.png', 'intermediate-conflict.png', 'guarded-recovery.png', 'human-review.png', 'demo.webm')
    manifest = {'format_version': 'browser-capture-v1', 'captured_at_utc': datetime.now(UTC).isoformat(),
        'scope': 'Actual Streamlit UI / SIMULATION / scripted offline fixtures', 'browser_errors': errors,
        'human_decision_recorded': False, 'live_oidc_tested': False,
        'assets': {name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in assets}}
    with (output / 'capture-manifest.json').open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main() -> int:
    """Write screenshots/video to a fresh directory; preserve failure artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = capture(args.output.resolve())
    sys.stdout.write(json.dumps(result, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
