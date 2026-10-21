"""Run a synthetic request: python -m ai_engine contracts/ai-engine/sample-input.json"""
import argparse
from pathlib import Path
import sys

from pydantic import ValidationError
from .pipeline import run_pipeline
from .schemas import PipelineInput


def main():
    parser = argparse.ArgumentParser(description="Run a local ProofPay evidence analysis")
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    try:
        request = PipelineInput.model_validate_json(args.input.read_text())
    except (OSError, ValidationError):
        print("Could not read or validate the input request.", file=sys.stderr)
        return 2
    print(run_pipeline(request).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
