"""Runtime/version fingerprints; no network or credential access."""
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import platform
import sqlite3
from ..llm.evidence import canonical_json, content_hash
from ..llm.extractor import PROMPT_VERSION as EXTRACTION_PROMPT
from ..llm.verifier import PROMPT_VERSION as VERIFICATION_PROMPT
from ..llm.explainer import PROMPT_VERSION as EXPLANATION_PROMPT
from .models import PackageVersion, VersionManifest

CODE_FILES = ('graph.py', 'workflow_models.py', 'models.py', 'planner.py', 'simulator.py',
    'guarded_simulator.py', 'compat.py', 'invariants.py', 'policy.py', 'recovery.py', 'versions.py',
    'scheduling.py', 'ab.py', 'boot.py', 'boot_models.py', 'boot_recovery.py', 'boot_comparison.py',
    'simulation_models.py', 'evidence.py', 'llm/models.py', 'llm/client.py', 'llm/extractor.py',
    'llm/verifier.py', 'llm/explainer.py', 'llm/pipeline.py', 'llm/evidence.py',
    'llm/explanation_models.py', 'persistence/models.py', 'persistence/versions.py',
    'persistence/locks.py', 'persistence/diff.py', 'persistence/service.py', 'persistence/store.py', 'persistence/receipts.py', 'persistence/recipes.py')


def current_manifest() -> VersionManifest:
    """Fingerprint relevant implementation and dependency versions for resumption."""
    root = Path(__file__).resolve().parents[1]
    hashes = {name: content_hash((root / name).read_text(encoding='utf-8-sig')) for name in CODE_FILES}
    packages = []
    for name in ('ota-verifier', 'pydantic', 'z3-solver', 'langgraph', 'langgraph-checkpoint',
                 'langgraph-checkpoint-sqlite', 'streamlit'):
        try:
            installed = version(name)
        except PackageNotFoundError:
            installed = 'not-installed'
        packages.append(PackageVersion(name=name, version=installed))
    return VersionManifest(extraction_prompt=EXTRACTION_PROMPT, verification_prompt=VERIFICATION_PROMPT,
        explanation_prompt=EXPLANATION_PROMPT, code_sha256=content_hash(canonical_json(hashes)),
        python_version=platform.python_version(), sqlite_version=sqlite3.sqlite_version, packages=tuple(packages))
