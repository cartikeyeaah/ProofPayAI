"""Run from repository root: python -m backend.export_openapi."""
from pathlib import Path
import yaml
from backend.app.main import app

if __name__ == "__main__":
    output = Path(__file__).resolve().parents[1] / "contracts" / "openapi.yaml"
    output.write_text(yaml.safe_dump(app.openapi(), sort_keys=False))
