.PHONY: setup-letta smoke-letta

setup-letta: ## Idempotent create/update Letta memory blocks, agents, and group
	cd v2/services/letta/setup && python3 setup_letta_group.py --apply

smoke-letta: ## Validate then apply Letta configuration
	cd v2/services/letta/setup && python3 setup_letta_group.py --dry-run && python3 setup_letta_group.py --apply
