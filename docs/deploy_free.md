# Free deployment: Streamlit Community Cloud

Status: prepared and locally tested; no hosted URL has been created or verified.
The user selected guided Community Cloud deployment. Signing in and publishing
source through the user's Git workflow remain required before hosting can start.

Streamlit describes Community Cloud as free hosting for Streamlit apps:
[official overview](https://docs.streamlit.io/deploy/streamlit-community-cloud).
Follow its [deployment instructions](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).

## Files prepared

* `requirements.txt` installs this repository's package (`-e .`) and its runtime
  dependencies from `pyproject.toml`. This supports the `src/ota_verifier` layout.
* `app/public_demo.py` launches the bounded public demonstration.
* `src/ota_verifier/public_demo.py` reuses the deterministic planner, simulator,
  policy comparison, evidence views, and review gate with synthetic fixtures.

The original `app/streamlit_app.py` remains the local/shared workspace entry point.
Do not choose that full workspace entry point for this public portfolio demo.

## Publish through your own Git workflow

Review and publish these files to your repository first:

```text
Repository: sravasti12/OTA-Campaign-Verifier
Branch: main
requirements.txt
app/public_demo.py
src/ota_verifier/public_demo.py
tests/test_public_demo.py
docs/deploy_free.md
README.md
```

The project root for this Git repository is the `ota_verifier` directory, so the
entrypoint path is `app/public_demo.py`, without an `ota_verifier/` prefix.
No commit or push was performed by the assistant. Do not publish `.env`, actual
Streamlit secrets, `.venv`, `.ota_state`, or generated runtime databases.

## Deploy in your browser

1. Open [Streamlit Community Cloud](https://share.streamlit.io/) and sign in with
   your GitHub account. Grant access to the intended repository as prompted.
2. Select **Create app**, then deploy from an existing GitHub repository.
3. Enter these values:

   | Field | Value |
   | --- | --- |
   | Repository | `sravasti12/OTA-Campaign-Verifier` |
   | Branch | `main` |
   | Main file / entrypoint | `app/public_demo.py` |
   | Python version (advanced settings) | `3.14` |
   | Secrets | Leave empty for this fixture-only demo |

4. Choose an available custom subdomain if desired, or let Streamlit assign one.
   The requested name is not a deployment result until the platform confirms it.
5. Select **Deploy** and inspect the build logs. The root `requirements.txt`
   installs the package, so do not replace it with only `streamlit` or remove the
   local package installation if a module import fails.
6. Open the actual `https://…streamlit.app` URL returned by the platform. Test
   **Analyze revision**, the intermediate-version conflict, and guarded trial
   boot on **Authorized rollback comparison**. In the guarded example, baseline
   violations must remain visible and no decision should be recorded automatically.
7. Share the actual deployed URL here. The assistant can verify the live page and
   replace the README's pending-deployment notice with that exact URL. No guessed
   or localhost URL is presented as a deployed application.

## What the public demo exposes

The public page has only predefined synthetic campaigns, policy selection, and
one-to-three concurrent write channels. It uses scripted extraction/verifier/
explanation responses, then runs the actual deterministic analysis. It does not
load provider configuration or call an LLM. No API key, Ollama installation, or
model hosting subscription is needed.

The full JSON editor, filesystem path input, persistent library, OIDC operator
configuration, and document uploads are absent. Evidence can be downloaded.
Review records are self-reported simulation records within the current session;
there is no cross-session or durable approval authority. Eight analyses per
session bound accumulated demo history. A host restart or new session can lose
these records; do not use the public demo as your persistent evidence archive.

The full local application and all deterministic safety/compatibility rules are
unchanged. This is still a simulation, with no vehicle integration or
certification claim. This free demo does not validate the project's separate
shared-mode OIDC deployment gate.

## Local verification

```powershell
.\.venv\Scripts\python -m pytest -q tests/test_public_demo.py tests/test_example_loading.py tests/test_policy_selection_app.py
.\.venv\Scripts\python -m streamlit run app/public_demo.py --server.address=127.0.0.1
```

The public-entry tests prohibit provider configuration/model calls and persistent
workspace construction. They check policy-specific outcomes, stale-draft review
blocking, per-session isolation, and bounded analysis controls. Actual Linux
cloud startup and the assigned URL remain unverified until the account deployment
is completed.
