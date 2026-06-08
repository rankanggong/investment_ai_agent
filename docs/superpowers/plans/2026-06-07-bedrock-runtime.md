# Bedrock Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable Amazon Bedrock Converse API client that defaults to `qwen.qwen3-32b-v1:0` without changing existing report behavior.

**Architecture:** A focused `app/llm` package owns environment-backed Bedrock settings and the Bedrock Runtime adapter. The adapter accepts simple application messages, translates them to the standardized Converse API, and supports dependency injection so unit tests never contact AWS.

**Tech Stack:** Python 3.11+, boto3 Bedrock Runtime client, dataclasses, pytest

---

## File Structure

- Create `app/llm/__init__.py` to export the public Bedrock API.
- Create `app/llm/bedrock.py` for settings, message validation, Converse request construction, and response extraction.
- Create `tests/test_bedrock.py` for isolated settings and client behavior tests.
- Modify `pyproject.toml` to declare the boto3 runtime dependency.
- Modify `.env.example` to document the optional model and region settings.
- Modify `README.md` to document Bedrock configuration and a minimal usage example.

### Task 1: Bedrock Settings

**Files:**
- Create: `app/llm/__init__.py`
- Create: `app/llm/bedrock.py`
- Create: `tests/test_bedrock.py`

- [ ] **Step 1: Write failing settings tests**

```python
from app.llm.bedrock import BedrockSettings


def test_bedrock_settings_use_qwen_default(monkeypatch):
    monkeypatch.delenv("FINANCE_AGENT_BEDROCK_MODEL_ID", raising=False)

    settings = BedrockSettings.from_env()

    assert settings.model_id == "qwen.qwen3-32b-v1:0"


def test_bedrock_settings_allow_model_override(monkeypatch):
    monkeypatch.setenv("FINANCE_AGENT_BEDROCK_MODEL_ID", "custom.model")

    settings = BedrockSettings.from_env()

    assert settings.model_id == "custom.model"
```

- [ ] **Step 2: Run the settings tests to verify they fail**

Run: `python -m pytest tests/test_bedrock.py -v`

Expected: FAIL because `app.llm.bedrock` does not exist.

- [ ] **Step 3: Implement minimal environment-backed settings**

```python
# app/llm/bedrock.py
import os
from dataclasses import dataclass


DEFAULT_BEDROCK_MODEL_ID = "qwen.qwen3-32b-v1:0"


@dataclass(frozen=True)
class BedrockSettings:
    model_id: str = DEFAULT_BEDROCK_MODEL_ID

    @classmethod
    def from_env(cls) -> "BedrockSettings":
        return cls(
            model_id=os.environ.get(
                "FINANCE_AGENT_BEDROCK_MODEL_ID",
                DEFAULT_BEDROCK_MODEL_ID,
            )
        )
```

```python
# app/llm/__init__.py
from app.llm.bedrock import BedrockSettings

__all__ = ["BedrockSettings"]
```

- [ ] **Step 4: Run the settings tests to verify they pass**

Run: `python -m pytest tests/test_bedrock.py -v`

Expected: 2 tests PASS.

### Task 2: Converse Request and Response

**Files:**
- Modify: `app/llm/bedrock.py`
- Modify: `app/llm/__init__.py`
- Modify: `tests/test_bedrock.py`

- [ ] **Step 1: Write a failing Converse mapping test**

```python
from app.llm.bedrock import BedrockClient, BedrockSettings


class FakeRuntimeClient:
    def __init__(self):
        self.request = None

    def converse(self, **request):
        self.request = request
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [{"text": "Market summary"}],
                }
            }
        }


def test_converse_maps_messages_and_returns_text():
    runtime = FakeRuntimeClient()
    client = BedrockClient(
        settings=BedrockSettings(model_id="test.model"),
        runtime_client=runtime,
    )

    result = client.converse(
        messages=[{"role": "user", "content": "Summarize the market"}],
        system_prompt="Use only supplied facts.",
        max_tokens=300,
        temperature=0.2,
    )

    assert result == "Market summary"
    assert runtime.request == {
        "modelId": "test.model",
        "messages": [
            {"role": "user", "content": [{"text": "Summarize the market"}]}
        ],
        "system": [{"text": "Use only supplied facts."}],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0.2},
    }
```

- [ ] **Step 2: Run the mapping test to verify it fails**

Run: `python -m pytest tests/test_bedrock.py::test_converse_maps_messages_and_returns_text -v`

Expected: FAIL because `BedrockClient` does not exist.

- [ ] **Step 3: Implement the Converse wrapper**

```python
# Add to app/llm/bedrock.py
from collections.abc import Mapping, Sequence
from typing import Any


class BedrockResponseError(RuntimeError):
    pass


class BedrockClient:
    def __init__(
        self,
        settings: BedrockSettings | None = None,
        runtime_client: Any | None = None,
    ) -> None:
        self.settings = settings or BedrockSettings.from_env()
        self._runtime_client = runtime_client

    def converse(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        system_prompt: str | None = None,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        request: dict[str, Any] = {
            "modelId": self.settings.model_id,
            "messages": [self._map_message(message) for message in messages],
        }
        if system_prompt is not None:
            request["system"] = [{"text": system_prompt}]

        inference_config: dict[str, Any] = {}
        if max_tokens is not None:
            inference_config["maxTokens"] = max_tokens
        if temperature is not None:
            inference_config["temperature"] = temperature
        if inference_config:
            request["inferenceConfig"] = inference_config

        response = self._get_runtime_client().converse(**request)
        try:
            content = response["output"]["message"]["content"]
            text = "".join(block["text"] for block in content if "text" in block)
        except (KeyError, TypeError) as exc:
            raise BedrockResponseError("Bedrock response did not contain text") from exc
        if not text:
            raise BedrockResponseError("Bedrock response did not contain text")
        return text

    def _get_runtime_client(self) -> Any:
        if self._runtime_client is None:
            import boto3

            self._runtime_client = boto3.client("bedrock-runtime")
        return self._runtime_client

    @staticmethod
    def _map_message(message: Mapping[str, str]) -> dict[str, Any]:
        return {
            "role": message["role"],
            "content": [{"text": message["content"]}],
        }
```

```python
# app/llm/__init__.py
from app.llm.bedrock import BedrockClient, BedrockResponseError, BedrockSettings

__all__ = ["BedrockClient", "BedrockResponseError", "BedrockSettings"]
```

- [ ] **Step 4: Run the mapping test to verify it passes**

Run: `python -m pytest tests/test_bedrock.py::test_converse_maps_messages_and_returns_text -v`

Expected: PASS.

### Task 3: Input and Response Validation

**Files:**
- Modify: `app/llm/bedrock.py`
- Modify: `tests/test_bedrock.py`

- [ ] **Step 1: Write failing validation tests**

```python
import pytest

from app.llm.bedrock import BedrockClient, BedrockResponseError


class MalformedRuntimeClient:
    def converse(self, **request):
        return {"output": {"message": {"content": []}}}


def test_converse_rejects_invalid_role():
    client = BedrockClient(runtime_client=FakeRuntimeClient())

    with pytest.raises(ValueError, match="Unsupported message role"):
        client.converse([{"role": "system", "content": "Not valid here"}])


def test_converse_rejects_response_without_text():
    client = BedrockClient(runtime_client=MalformedRuntimeClient())

    with pytest.raises(BedrockResponseError, match="did not contain text"):
        client.converse([{"role": "user", "content": "Hello"}])
```

- [ ] **Step 2: Run the validation tests to verify the invalid-role test fails**

Run: `python -m pytest tests/test_bedrock.py::test_converse_rejects_invalid_role tests/test_bedrock.py::test_converse_rejects_response_without_text -v`

Expected: invalid-role test FAIL because roles are not validated; malformed-response test PASS.

- [ ] **Step 3: Add role and content validation**

```python
# Replace BedrockClient._map_message in app/llm/bedrock.py
@staticmethod
def _map_message(message: Mapping[str, str]) -> dict[str, Any]:
    role = message.get("role")
    if role not in {"user", "assistant"}:
        raise ValueError(f"Unsupported message role: {role}")
    content = message.get("content")
    if not content:
        raise ValueError("Message content must not be empty")
    return {"role": role, "content": [{"text": content}]}
```

- [ ] **Step 4: Run all Bedrock tests**

Run: `python -m pytest tests/test_bedrock.py -v`

Expected: all Bedrock tests PASS.

### Task 4: Dependency and Configuration Documentation

**Files:**
- Modify: `pyproject.toml`
- Modify: `.env.example`
- Modify: `README.md`

- [ ] **Step 1: Declare boto3**

```toml
dependencies = ["boto3>=1.34"]
```

- [ ] **Step 2: Document environment configuration**

Append to `.env.example`:

```dotenv
FINANCE_AGENT_BEDROCK_MODEL_ID=qwen.qwen3-32b-v1:0
AWS_REGION=us-west-2
```

- [ ] **Step 3: Add Bedrock setup and usage to README**

Add a short section explaining that:

- AWS credentials use the normal boto3 credential chain.
- `AWS_REGION` selects the Bedrock region.
- `FINANCE_AGENT_BEDROCK_MODEL_ID` defaults to `qwen.qwen3-32b-v1:0`.
- Model access must be enabled in the selected AWS region.

Include this example:

```python
from app.llm import BedrockClient

client = BedrockClient()
text = client.converse(
    [{"role": "user", "content": "Summarize these supplied market facts."}],
    system_prompt="Do not infer facts that were not supplied.",
)
```

- [ ] **Step 4: Inspect documentation changes**

Run: `git diff -- pyproject.toml .env.example README.md`

Expected: only boto3 and Bedrock setup documentation changes are present.

### Task 5: Full Verification

**Files:**
- Verify: all changed files

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -v`

Expected: all existing and new tests PASS.

- [ ] **Step 2: Verify no AWS call is made by tests**

Run: `AWS_ACCESS_KEY_ID=invalid AWS_SECRET_ACCESS_KEY=invalid python -m pytest tests/test_bedrock.py -v`

Expected: all Bedrock tests PASS because every Converse test injects a fake runtime client and settings tests do not construct a boto3 client.

- [ ] **Step 3: Review the final diff**

Run: `git diff -- app/llm tests/test_bedrock.py pyproject.toml .env.example README.md docs/plans/2026-06-07-bedrock-runtime-design.md docs/superpowers/plans/2026-06-07-bedrock-runtime.md`

Expected: changes are limited to the reusable Bedrock layer, its tests, dependencies, and documentation; daily report behavior is unchanged.
