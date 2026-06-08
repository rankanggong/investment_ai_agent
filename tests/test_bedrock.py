import pytest

from app.llm.bedrock import BedrockClient, BedrockResponseError, BedrockSettings


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


class MalformedRuntimeClient:
    def converse(self, **request):
        return {"output": {"message": {"content": []}}}


def test_bedrock_settings_use_qwen_default(monkeypatch):
    monkeypatch.delenv("FINANCE_AGENT_BEDROCK_MODEL_ID", raising=False)

    settings = BedrockSettings.from_env()

    assert settings.model_id == "qwen.qwen3-32b-v1:0"


def test_bedrock_settings_allow_model_override(monkeypatch):
    monkeypatch.setenv("FINANCE_AGENT_BEDROCK_MODEL_ID", "custom.model")

    settings = BedrockSettings.from_env()

    assert settings.model_id == "custom.model"


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


def test_converse_rejects_invalid_role():
    client = BedrockClient(runtime_client=FakeRuntimeClient())

    with pytest.raises(ValueError, match="Unsupported message role"):
        client.converse([{"role": "system", "content": "Not valid here"}])


def test_converse_rejects_empty_content():
    client = BedrockClient(runtime_client=FakeRuntimeClient())

    with pytest.raises(ValueError, match="must not be empty"):
        client.converse([{"role": "user", "content": ""}])


def test_converse_rejects_response_without_text():
    client = BedrockClient(runtime_client=MalformedRuntimeClient())

    with pytest.raises(BedrockResponseError, match="did not contain text"):
        client.converse([{"role": "user", "content": "Hello"}])
