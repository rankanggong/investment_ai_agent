import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


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


class BedrockResponseError(RuntimeError):
    """Raised when Bedrock returns no usable text."""


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
        role = message.get("role")
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported message role: {role}")

        content = message.get("content")
        if not content:
            raise ValueError("Message content must not be empty")

        return {"role": role, "content": [{"text": content}]}
