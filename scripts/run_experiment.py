"""Run both experiments for one model.

    python scripts/run_experiment.py --model qwen2.5:3b            # needs an Ollama server
    python scripts/run_experiment.py --mock --patients 3           # dry run with the mock model (not a result)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from taint.experiment import experiment_a, experiment_b  # noqa: E402
from taint.llm import ChatModel, MockModel  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="qwen2.5:3b")
    ap.add_argument("--base-url", default="http://localhost:11434/v1")
    ap.add_argument("--patients", type=int, default=6)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    name = "mock" if a.mock else a.model.replace(":", "_").replace("/", "_")
    out = Path(a.out or Path(__file__).resolve().parents[1] / "results" / name)
    out.mkdir(parents=True, exist_ok=True)
    model = MockModel() if a.mock else ChatModel(a.model, a.base_url, cache=out / "cache.jsonl")
    experiment_a(model, a.patients, out / "runs_a.jsonl")
    experiment_b(model, a.patients, out / "runs_b.jsonl")
    print("done:", out)


if __name__ == "__main__":
    main()
