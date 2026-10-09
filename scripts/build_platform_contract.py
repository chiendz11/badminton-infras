"""Read ONLY allow-listed non-secret Terraform outputs, then validate v1."""
import argparse
import json
from pathlib import Path
from validate_platform_contract import validate

def build(outputs):
    def value(key):
        item = outputs[key]
        if item.get("sensitive", False):
            raise ValueError(f"Refusing sensitive Terraform output: {key}")
        return item["value"]
    # RDS master ARNs are metadata only. Consumers use per-service runtime
    # application credentials populated by an operator, never RDS masters.
    return {
        "schema_version": "v1", "environment": "production",
        "aws_region": value("aws_region"), "cluster_name": value("cluster_name"),
        "cluster_endpoint": value("cluster_endpoint"), "vpc_id": value("vpc_id"),
        "vpc_cidr": value("vpc_cidr"), "ecr": value("ecr_repository_urls"),
        "database": value("database"),
        "cache": {"host": value("redis_endpoint"), "port": 6379, "tls": True},
        "messaging": {"endpoint": value("rabbitmq_endpoint")},
        "secret_arns": value("secret_arns"), "irsa": value("irsa"),
        "mongodb_allowed_cidrs": value("mongodb_allowed_cidrs"),
        "public": {"domain": value("public_domain_name"), "admin_domain": value("admin_domain_name"),
                   "certificate_arn": value("public_certificate_arn"), "zone_id": value("route53_zone_id")},
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("outputs", type=Path)
    parser.add_argument("--output", type=Path, default=Path("platform-contract-v1.json"))
    args = parser.parse_args()
    contract = build(json.loads(args.outputs.read_text()))
    validate(contract)
    args.output.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
