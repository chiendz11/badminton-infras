"""Verification checks for Badminton Local Development & Contracts."""

import ast
from pathlib import Path

from .common import ROOT, read


def check():
    for path in (ROOT / "localdev").glob("*.py"):
        ast.parse(path.read_text(), filename=str(path))

    contract = read(ROOT / "local/config/contract.json")
    if contract.get("cluster_name") != "badminton-local":
        raise ValueError("Unexpected cluster name in contract")
    if contract.get("namespace") != "badminton":
        raise ValueError("Unexpected namespace in contract")

    catalog = read(ROOT / "local/config/runtime-catalog.json")["components"]
    for comp in ("booking-core", "ai-service", "api-gateway", "web", "admin"):
        if comp not in catalog:
            raise ValueError(f"Component {comp} missing in runtime catalog")

    print("Badminton local syntax and contract validation passed.")


if __name__ == "__main__":
    check()

