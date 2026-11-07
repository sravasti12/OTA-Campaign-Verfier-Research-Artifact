# Third-party publication decisions

7 November 2026. This file records source provenance and a proposed distribution
selection; it does not change upstream rights or historical evidence.

| Material | Provenance / basis | Proposed publication |
| --- | --- | --- |
| MCUboot documentation excerpts and snapshots | Official mcu-tools/mcuboot v2.4.0 commit `6d3b3d2c38ab20c242e5b9abb04d050086383eb2`; Apache-2.0; original LICENSE/NOTICE already retained in review-materials-v1 and copied source packages | Include with original notices, links and version identification; no endorsement or equivalence claim |
| ExpressLRS documentation text | Official ExpressLRS/Docs commit `805830b6d0bcd352ee7167ab16ab57d1c26fb421`; root LICENSE and docs/info/licenses.md explicitly cover the documentation website under GPL-3.0 | Include unchanged textual source with GPL license, provenance and attribution; do not imply sponsorship or license this project's independent code by inference |
| Flysky NB4+ complete PDF, two copies | Manufacturer URL and byte hashes recorded in the immutable packages; document filename revision 20231219 | Exclude full manual from proposed Git index: no redistribution grant was established |
| Two rendered Flysky pages | Assistant-generated rasterizations of the manufacturer manual, PDF pages7/67, used for visual verification | Exclude images from proposed Git index pending appropriate distribution permission/basis; keep the original local images and hashes |
| Brief attributed quotations inside labels/reports | Exact limited source passages used for evaluation/commentary; surrounding output and metadata are project-generated | Retain attribution and upstream-license notices where applicable. A short quotation is not a license for the complete manual. Distribution decisions for the manufacturer excerpts remain an owner review item |
| TLA+ tools / downloaded MCUboot checkout | Existing pinned retrieval configuration; tools/bin and .mcuboot-reference are ignored | Do not bundle installation trees/binaries. Use existing documented retrieval/setup commands |
| Project source_snapshot / reproduction_source directories | Copies of this project's own evaluation/harness code, not entire upstream repositories | Retain as evidence, distinct from third-party source licensing |

## ExpressLRS attribution

Documentation developed and maintained by ExpressLRS LLC and its contributors.
Pinned [source](https://github.com/ExpressLRS/Docs/blob/805830b6d0bcd352ee7167ab16ab57d1c26fb421/docs/quick-start/receivers/firmware-version.md).
The [pinned licensing statement](https://github.com/ExpressLRS/Docs/blob/805830b6d0bcd352ee7167ab16ab57d1c26fb421/docs/info/licenses.md)
explicitly includes the website. Its exact downloaded licensing statement and
GPL text are preserved in [the licensing statement](third_party/EXPRESSLRS_DOCS_LICENSING.md)
and [GPL-3.0](third_party/EXPRESSLRS_DOCS_GPL-3.0.txt).
Copied source text remains subject to those terms. No logos/theme code were
added by this publication repair. Trademarks do not imply affiliation.

## Retrieve the manufacturer reference locally

The original PDF is available from the
[manufacturer entry URL](https://www.flysky-cn.com/s/Noble-NB4-User-manual-20231219-EN.pdf).
Consult `eval/live_extraction/real-review-v3/sources/flysky-source.json` for the
recorded redirect, size and provenance. Download only when authorized to access
that source; do not substitute a mirror or a newer manual silently.

1. Save the exact manual to a local temporary path, verify SHA-256
   `c18b753b23361f2c71f8b642bcfc9eddf0b51c248f247b4cc7e9989641b63556`, then
   copy the verified bytes to the two ignored reference paths:
   `eval/live_extraction/real-review-v2/sources/flysky-nb4-manual.pdf` and
   `eval/live_extraction/real-review-v3/sources/flysky-nb4-manual.pdf`.
2. Existing Windows-only `eval/live_extraction/render_flysky.ps1` can render
   pages7/67 into a new output directory. It requires the built-in Windows PDF
   API, not an LLM or a model download.
3. Compare outputs with the exact image hashes in the original
   `real-review-v3/SHA256SUMS.json`. Renderer/platform changes may produce
   different raster bytes. A new render is not automatically the original
   historical image. Do not replace the historical manifest to make it pass.
4. Exact historical visual evidence, when needed, must be restored from the
   owner's unchanged private archive under an appropriate access/distribution
   basis. Do not publish that archive by accident.

The four excluded files remain on this machine; no evidence was deleted or
rewritten. Their manifests still describe the complete historical package.
A public checkout deliberately lacks those four external references. Normal tests
still execute all schema, citation, gate, planner and first-party integrity checks;
only verification of the absent external bytes is unavailable, explicitly reported
with warnings and machine-readable statuses. No pytest test is skipped. If any
external file is present with incorrect bytes, verification fails.

## Offline commands

From the repository root in PowerShell, using the existing environment:

```powershell
# Public tests: no downloads or LLM services, optional assets need not be present.
.\.venv\Scripts\python.exe -m pytest -q
# Read-only published evidence audit; lists unavailable external assets separately.
.\.venv\Scripts\python.exe eval/live_extraction/verify_reference_assets.py
# Strict optional audit after obtaining the original reference assets independently.
.\.venv\Scripts\python.exe eval/live_extraction/verify_reference_assets.py --require-external
# Read-only schema/evidence/gate and Z3 corpus controls (no packet rewriting).
.\.venv\Scripts\python.exe eval/live_extraction/validate_real_v3.py
```

The public audit exits 0 when all published evidence matches, while listing
`UNAVAILABLE_EXTERNAL_REFERENCE` conditions separately from verified entries.
Strict `--require-external` exits 2 for unavailable references; any wrong present
bytes or missing required first-party evidence exits 1 in either mode. Neither
command downloads anything. A complete historical reference package is verified
only when all four original external assets are available with exact hashes.
The PDF is revision 20231219; its two copies have the hash above. Original page7
SHA-256: `7ffebbd526145a9773950b2fe0b5b236ce2571ecbd97de4b89b748d9ba3f4a84`;
page67: `f71ccf2ce4b3f7fe007f65a70c686ff24f4d565c87abcad1424faea96bebe2b9`.

## Dependency boundary

`tests/test_real_review_v2.py` checks source identity when available while always
running schema, offsets and gate checks. `tests/test_real_review_v3.py` invokes
`validate_real_v3.py`, which separately reports unavailable PDF/page provenance
while retaining all five cases and actual Z3 controls. The original v3 page check
only required nonempty images; it now verifies their manifest hashes when present.
`prepare_real_v2.py` / `prepare_real_v3.py` are historical packet-construction
scripts requiring the reference material for original provenance/copy checks;
they are not public test prerequisites and must not be used to regenerate frozen
packets. `render_flysky.ps1` requires a user-supplied PDF and Windows rendering
APIs, and is optional. Historical manifests and archived source snapshots retain
their original strict dependencies; the new read-only public verifier reports
which entries are unavailable rather than altering those manifests.

The original untracked cohort and proposed decisions are listed in
[PUBLICATION_FILE_INVENTORY.csv](PUBLICATION_FILE_INVENTORY.csv). Existing
source headers and upstream notices remain authoritative. This review does not
grant rights absent from the upstream material or select a new license for the
project's own code.
