PYTHON ?= .venv/bin/python
PAT_FILE ?= ../PAT.txt
GITHUB_USERNAME ?= chiendz11

.PHONY: local-init local-up local-secrets local-build local-import local-bootstrap-argocd local-image-updater-pat local-migrate local-status local-check local-test tf-init tf-plan tf-apply tf-destroy

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

local-image-updater-pat:
	$(PYTHON) -m localdev image-updater-pat --username $(GITHUB_USERNAME) --token-file $(PAT_FILE)

local-migrate:
	$(PYTHON) -m localdev migrate

local-status:
	$(PYTHON) -m localdev status

local-check:
	$(PYTHON) -m localdev.checks

local-test:
	$(PYTHON) -m unittest discover -s local/tests -p 'test_*.py' -v

tf-init:
	cd terraform/local && terraform init

tf-plan:
	cd terraform/local && terraform plan

tf-apply:
	cd terraform/local && terraform apply -auto-approve

tf-destroy:
	cd terraform/local && terraform destroy -auto-approve
