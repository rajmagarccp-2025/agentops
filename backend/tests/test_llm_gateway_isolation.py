import sys

from platform_api.llm.gateway import default_gateway
from platform_api.llm.types import ChatMessage, LLMRequest, MessageRole, ModelAlias
from platform_api.security import Principal


def test_agent_cannot_import_provider_sdks_directly() -> None:
    forbidden_sdk_modules = [
        "openai",
        "anthropic",
        "google.generativeai",
        "google.genai",
        "boto3.services.bedrock",
    ]
    agent_modules = [
        mod_name for mod_name in sys.modules if mod_name.startswith("platform_api.agents.")
    ]
    for agent_mod in agent_modules:
        mod_obj = sys.modules[agent_mod]
        for sdk in forbidden_sdk_modules:
            assert not hasattr(mod_obj, sdk), (
                f"Module {agent_mod} directly imported forbidden SDK {sdk}"
            )


def test_llm_gateway_logical_aliases_and_telemetry() -> None:
    gateway = default_gateway()
    principal = Principal("user-1", "tenant-llm-test", frozenset(), frozenset())

    req = LLMRequest(
        task="testing_alias",
        model_alias=ModelAlias.REASONING_FAST,
        messages=[ChatMessage(role=MessageRole.USER, content="Hello fast reasoner")],
    )
    res = gateway.complete(req, principal)

    assert res.provider == "mock-primary"
    assert res.model == "mock-fast-v1"
    assert res.input_tokens > 0
    assert res.output_tokens > 0
    assert res.latency_ms > 0
    assert res.estimated_cost_usd > 0


def test_llm_gateway_structured_output_validation() -> None:
    gateway = default_gateway()
    principal = Principal("user-1", "tenant-llm-test", frozenset(), frozenset())

    req = LLMRequest(
        task="testing_structured",
        model_alias=ModelAlias.STRUCTURED_OUTPUT,
        response_format="json",
        messages=[ChatMessage(role=MessageRole.USER, content="Generate json")],
    )
    res = gateway.complete(req, principal)

    assert res.structured is not None
    assert res.structured.get("grounded") is True
