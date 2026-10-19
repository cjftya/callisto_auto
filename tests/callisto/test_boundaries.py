import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from google.genai import types
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
import pytest
from typer.testing import CliRunner

from callisto.cli import app
from callisto.llm_adapter.errors import UnsupportedCapability
from callisto.llm_adapter.native import Client, convert_contents


def test_configuration_requires_no_api_key():
    from artemis.config.llm import get_default_llm_config, lightweight_judge_default
    config = get_default_llm_config()
    config.validate_providers()
    assert config.operator.provider == "cli"
    assert lightweight_judge_default().provider == "cli"


def test_factory_rejects_direct_api_without_constructing_client():
    from artemis.llm.router import ModelEndpoint, ModelFactory
    with pytest.raises(ValueError, match="direct AI API"):
        ModelFactory.create_model(ModelEndpoint(provider="google", model_name="legacy"))


def test_doctor_help_never_start_ai_cli(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: pytest.fail("doctor launched a process"))
    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code in (0, 1)
    report = json.loads(result.stdout)
    assert report["authentication"] == report["live_inference"] == "not_checked"
    help_text = runner.invoke(app, ["--help"]).stdout
    assert all(command not in help_text for command in (" ui ", " server ", " mcp ", " restart "))


def test_flash_profile_rejected_before_initialization():
    result = CliRunner().invoke(app, ["run", "test goal", "--profile", "flash"])
    assert result.exit_code == 2
    assert "Only the Pro" in result.output


def test_cli_version_does_not_require_a_subcommand():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Callisto 0.1.0" in result.stdout


def test_graph_prompts_and_core_agents_match_upstream_manifest():
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "docs/upstream-preserved-manifest.json").read_text())
    assert len(manifest) > 20
    for name, digest in manifest.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, name


def test_native_message_tool_id_roundtrip():
    messages = convert_contents([
        types.Content(role="user", parts=[types.Part.from_text(text="tap")]),
        types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(
            id="native-call", name="tap", args={"x": 1}))]),
        types.Content(role="user", parts=[types.Part(function_response=types.FunctionResponse(
            id="native-call", name="tap", response={"done": True}))]),
    ])
    assert isinstance(messages[0], HumanMessage)
    assert isinstance(messages[1], AIMessage)
    assert isinstance(messages[2], ToolMessage)
    assert messages[2].tool_call_id == messages[1].tool_calls[0]["id"] == "native-call"


@pytest.mark.asyncio
async def test_native_port_uses_cli_and_preserves_response_contract():
    fake = AsyncMock()
    fake.ainvoke.return_value = AIMessage(content="answer")
    with patch("callisto.llm_adapter.native.configured_model", return_value=fake):
        response = await Client().aio.models.generate_content(model="legacy",
            contents=[types.Content(role="user", parts=[types.Part.from_text(text="hi")])])
    assert response.text == "answer"
    assert fake.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_native_cloud_features_fail_explicitly():
    client = Client()
    with pytest.raises(UnsupportedCapability):
        await client.aio.files.upload(file="private-video.mp4")
    with pytest.raises(UnsupportedCapability):
        await client.aio.caches.create(model="legacy")
    with pytest.raises(UnsupportedCapability):
        await client.aio.interactions.create(model="legacy")


def test_native_media_is_not_silently_discarded():
    with pytest.raises(UnsupportedCapability):
        convert_contents([types.Content(role="user", parts=[
            types.Part(inline_data=types.Blob(mime_type="audio/wav", data=b"audio"))])])


@pytest.mark.parametrize("status,summary,exit_code,test_status", [
    ("completed", {"passed": 1}, 0, "passed"),
    ("completed", {"failed": 1}, 1, "failed"),
    ("completed", {"inconclusive": 1}, 2, "incomplete"),
    ("completed", {}, 0, "not_reported"),
    ("failed", {}, 1, "not_reported"),
])
def test_cli_preserves_task_and_test_verdict_axes(monkeypatch, tmp_path, status, summary, exit_code, test_status):
    monkeypatch.delenv("CALLISTO_FORBID_LIVE_CLI")
    async def fake_task(**kwargs):
        assert kwargs["profile"] == "pro"
        kwargs["result_report"].update(status=status, result={"content": {"test_summary": summary}})
    monkeypatch.setattr("artemis.interfaces.cli.commands.run.execute_task", fake_task)
    result = CliRunner().invoke(app, ["run", "mock test only", "--traces-path", str(tmp_path)])
    assert result.exit_code == exit_code
    metadata = json.loads(result.stdout)
    assert metadata["status"] == status and metadata["test_status"] == test_status
    persisted = json.loads(Path(metadata["result_file"]).read_text())
    assert persisted["test_status"] == test_status


def test_cli_disabled_environment_cannot_run_live():
    result = CliRunner().invoke(app, ["run", "not to be executed"])
    assert result.exit_code == 2
    assert "Live AI inference is disabled" in result.output


@pytest.mark.asyncio
async def test_native_function_schema_and_usage_conversion():
    import jsonschema
    from unittest.mock import MagicMock
    fake = MagicMock()
    fake.bind_tools.return_value = fake
    fake.ainvoke = AsyncMock(return_value=AIMessage(content="", tool_calls=[
        {"name": "tap", "args": {"x": 3}, "id": "n1"}],
        usage_metadata={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}))
    config = types.GenerateContentConfig(tools=[types.Tool(function_declarations=[
        types.FunctionDeclaration(name="tap", parameters=types.Schema(type="OBJECT",
            properties={"x": types.Schema(type="INTEGER")}, required=["x"]))])])
    with patch("callisto.llm_adapter.native.configured_model", return_value=fake):
        response = await Client().generate_content(model="legacy", contents="tap", config=config)
    declaration = fake.bind_tools.call_args.args[0][0]
    jsonschema.Draft202012Validator.check_schema(declaration["function"]["parameters"])
    assert response.function_calls[0].id == "n1"
    assert response.usage_metadata.total_token_count == 14
