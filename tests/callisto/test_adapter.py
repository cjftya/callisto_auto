import asyncio
import base64
import json
from pathlib import Path
import sys
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel
import pytest

from callisto.llm_adapter.codec import encode_messages
from callisto.llm_adapter.errors import CLIError, CLIProtocolError, UnsupportedCapability
from callisto.llm_adapter.model import CLIChatModel
from callisto.llm_adapter.process import ProcessResult, run_process
from callisto.llm_adapter.providers import decode_result, command_for

TOOL = {"type": "function", "function": {"name": "tap", "description": "Tap a coordinate",
    "parameters": {"type": "object", "properties": {"x": {"type": "integer"}}, "required": ["x"],
                   "additionalProperties": False}}}


def envelope(content="answer", calls=None):
    return json.dumps({"content": content, "tool_calls": calls or []})


def cli_result(text, *, complete=True, stderr=""):
    events = [{"type": "item.completed", "item": {"type": "agent_message", "text": text}}]
    if complete:
        events.append({"type": "turn.completed", "usage": {"input_tokens": 12, "output_tokens": 4}})
    return ProcessResult(0, "\n".join(map(json.dumps, events)), stderr)


def fake_inference(monkeypatch, result):
    from callisto.llm_adapter import model
    monkeypatch.setattr(model, "command_for", lambda *args: ["MOCK_ONLY_NO_CLI_EXECUTION"])
    execute = AsyncMock(return_value=result)
    monkeypatch.setattr(model, "run_process", execute)
    return execute


def test_lossless_roles_tools_and_image_order(tmp_path):
    image = "data:image/png;base64," + base64.b64encode(b"image-bytes").decode()
    history = [SystemMessage(content="system"), HumanMessage(content=[
        {"type": "text", "text": "first"}, {"type": "image_url", "image_url": {"url": image}}]),
        AIMessage(content="", tool_calls=[{"name": "tap", "args": {"x": 2}, "id": "a"}]),
        ToolMessage(content="done", tool_call_id="a")]
    records, images = encode_messages(history, tmp_path)
    assert [r["role"] for r in records] == ["system", "human", "ai", "tool"]
    assert records[2]["tool_calls"][0]["id"] == records[3]["tool_call_id"] == "a"
    assert records[1]["content"][1]["index"] == 1
    assert Path(images[0]).read_bytes() == b"image-bytes"


@pytest.mark.parametrize("block", [
    {"type": "image_url", "image_url": {"url": "https://example.com/private.png"}},
    {"type": "input_audio", "input_audio": {"data": "AAAA", "format": "wav"}},
])
def test_unsupported_media_fails_before_process(block, tmp_path):
    with pytest.raises(UnsupportedCapability):
        encode_messages([HumanMessage(content=[block])], tmp_path)


@pytest.mark.asyncio
async def test_text_and_measured_usage_warning_is_not_auth_failure(monkeypatch):
    fake_inference(monkeypatch, cli_result(envelope(), stderr="featured plugins: 401 Unauthorized"))
    result = await CLIChatModel().ainvoke([HumanMessage(content="hello")])
    assert result.content == "answer"
    assert result.usage_metadata["total_tokens"] == 16


@pytest.mark.asyncio
async def test_tool_roundtrip_and_full_conversation(monkeypatch):
    call = {"id": "a", "name": "tap", "args_json": '{"x":2}'}
    execute = fake_inference(monkeypatch, cli_result(envelope("", [call])))
    result = await CLIChatModel().bind_tools([TOOL], tool_choice="required").ainvoke("tap")
    assert result.tool_calls[0]["args"] == {"x": 2}
    await CLIChatModel().bind_tools([TOOL]).ainvoke([
        HumanMessage(content="tap"), result, ToolMessage(content="done", tool_call_id="a")])
    sent = json.loads(execute.call_args.kwargs["stdin"].split("\n", 1)[1])
    assert sent["messages"][1]["tool_calls"][0]["id"] == "a"
    assert sent["messages"][2]["tool_call_id"] == "a"


@pytest.mark.parametrize("calls,choice", [
    ([{"id": "a", "name": "unknown", "args_json": "{}"}], "auto"),
    ([{"id": "a", "name": "tap", "args_json": '{"x":"wrong"}'}], "auto"),
    ([{"id": "a", "name": "tap", "args_json": '{"x":1}'}] * 2, "auto"),
    ([], "required"),
    ([{"id": "a", "name": "tap", "args_json": '{"x":1}'}], "none"),
])
def test_bad_tool_contracts_are_rejected(calls, choice):
    with pytest.raises(CLIProtocolError):
        CLIChatModel._message(envelope("answer", calls), [TOOL], choice)


@pytest.mark.asyncio
async def test_native_langchain_structured_output(monkeypatch):
    class Answer(BaseModel):
        passed: bool
    fake_inference(monkeypatch, cli_result(envelope("", [
        {"id": "structured", "name": "Answer", "args_json": '{"passed":true}'}])))
    result = await CLIChatModel().with_structured_output(Answer).ainvoke("check")
    assert isinstance(result, Answer) and result.passed


@pytest.mark.asyncio
async def test_stream_delivers_one_complete_message(monkeypatch):
    fake_inference(monkeypatch, cli_result(envelope("complete")))
    chunks = [c async for c in CLIChatModel().astream("hello")]
    assert "".join(c.content for c in chunks) == "complete"


@pytest.mark.parametrize("result", [
    ProcessResult(1, "private stdout", "secret token"),
    ProcessResult(0, "not json", "secret"),
    cli_result(envelope(), complete=False),
    ProcessResult(0, '{"type":"turn.failed"}', ""),
])
def test_exit_partial_and_malformed_are_not_success(result):
    with pytest.raises(CLIError) as error:
        decode_result("codex", result)
    assert "secret" not in str(error.value) and "private" not in str(error.value)


@pytest.mark.asyncio
async def test_serializes_calls_across_model_instances(monkeypatch):
    from callisto.llm_adapter import model
    monkeypatch.setattr(model, "command_for", lambda *args: ["MOCK_ONLY"])
    current = maximum = 0
    async def execute(*args, **kwargs):
        nonlocal current, maximum
        current += 1
        maximum = max(current, maximum)
        await asyncio.sleep(0.01)
        current -= 1
        return cli_result(envelope())
    monkeypatch.setattr(model, "run_process", execute)
    await asyncio.gather(*(CLIChatModel().ainvoke("hello") for _ in range(4)))
    assert maximum == 1


@pytest.mark.asyncio
async def test_fake_executable_end_to_end_transport(monkeypatch, tmp_path):
    from callisto.llm_adapter import model
    script = tmp_path / "fake_inference.py"
    script.write_text('''import json,sys
prompt=json.loads(sys.stdin.read().split("\\n",1)[1])
assert prompt["messages"][0]["content"][0]["text"] == "hello"
answer=json.dumps({"content":"fake contract response","tool_calls":[]})
print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":answer}}))
print(json.dumps({"type":"turn.completed"}))
''')
    monkeypatch.setattr(model, "command_for", lambda *args: [sys.executable, str(script)])
    result = await CLIChatModel().ainvoke("hello")
    assert result.content == "fake contract response"
    assert result.usage_metadata is None


@pytest.mark.asyncio
async def test_timeout_and_cancellation_remove_child_group(tmp_path):
    import os
    import psutil
    if os.name == "nt":
        pytest.skip("POSIX descendant-state assertion; Windows requires target-host validation")
    script = tmp_path / "fake_process.py"
    pid_path = tmp_path / "descendant.pid"
    script.write_text('''import subprocess,sys,time
child="import os,sys,time; open(sys.argv[1],'w').write(os.readlink('/proc/self')); time.sleep(90)"
p=subprocess.Popen([sys.executable,"-c",child,sys.argv[1]])
time.sleep(90)
''')
    with pytest.raises(TimeoutError):
        await run_process([sys.executable, str(script), str(pid_path)], stdin="", cwd=str(tmp_path), timeout=0.3)
    child = int(pid_path.read_text())
    assert not psutil.pid_exists(child) or psutil.Process(child).status() == psutil.STATUS_ZOMBIE
    pid_path.unlink()
    task = asyncio.create_task(run_process([sys.executable, str(script), str(pid_path)],
                               stdin="", cwd=str(tmp_path), timeout=90))
    for _ in range(100):
        if pid_path.exists():
            break
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    child = int(pid_path.read_text())
    assert not psutil.pid_exists(child) or psutil.Process(child).status() == psutil.STATUS_ZOMBIE


@pytest.mark.asyncio
async def test_bounded_output_and_redacted_launch_error(tmp_path):
    with pytest.raises(CLIError, match="size limit"):
        await run_process([sys.executable, "-c", "print('x'*10000)"], stdin="", cwd=str(tmp_path),
                          timeout=2, max_bytes=100)
    with pytest.raises(CLIError) as error:
        await run_process(["/missing/private-secret-executable"], stdin="", cwd=str(tmp_path), timeout=1)
    assert "private-secret" not in str(error.value)


def test_live_cli_is_forbidden_in_test_environment(tmp_path):
    with pytest.raises(CLIError, match="forbidden"):
        command_for("codex", None, tmp_path, [], tmp_path / "schema.json")


def test_auth_classification_uses_failed_inference_event_only():
    from callisto.llm_adapter.errors import CLIAuthenticationError
    data = json.dumps({"type": "error", "message": "401 Unauthorized"})
    with pytest.raises(CLIAuthenticationError):
        decode_result("codex", ProcessResult(1, data, ""))
    assert decode_result("codex", cli_result(envelope(), stderr="401 Unauthorized"))[0] == envelope()
