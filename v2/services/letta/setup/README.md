# Letta Dynamic Group Setup

This helper fires the Letta APIs to create/update the memory blocks, agents, and dynamic group described in `v2/docs/AGENTS.md`.

## Prerequisites

- Python 3.10+
- `requests` library (`pip install requests`)
- A reachable Letta server and API key

Populate `.env` in this directory with the correct endpoint and key.

```
LETTA_URL=http://letta:8283
LETTA_API_KEY=super-secret
LETTA_TIMEOUT_S=15
```

## Usage

```
python setup_letta_group.py --dry-run   # validate config, show intended mutations
python setup_letta_group.py --apply     # upsert memory blocks, agents, group, then smoke test
python setup_letta_group.py --delete-all
```

`config.json` points at the JSON artefacts created earlier. Successful runs write IDs to `.letta_ids.json` and print the group streaming URL you can drop into Home Assistant.


make setup-letta