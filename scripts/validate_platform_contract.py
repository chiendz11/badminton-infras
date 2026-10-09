import json
import sys
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
def validate(contract):
    schema = json.loads((ROOT / "contracts/platform-contract-v1.schema.json").read_text())
    Draft202012Validator(schema).validate(contract)
    for component, repository in contract["ecr"].items():
        if not repository.endswith("/" + component):
            raise ValueError(f"Wrong ECR repository for {component}")
    return contract

if __name__ == "__main__":
    validate(json.loads(Path(sys.argv[1]).read_text()))
