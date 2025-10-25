#!/usr/bin/env python3
"""
Idempotent Letta setup tooling.

Creates/updates memory blocks, agents, and dynamic groups as defined in the
JSON artefacts under ../config/. Supports dry-run, apply, and delete modes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, List, Set
from urllib.parse import urljoin

import requests

BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config.json"
ENV_PATH = BASE_DIR / ".env"


class SetupError(RuntimeError):
    """Raised for validation or API failures."""


def load_env_file(path: Path) -> Dict[str, str]:
    """Parse simple KEY=VALUE lines from an env file."""
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise SetupError(f"Invalid env line (missing '='): {line}")
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def load_json(path: Path) -> Dict:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SetupError(f"Config file missing: {path}") from exc


def require_field(data: Dict, field: str, ctx: str) -> None:
    if field not in data or data[field] in (None, ""):
        raise SetupError(f"{ctx} must include '{field}'")


def unwrap_data(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


@dataclass
class RequestResult:
    data: Optional[Dict]
    raw: Optional[requests.Response] = None


class LettaClient:
    def __init__(self, base_url: str, api_key: str, timeout: float, dry_run: bool = False):
        if not base_url:
            raise SetupError("LETTA_URL is required")
        if not api_key:
            raise SetupError("LETTA_API_KEY is required")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict] = None,
        payload: Optional[Dict] = None,
        expected: Iterable[int] = (200, 201, 202, 204),
        stream: bool = False,
    ) -> RequestResult:
        url = urljoin(f"{self.base_url}/", path.lstrip("/"))
        method_upper = method.upper()
        if self.dry_run and method_upper in {"POST", "PUT", "PATCH", "DELETE"}:
            print(f"[dry-run] {method_upper} {url}")
            return RequestResult(data=None, raw=None)

        response = self.session.request(
            method_upper,
            url,
            params=params,
            json=payload,
            timeout=self.timeout,
            stream=stream,
        )
        if response.status_code == 404:
            return RequestResult(data=None, raw=response)
        if response.status_code not in expected:
            body = None
            try:
                body = response.json()
            except Exception:
                body = response.text
            raise SetupError(f"{method_upper} {url} failed ({response.status_code}): {body}")

        if stream:
            return RequestResult(data=None, raw=response)

        if response.status_code == 204 or not response.content:
            return RequestResult(data=None, raw=response)

        try:
            return RequestResult(data=unwrap_data(response.json()), raw=response)
        except ValueError:
            return RequestResult(data=None, raw=response)

    # Memory blocks -----------------------------------------------------------------

    def find_memory_block(self, label: str) -> Optional[Dict]:
        result = self._request("GET", "/v1/blocks/", params={"label": label, "limit": 1})
        data = result.data
        if isinstance(data, list) and data:
            return data[0]
        return None

    def create_memory_block(self, payload: Dict) -> Dict:
        result = self._request("POST", "/v1/blocks/", payload=payload)
        return result.data or {}

    def update_memory_block(self, block_id: str, payload: Dict) -> Dict:
        result = self._request("PATCH", f"/v1/blocks/{block_id}", payload=payload)
        return result.data or {}

    def delete_memory_block(self, block_id: str) -> None:
        self._request("DELETE", f"/v1/blocks/{block_id}")

    # Agents ------------------------------------------------------------------------

    def find_agent(self, name: str) -> Optional[Dict]:
        result = self._request("GET", "/v1/agents", params={"name": name})
        data = result.data
        if not data:
            return None
        if isinstance(data, list):
            for item in data:
                if item.get("name") == name:
                    return item
            return None
        if isinstance(data, dict) and data.get("name") == name:
            return data
        return None

    def create_agent(self, payload: Dict) -> Dict:
        result = self._request("POST", "/v1/agents", payload=payload)
        return result.data or {}

    def update_agent(self, agent_id: str, payload: Dict) -> Dict:
        result = self._request("PATCH", f"/v1/agents/{agent_id}", payload=payload)
        return result.data or {}

    def delete_agent(self, agent_id: str) -> None:
        self._request("DELETE", f"/v1/agents/{agent_id}")

    # Groups ------------------------------------------------------------------------

    def find_group(self, name: str) -> Optional[Dict]:
        result = self._request("GET", "/v1/groups", params={"name": name})
        data = result.data
        if not data:
            return None
        if isinstance(data, list):
            for item in data:
                if item.get("name") == name:
                    return item
            return None
        if isinstance(data, dict) and data.get("name") == name:
            return data
        return None

    def create_group(self, payload: Dict) -> Dict:
        result = self._request("POST", "/v1/groups", payload=payload)
        return result.data or {}

    def update_group(self, group_id: str, payload: Dict) -> Dict:
        result = self._request("PATCH", f"/v1/groups/{group_id}", payload=payload)
        return result.data or {}

    def delete_group(self, group_id: str) -> None:
        self._request("DELETE", f"/v1/groups/{group_id}")

    # Streaming ---------------------------------------------------------------------

    def stream_group_message(self, group_id: str, payload: Dict) -> requests.Response:
        return self._request(
            "POST",
            f"/v1/groups/{group_id}/messages/stream",
            payload=payload,
            expected=(200,),
            stream=True,
        ).raw

    # Tools ------------------------------------------------------------------------

    def list_tools(self) -> List[Dict]:
        result = self._request("GET", "/v1/tools/", params={"limit": 200})
        return result.data or []

    def create_tool(self, payload: Dict) -> Dict:
        result = self._request("POST", "/v1/tools/", payload=payload)
        return result.data or {}

    def update_tool(self, tool_id: str, payload: Dict) -> Dict:
        result = self._request("PATCH", f"/v1/tools/{tool_id}", payload=payload)
        return result.data or {}

    def delete_tool(self, tool_id: str) -> None:
        self._request("DELETE", f"/v1/tools/{tool_id}")


# Validation helpers -----------------------------------------------------------------

def validate_memory_block(block: Dict) -> None:
    require_field(block, "label", "memory block")
    require_field(block, "description", block["label"])
    value = block.get("initial_value") or block.get("value")
    if not value:
        raise SetupError(f"memory block '{block['label']}' requires 'initial_value'")
    limit = block.get("character_limit")
    if not isinstance(limit, int):
        raise SetupError(f"memory block '{block['label']}' must set integer 'character_limit'")
    if limit > 2000:
        raise SetupError(f"memory block '{block['label']}' exceeds character_limit 2000")


def validate_agent(name: str, agent: Dict) -> None:
    require_field(agent, "name", f"agent '{name}'")
    require_field(agent, "description", agent["name"])
    if "model" not in agent and "llm_config" not in agent:
        raise SetupError(f"{agent['name']} must include either 'model' or 'llm_config'")
    require_field(agent, "tools", agent["name"])
    if not isinstance(agent["tools"], list):
        raise SetupError(f"agent '{agent['name']}' tools must be a list")
    if agent["name"] == "GLaDOS Orchestrator":
        if "ha_call_service" not in agent["tools"]:
            raise SetupError("orchestrator must include ha_call_service tool")
    else:
        if "ha_call_service" in agent["tools"]:
            raise SetupError(f"agent '{agent['name']}' must not call ha_call_service directly")

    # Enforce that all agents mount the standard Letta blocks
    memory_blocks = agent.get("memory_blocks", [])
    if "persona" not in memory_blocks:
        raise SetupError(f"agent '{agent['name']}' must mount 'persona' memory block")
    if "human" not in memory_blocks:
        raise SetupError(f"agent '{agent['name']}' must mount 'human' memory block")


def validate_group(group: Dict, agent_lookup: Dict[str, Dict]) -> None:
    require_field(group, "name", "group")
    if group.get("type") != "dynamic":
        raise SetupError("group must be of type 'dynamic'")
    require_field(group, "manager_id", "group")
    if "agent_glados_orchestrator" not in agent_lookup:
        raise SetupError("orchestrator agent definition missing for group validation")
    participants = group.get("participant_ids") or group.get("participants")
    if participants and not isinstance(participants, list):
        raise SetupError("group participants must be a list")
    if "agent_hermes_fast" not in agent_lookup or "agent_qwen_vl" not in agent_lookup:
        raise SetupError("group participants must include Hermes and Qwen-VL definitions")
    config = group.get("config") or {}
    if config.get("termination_token") != "[[DONE]]":
        raise SetupError("group termination_token must be [[DONE]]")
    if config.get("max_turns") != 4:
        raise SetupError("group max_turns must be 4")
    if config.get("stream_steps") is not True:
        raise SetupError("group must enable stream_steps")


def ensure_memory_blocks(client: LettaClient, blocks: Iterable[Dict], dry_run: bool) -> Dict[str, Optional[str]]:
    ids: Dict[str, Optional[str]] = {}
    for block in blocks:
        validate_memory_block(block)
        label = block["label"]
        existing = client.find_memory_block(label)
        payload = {
            "label": label,
            "description": block.get("description", ""),
            "value": block.get("initial_value") or block.get("value"),
            "limit": block.get("character_limit"),
            "metadata": {"tags": block.get("tags", [])},
            "read_only": False,
        }
        if existing:
            block_id = existing.get("id")
            if not block_id:
                raise SetupError(f"Existing memory block '{label}' missing id")
            ids[label] = block_id
            print(f"[memory] Updating {label} (id={block_id})")
            if not dry_run:
                client.update_memory_block(block_id, payload)
        else:
            print(f"[memory] Creating {label}")
            if not dry_run:
                created = client.create_memory_block(payload)
                block_id = created.get("id")
                if not block_id:
                    lookup = client.find_memory_block(label)
                    block_id = lookup.get("id") if lookup else None
                if not block_id:
                    raise SetupError(f"Letta did not return id for memory block '{label}'")
                ids[label] = block_id
            else:
                ids[label] = None
    return ids


def format_model_value(model_value) -> Optional[str]:
    if isinstance(model_value, str) or model_value is None:
        return model_value
    if isinstance(model_value, dict):
        name = model_value.get("name")
        provider = model_value.get("provider")
        if provider and name:
            return f"{provider}/{name}"
        return name
    raise SetupError(f"Unsupported model configuration: {model_value}")


def ensure_agent(
    client: LettaClient,
    agent_json: Dict,
    memory_ids: Dict[str, Optional[str]],
    available_tools: Optional[Set[str]],
    dry_run: bool,
) -> Tuple[str, Optional[str]]:
    validate_agent(agent_json.get("name", ""), agent_json)
    payload = dict(agent_json)
    payload.pop("id", None)
    payload["external_id"] = agent_json.get("id")

    block_labels = payload.pop("memory_blocks", []) or []
    block_ids: list[str] = []
    for label in block_labels:
        block_id = memory_ids.get(label)
        if not block_id:
            if dry_run:
                continue
            raise SetupError(f"No memory block id found for label '{label}'")
        block_ids.append(block_id)
    if block_ids:
        payload["block_ids"] = block_ids

    model_value = format_model_value(payload.get("model"))
    if model_value:
        payload["model"] = model_value

    name = agent_json["name"]

    tools = payload.get("tools") or []
    if available_tools is not None and not dry_run:
        missing = [tool for tool in tools if tool not in available_tools]
        if missing:
            raise SetupError(f"Agent {name} references unknown tools: {', '.join(missing)}")
    existing = client.find_agent(name)
    if existing:
        agent_id = existing.get("id")
        print(f"[agent] Updating {name} (id={agent_id})")
        if not dry_run:
            client.update_agent(agent_id, payload)
        return name, agent_id
    print(f"[agent] Creating {name}")
    if dry_run:
        return name, None
    created = client.create_agent(payload)
    return name, created.get("id")


def ensure_tools(client: LettaClient, tool_specs: List[Dict], dry_run: bool) -> Dict[str, Optional[str]]:
    existing_tools = {tool.get("name"): tool for tool in client.list_tools()}
    tool_ids: Dict[str, Optional[str]] = {}

    for spec in tool_specs:
        name = spec.get("function_name")
        if not name:
            raise SetupError("tool spec missing function_name")

        payload = {k: spec[k] for k in ("description", "tags", "source_code", "pip_requirements", "npm_requirements", "return_char_limit", "json_schema", "args_json_schema", "source_type", "default_requires_approval") if k in spec}
        if "source_code" not in payload or not payload["source_code"]:
            raise SetupError(f"tool '{name}' must include source_code")

        existing = existing_tools.get(name)
        if existing:
            tool_id = existing.get("id")
            tool_ids[name] = tool_id
            print(f"[tool] Updating {name} (id={tool_id})")
            if not dry_run:
                client.update_tool(tool_id, payload)
        else:
            print(f"[tool] Creating {name}")
            if dry_run:
                tool_ids[name] = None
            else:
                created = client.create_tool(payload)
                tool_id = created.get("id")
                if not tool_id:
                    lookup = {tool.get("name"): tool for tool in client.list_tools()}
                    tool_id = lookup.get(name, {}).get("id")
                if not tool_id:
                    raise SetupError(f"Letta did not return id for tool '{name}'")
                tool_ids[name] = tool_id

    return tool_ids


def ensure_group(
    client: LettaClient,
    group_json: Dict,
    agent_ids: Dict[str, Optional[str]],
    dry_run: bool,
) -> Tuple[str, Optional[str]]:
    validate_group(group_json, agent_ids)
    payload = dict(group_json)
    payload.pop("id", None)

    manager_key = group_json["manager_id"]
    manager_id = agent_ids.get("agent_glados_orchestrator") or agent_ids.get(manager_key)
    if not manager_id:
        raise SetupError("orchestrator agent id missing; cannot create group")

    payload["manager_id"] = manager_id
    participant_keys = [key for key in ("agent_hermes_fast", "agent_qwen_vl", "agent_memory_archival") if key in agent_ids]
    participant_ids = [agent_ids[k] for k in participant_keys if agent_ids[k]]
    if len(participant_ids) < 2:
        raise SetupError("group requires Hermes and Qwen-VL participant IDs")
    payload["participant_ids"] = participant_ids
    payload["agent_ids"] = [manager_id] + participant_ids

    name = group_json["name"]
    existing = client.find_group(name)
    if existing:
        group_id = existing.get("id")
        print(f"[group] Updating {name} (id={group_id})")
        if not dry_run:
            client.update_group(group_id, payload)
        return name, group_id

    print(f"[group] Creating {name}")
    if dry_run:
        return name, None

    created = client.create_group(payload)
    return name, created.get("id")


def smoke_test(client: LettaClient, group_id: str) -> None:
    print("[smoke] Sending test message to dynamic group...")
    try:
        response = client.stream_group_message(
            group_id,
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "hi"
                    }
                ],
                "stream": True
            },
        )
    except SetupError as exc:
        print(f"[smoke] Warning: streaming test failed ({exc})")
        return

    if response is None:
        print("[smoke] Warning: streaming test returned no response")
        return
    if response.status_code != 200:
        print(f"[smoke] Warning: streaming status {response.status_code}")
        return
    content_type = response.headers.get("Content-Type", "")
    if "text/event-stream" not in content_type.lower():
        raise SetupError(f"Smoke test expected text/event-stream, got {content_type}")
    lines_read = 0
    for line in response.iter_lines(decode_unicode=True):
        if line:
            print(f"[stream] {line}")
            lines_read += 1
        if lines_read >= 5:
            break
    response.close()
    print("[smoke] Stream looks healthy (truncated).")


def delete_all(client: LettaClient, config: Dict) -> None:
    data = load_config_payloads(config)
    group_payload = data["group"]
    group_existing = client.find_group(group_payload["name"])
    if group_existing:
        gid = group_existing.get("id")
        print(f"[delete] Removing group {group_payload['name']} (id={gid})")
        if not client.dry_run:
            client.delete_group(gid)
    else:
        print(f"[delete] Group {group_payload['name']} not found")

    for key, agent_payload in data["agents"].items():
        existing = client.find_agent(agent_payload["name"])
        if existing:
            aid = existing.get("id")
            print(f"[delete] Removing agent {agent_payload['name']} (id={aid})")
            if not client.dry_run:
                client.delete_agent(aid)
        else:
            print(f"[delete] Agent {agent_payload['name']} not found")

    for block in data["memory_blocks"]:
        existing = client.find_memory_block(block["label"])
        if existing:
            bid = existing.get("id")
            print(f"[delete] Removing memory block {block['label']} (id={bid})")
            if not client.dry_run:
                client.delete_memory_block(bid)
        else:
            print(f"[delete] Memory block {block['label']} not found")

    if data.get("tools"):
        existing_tools = {tool.get("name"): tool for tool in client.list_tools()}
        for tool_spec in data["tools"]:
            tool_name = tool_spec.get("function_name")
            if not tool_name:
                continue
            existing_tool = existing_tools.get(tool_name)
            if existing_tool:
                tid = existing_tool.get("id")
                print(f"[delete] Removing tool {tool_name} (id={tid})")
                if not client.dry_run:
                    client.delete_tool(tid)


def load_config_payloads(config: Dict) -> Dict:
    memory_blocks_path = (BASE_DIR / config["memory_blocks"]).resolve()
    agents_config = config["agents"]
    group_path = (BASE_DIR / config["group"]).resolve()
    tools_path = (BASE_DIR / config.get("tools", "")).resolve() if config.get("tools") else None

    blocks = load_json(memory_blocks_path)
    if not isinstance(blocks, list):
        raise SetupError("memory_blocks JSON must be a list")

    agents: Dict[str, Dict] = {}
    for key, rel_path in agents_config.items():
        path = (BASE_DIR / rel_path).resolve()
        agents[key] = load_json(path)

    group = load_json(group_path)
    tools = []
    if tools_path:
        tools = load_json(tools_path)
        if not isinstance(tools, list):
            raise SetupError("tools JSON must be a list")

    return {"memory_blocks": blocks, "agents": agents, "group": group, "tools": tools}


def write_ids(ids_path: Path, memory_ids: Dict[str, Optional[str]], tool_ids: Dict[str, Optional[str]], agent_ids: Dict[str, Optional[str]], group_name: str, group_id: Optional[str]) -> None:
    payload = {
        "memory_blocks": memory_ids,
        "tools": tool_ids,
        "agents": {
            "orchestrator": agent_ids.get("agent_glados_orchestrator"),
            "hermes": agent_ids.get("agent_hermes_fast"),
            "qwen_vl": agent_ids.get("agent_qwen_vl"),
            "memory_archival": agent_ids.get("agent_memory_archival"),
        },
        "group": {group_name: group_id},
    }
    ids_path.write_text(json.dumps(payload, indent=2))
    print(f"[output] Wrote identifiers to {ids_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ensure Letta dynamic group configuration.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--apply", action="store_true", help="Upsert memory blocks, agents, group, then run smoke test.")
    group.add_argument("--dry-run", action="store_true", help="Validate config and show planned changes without mutating.")
    group.add_argument("--delete-all", action="store_true", help="Delete configured memory blocks, agents, and group.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = load_json(CONFIG_PATH)
    env_file_values = load_env_file(ENV_PATH)

    letta_url = os.environ.get("LETTA_URL", env_file_values.get("LETTA_URL"))
    api_key = os.environ.get("LETTA_API_KEY", env_file_values.get("LETTA_API_KEY"))
    timeout = float(os.environ.get("LETTA_TIMEOUT_S", env_file_values.get("LETTA_TIMEOUT_S", 15)))

    if args.delete_all:
        delete_client = LettaClient(letta_url, api_key, timeout, dry_run=False)
        delete_all(delete_client, config)
        ids_path = BASE_DIR / config.get("output_ids", ".letta_ids.json")
        if ids_path.exists():
            ids_path.unlink()
            print(f"[delete] Removed {ids_path}")
        return

    dry_run = args.dry_run
    payloads = load_config_payloads(config)
    client = LettaClient(letta_url, api_key, timeout, dry_run=dry_run)

    print(f"[mode] {'dry-run' if args.dry_run else 'apply'}")

    memory_ids = ensure_memory_blocks(client, payloads["memory_blocks"], dry_run=client.dry_run)

    tool_specs = payloads.get("tools", [])
    tool_ids = ensure_tools(client, tool_specs, dry_run=client.dry_run) if tool_specs else {}
    if client.dry_run:
        available_tool_names: Optional[Set[str]] = set(tool_ids.keys()) if tool_specs else None
    else:
        current_tools = client.list_tools()
        available_tool_names = {tool.get("name") for tool in current_tools if tool.get("name")}

    agent_ids: Dict[str, Optional[str]] = {}
    for key, agent_payload in payloads["agents"].items():
        _, agent_id = ensure_agent(client, agent_payload, memory_ids, available_tool_names, dry_run=client.dry_run)
        agent_key = agent_payload.get("id") or (key if key.startswith("agent_") else f"agent_{key}")
        agent_ids[agent_key] = agent_id

    group_name, group_id = ensure_group(client, payloads["group"], agent_ids, dry_run=client.dry_run)

    if client.dry_run:
        print("[dry-run] Skipping smoke test and ID file write.")
        return

    if not group_id:
        raise SetupError("Group creation returned no id; aborting.")

    smoke_test(client, group_id)

    ids_path = BASE_DIR / config.get("output_ids", ".letta_ids.json")
    write_ids(ids_path, memory_ids, tool_ids, agent_ids, group_name, group_id)

    stream_url = f"{letta_url.rstrip('/')}/v1/groups/{group_id}/messages/stream"
    print("\nLetta Group Stream URL:")
    print(stream_url)


if __name__ == "__main__":
    try:
        main()
    except SetupError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        sys.exit(130)
