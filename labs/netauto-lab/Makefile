# Atalhos do lab. Rode a partir de labs/netauto-lab.
SHELL := /bin/bash
PY ?= .venv/bin/python
VENV_BIN := .venv/bin
export RUN_ID ?= $(shell date +%Y%m%d-%H%M%S)
export NETBOX_API ?= $(NETBOX_URL)

# LAB_SIZE=mini: 1 spine e 2 leaves, para máquinas de 6 a 8 GB
LAB_SIZE ?= full
ifeq ($(LAB_SIZE),mini)
TOPO ?= topology/fabric-mini.clab.yml
FABRIC ?= data/fabric-mini.yml
export GNMIC_FILE ?= gnmic-mini.yml
else
TOPO ?= topology/fabric.clab.yml
FABRIC ?= data/fabric.yml
endif
ANSIBLE := cd ansible && ../$(VENV_BIN)/ansible-playbook

.PHONY: help venv collections lab-up lab-down netbox-up seed render pre backup apply post drift rollback deploy deploy-check drift-watch mon-up mon-down test lint

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

venv: ## Cria o ambiente Python com as dependências de dev
	python3 -m venv .venv && $(VENV_BIN)/pip install -q -r requirements-dev.txt

collections: ## Instala as coleções Ansible (nokia.srlinux, netbox.netbox)
	cd ansible && ../$(VENV_BIN)/ansible-galaxy collection install -r requirements.yml -p ./collections

lab-up: ## Sobe os 4 SR Linux no containerlab
	sudo containerlab deploy -t $(TOPO) --reconfigure

lab-down: ## Derruba o lab
	sudo containerlab destroy -t $(TOPO) --cleanup

netbox-up: ## Sobe o NetBox local (netbox-docker)
	./netbox/setup.sh

seed: ## Carrega data/fabric.yml no NetBox
	$(PY) -m netauto.seed --fabric $(FABRIC)

render: ## Gera build/intents a partir do NetBox
	$(PY) -m netauto.render --source netbox

pre: ## Pre-checks (Robot)
	$(VENV_BIN)/robot --pythonpath . --outputdir build/robot/pre robot/pre_checks.robot

backup: ## Backup da running de todos os equipamentos
	$(ANSIBLE) playbooks/backup.yml

apply: ## Aplica a intenção (um equipamento por vez)
	$(ANSIBLE) playbooks/apply.yml --diff

post: ## Post-checks (Robot): interfaces, LLDP x NetBox, drift
	$(VENV_BIN)/robot --pythonpath . --outputdir build/robot/post robot/post_checks.robot

drift: ## Relatório de drift em build/drift/report.json
	$(PY) -m netauto.drift

rollback: ## Volta o backup do RUN_ID informado: make rollback RUN_ID=...
	$(ANSIBLE) playbooks/rollback.yml

deploy: ## Fluxo completo num trace só, com rollback automático se o post-check falhar
	$(PY) -m netauto.pipeline deploy

deploy-check: ## Simula o deploy (ansible --check, nada muda na rede)
	$(PY) -m netauto.pipeline deploy --check

drift-watch: ## Render + drift a cada 5 min (mantém o painel e os alertas vivos)
	while true; do export RUN_ID=$$(date +%Y%m%d-%H%M%S); $(PY) -m netauto.render --source netbox && $(PY) -m netauto.drift; sleep 300; done

mon-up: ## Sobe gnmic + Grafana Alloy (precisa de monitoring/.env)
	cd monitoring && docker compose up -d
	@echo; echo "Para mandar traces e métricas do pipeline:"; echo "  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318"

mon-down: ## Derruba o monitoramento
	cd monitoring && docker compose down

test: ## Testes unitários (sem equipamento)
	$(PY) -m pytest

lint: ## ruff + ansible-lint
	$(VENV_BIN)/ruff check . && $(VENV_BIN)/ruff format --check .
	cd ansible && ../$(VENV_BIN)/ansible-lint
