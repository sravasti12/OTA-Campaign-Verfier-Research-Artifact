# Campaigns

`research_v1.json` is the campaign set for experiments. It is derived from the frozen `ota-benchmark-v1` corpus, which stays
unchanged as a regression artifact.

In v1, `core-parallel` and `core-rollback-trap` are the same campaign under two names, so v1's case counts overstate coverage.
Here each campaign appears once, with the removed name in `also_known_as` and its tags merged in. Do not quote v1 totals in the
paper as independent cases.

Regenerate with:

```bash
PYTHONPATH=src python -m ota_verifier.formal.research_corpus
```

A test fails if this file drifts from a fresh derivation.
