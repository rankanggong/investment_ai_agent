# Bedrock Runtime Design

## Scope

Add a reusable Amazon Bedrock runtime and configuration layer. This change does
not add LLM-generated content to the existing daily report or alter Phase 1
behavior.

## Architecture

Create a small `app/llm` package with:

- `BedrockSettings`, which reads Bedrock configuration from environment
  variables.
- `BedrockClient`, which wraps the Bedrock Runtime Converse API behind a
  provider-neutral text conversation method.

The default model ID is `qwen.qwen3-32b-v1:0`. It can be overridden with
`FINANCE_AGENT_BEDROCK_MODEL_ID`.

The implementation uses the standardized Converse API instead of model-specific
`InvokeModel` request bodies. This keeps future agents independent of Qwen's
wire format and makes model replacement a configuration change.

## Configuration

Supported environment variables:

- `FINANCE_AGENT_BEDROCK_MODEL_ID`, defaulting to `qwen.qwen3-32b-v1:0`
- `AWS_REGION` or `AWS_DEFAULT_REGION`, used by the standard AWS SDK session

Credentials are not read or stored by the application. Boto3 uses the standard
AWS credential provider chain, including environment variables, shared AWS
configuration, IAM roles, and workload identity.

## Client Contract

`BedrockClient.converse()` accepts:

- A sequence of conversation messages with `user` or `assistant` roles
- An optional system prompt
- Optional inference settings such as maximum tokens and temperature

It calls Bedrock Runtime's Converse API and returns the model's text response.
Malformed Bedrock responses raise a clear application error. AWS SDK service and
credential errors propagate with their original context.

The boto3 runtime client can be injected for tests. Production code creates it
from a boto3 session only when needed.

## Error Handling

- Missing response text raises a Bedrock response error.
- Invalid application-level message roles are rejected before making an AWS
  request.
- AWS authentication, authorization, throttling, and model-access errors remain
  boto3/botocore errors so callers retain their structured metadata.

## Testing

Unit tests use a fake Bedrock Runtime client and never call AWS. Tests cover:

- Default and overridden model configuration
- Converse request construction
- System prompt and inference configuration mapping
- Text extraction from a valid response
- Invalid roles and malformed responses

The existing Phase 1 test suite must remain unchanged and pass.
