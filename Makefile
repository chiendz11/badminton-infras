PYTHON ?= .venv/bin/python

.PHONY: local-init local-up local-secrets local-build local-import local-bootstrap-argocd local-migrate local-status local-check tf-init tf-plan tf-apply tf-destroy

local-init:
	$(PYTHON) -m localdev init

local-up:
	$(PYTHON) -m localdev up

local-secrets:
	$(PYTHON) -m localdev secrets

local-build:
	$(PYTHON) -m localdev build

local-import:
	$(PYTHON) -m localdev import-images

local-bootstrap-argocd:
	$(PYTHON) -m localdev bootstrap-argocd

local-migrate:
	$(PYTHON) -m localdev migrate

local-status:
	$(PYTHON) -m localdev status

local-check:
	$(PYTHON) -m localdev.checks

tf-init:
	cd terraform/local && terraform init

tf-plan:
	cd terraform/local && terraform plan

tf-apply:
	cd terraform/local && terraform apply -auto-approve

tf-destroy:
	cd terraform/local && terraform destroy -auto-approve

