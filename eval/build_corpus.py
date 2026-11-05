"""Explicitly rebuild a candidate corpus artifact without overwriting reviewed data."""
import argparse
from pathlib import Path
from ota_verifier.benchmark.corpus import build_corpus, corpus_hash


def main() -> int:
    """Write an unreviewed candidate; updating a benchmark version is a separate review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    corpus = build_corpus()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(corpus.model_dump_json(indent=2) + '\n')
    parser.exit(message=f'Candidate canonical SHA256: {corpus_hash(corpus)}\n')


if __name__ == '__main__':
    raise SystemExit(main())
