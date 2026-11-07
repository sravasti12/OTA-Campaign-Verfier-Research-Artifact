# Phase 2C — live LLM evaluation readiness

Checked on 6 November 2026. Workstream Phase 2C corresponds to project Phase 13C. **Blocked before inference: no live provider is configured in this workspace.**

## Actual checks

| Check | Observed result |
| --- | --- |
| Project `.env` | Absent |
| Existing `ClientSettings.from_env`, extraction | Configuration rejected: `Set LLM_MODEL to an installed or provider-supported model` |
| Existing `ClientSettings.from_env`, verification | Same configuration rejection |
| `ollama` executable on PATH | Not found; this does not prove it is absent elsewhere on the machine |
| `http://localhost:11434/api/tags`, three-second request timeout | Unavailable |
| Live extraction/verification calls | **0** |

No API keys were displayed. No model was installed, downloaded or silently selected. No extraction scores were computed, and scripted fixtures were not substituted for live inference. Production code and existing benchmark/MCUboot evidence were unchanged. No pytest suite was run for this documentation-only readiness update; the provider checks above are not pytest results.

## Configuration needed

Use the existing [provider template](../.env.example). From the project directory in PowerShell, create the local configuration only if it does not already exist:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

For local Ollama, install/start Ollama separately and choose a model actually available on this machine. `ollama list` lists installed models; `ollama serve` starts the service if needed. Set these values in `.env`:

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=<actual-installed-model-name>
OLLAMA_BASE_URL=http://localhost:11434
```

Alternatively, configure `LLM_PROVIDER=gemini` or `groq`, an actually supported `LLM_MODEL`, and the matching `GEMINI_API_KEY` or `GROQ_API_KEY`. Keep credentials local, outside chat and version control. A configured API key does not establish free quota; confirm available free-tier access before evaluation. No paid inference is authorized by this readiness check.

## Gates before evaluation

Provider availability is only the first gate. The [approved evaluation plan](PHASE2_EVALUATION_PLAN.md) also requires a manually reviewed, frozen corpus with expressible requirements, exact evidence spans, ambiguity labels and separate real-document/synthetic partitions. That new reviewed corpus has not been admitted by this check. Existing scripted evaluations do not satisfy this gate.

Once a provider is available, finish dataset admission, freeze prompts/models and the bounded request manifest, execute the real extraction/faithfulness pipeline, preserve sanitized raw outputs and errors, and calculate metrics against reviewed gold. Do not restart the long scalability matrix as part of this stage. Stop after Phase 2C; the consolidated Phase 2D report remains separate.
