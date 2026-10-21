"""Regenerate engine JSON schemas, independently of the unchanged HTTP OpenAPI."""
import json
from pathlib import Path
from .schemas import PipelineInput, PipelineResult


def export_contracts():
    root = Path(__file__).resolve().parents[1] / "contracts" / "ai-engine"
    root.mkdir(parents=True, exist_ok=True)
    for filename, model in (("input.schema.json", PipelineInput), ("result.schema.json", PipelineResult)):
        (root / filename).write_text(json.dumps(model.model_json_schema(mode="serialization"), indent=2) + "\n")


if __name__ == "__main__":
    export_contracts()
