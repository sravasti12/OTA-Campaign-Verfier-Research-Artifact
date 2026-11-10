# Checking the Functional Safety of Multi-ECU OTA Update Campaigns: Research Artifact

This repository is the research artifact for the paper:

> **Checking the Functional Safety of Multi-ECU Over-the-Air Update Campaigns: A TLA+ Model, a Pair Abstraction and Software-in-the-Loop Validation**
> Sravasti Bose, independent researcher, Kolkata, India.
> Draft, not yet submitted. PDF: [paper/OTA_Campaign_Safety_DRAFT_IEEE.pdf](paper/OTA_Campaign_Safety_DRAFT_IEEE.pdf)

It holds the formal model, the experiment scripts, every raw result with its run manifest, the software-in-the-loop (SIL) simulator, and the script that generates every number and table in the paper.

## The question

When one OTA campaign updates several ECUs whose versions depend on each other, a partial failure can leave the vehicle running an incompatible mix, even when each ECU recovers correctly on its own.

- Can this campaign-level safety be checked formally?
- Do the model's predictions match an executable implementation?

## What is checked

A coordinator-driven A/B (dual-bank) campaign, modelled in TLA+ and checked with TLC:

| Property | Meaning |
| --- | --- |
| S1 | No ECU runs the new version while a dependency runs the old one, in any reachable state |
| S2 | Until commit, every ECU on the new version keeps the old image |
| S3 | When the campaign ends, all ECUs run the old version or all run the new one |
| S4 | Only images that passed verification run |
| L1 | Under fairness and a bounded number of faults, the campaign finishes |

Three flawed designs, each changing one decision, show that the checker finds real counterexamples:

- `LocalRollback`: only the failed ECU rolls back
- `EarlyErase`: the old image is erased on activation
- `SkipVerify`: verification always passes

## Results at a glance

Every number below is generated from the raw files in `results/raw/` by `paper/make_paper_data.py`.

| Experiment | Result |
| --- | --- |
| Three-ECU campaign, 63 TLC checks | All verdicts matched predictions recorded beforehand. `LocalRollback` breaks compatibility after one fault and passes every property with none |
| Direct checking, 5 to 50 ECUs | All generated graphs finished up to 8 ECUs, 2 of 3 at 9, none at 10 or above, on one laptop |
| Pair abstraction | Two models of 197 and 148 states cover S1 to S4 for any number of ECUs. This rests on a hand-written proof sketch, supported by 36 of 36 refinement checks and 144 agreement checks with 0 unsound results |
| SIL validation | 6,360 fault-injected runs against predictions frozen beforehand: 0 misses and 0 false alarms |

**Limits:**
- The SIL and the model share an author and a schedule, so their agreement is evidence of consistency, not independent validation.
- No hardware results exist. The Raspberry Pi testbed in [docs/RASPBERRY_PI_TESTBED.md](docs/RASPBERRY_PI_TESTBED.md) is a plan only.
- The full list of threats to validity is in the paper's Section VIII.

## Repository map

| Path | Contents |
| --- | --- |
| `specs/tla/OTACampaign.tla` | The campaign model, the properties and the three flaws |
| `specs/tla/OTAPair.tla` | The two-ECU pair abstraction |
| `specs/tla/OTAScripted.tla` | The model pinned to a schedule and fault script, for SIL predictions |
| `specs/SMALL_CAMPAIGN.md` | Plain-English definitions, written before the model |
| `experiments/` | `e0_small_campaign.py`, `e3_scaling.py`, `e5_predict.py`, `e5_sil.py`, and plotting scripts |
| `sil/` | The SIL simulator: one OS process per ECU, file-backed flash, process kill as power loss |
| `results/raw/<experiment>/<run-id>/` | Raw outputs of each run, with `manifest.json` |
| `results/predictions/e5/` | SIL predictions, committed before the SIL ran |
| `paper/` | LaTeX source, generated tables (`generated/`), citation checks, and the PDF |
| `docs/` | Write-ups: [model results](docs/SMALL_CAMPAIGN_RESULTS.md), [scaling](docs/SCALING_RESULTS.md), [soundness proof](docs/PAIR_ABSTRACTION_SOUNDNESS.md), [results audit](docs/RESULTS_AUDIT.md), [testbed plan](docs/RASPBERRY_PI_TESTBED.md) |
| `related_work.md` | Every cited source, what was read, and how this work differs |
| `run_all.py` | The entry point for every experiment |

## Reproduce

Requirements:
- Python 3.11 or later, and Java. CI uses Java 17; the recorded runs used Java 18.
- `matplotlib`, for the plot only.

```bash
pip install -e ".[dev]" matplotlib
python tools/fetch_tools.py                       # TLA+ tools v1.7.4, checked against a pinned SHA-256
python run_all.py --experiment e0_small_campaign  # minutes
python run_all.py --experiment e3_scaling         # about 3 hours on a laptop
python run_all.py --experiment e5_predict         # about 8 minutes
python run_all.py --experiment e5_sil             # about 1 hour
python experiments/plot_scaling.py
python paper/make_paper_data.py                   # regenerates every number and table in the paper
```

Each run writes a new folder in `results/raw/`. Existing runs are never overwritten.

**Rebuild the PDF** with any LaTeX installation, or with [Tectonic](https://tectonic-typesetting.github.io/), which was used here:

```bash
tectonic -X compile paper/main.tex --outdir paper/build
```

**Re-check the citations** against Crossref and arXiv:

```bash
python paper/verify_citations.py
```

## Checking the evidence

Each run folder has a `manifest.json` recording:
- the commit and any uncommitted files
- the random seed and the environment
- the SHA-256 of every output

The runs cited in the paper:

| Experiment | Run | Commit |
| --- | --- | --- |
| E0, three-ECU model checking | `results/raw/e0_small_campaign/20261106T140103Z-fc95dee/` | `fc95dee` |
| E3, scaling and abstraction | `results/raw/e3_scaling/20261106T141615Z-ce3eefb/` | `ce3eefb` |
| E5, predictions | `results/raw/e5_predict/20261107T095332Z-19423e3/` | `19423e3` |
| E5, SIL | `results/raw/e5_sil/20261108T074756Z-e593539/` | `e593539` |

**Predictions came before the SIL.** Tag `e5-predictions-frozen` points to commit `e593539`, which added the predictions. The SIL run's manifest names that same commit and records the predictions' SHA-256 (`08fb8744...`).

**Nothing was discarded.** Incomplete SIL runs are kept, each with a `NOTE.md` explaining why it stopped. Open problems found in review are listed in [docs/RESULTS_AUDIT.md](docs/RESULTS_AUDIT.md).

## Other code in this repository

This repository grew out of a broader OTA planning project, and its history is kept intact so that every commit cited above can be checked. Its other parts are **not** evidence for the paper:
- the Z3 planner
- the LLM extraction pipeline
- the MCUboot comparison
- the Streamlit app

They are described in [PROJECT_README.md](PROJECT_README.md).
