"""CLI-only regression gates; never execute an installed AI provider."""
import ast
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from callisto.llm_adapter.errors import CLIError, CLIProtocolError, UnsupportedCapability
from callisto.llm_adapter.process import ProcessResult, run_process
from callisto.llm_adapter.providers import command_for, decode_result

ROOT = Path(__file__).resolve().parents[2]


def test_active_sources_only_import_google_data_types():
    for base in ('artemis', 'callisto', 'third_party'):
        for path in (ROOT / base).rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                if isinstance(node, ast.Import):
                    assert not any(a.name.startswith(('google', 'openai', 'anthropic', 'langchain_google', 'langchain_openai')) for a in node.names), path
                elif isinstance(node, ast.ImportFrom) and node.module:
                    if node.module.startswith('google'):
                        assert node.module == 'google.genai' and all(a.name == 'types' for a in node.names), path


@pytest.mark.parametrize('provider', ['google', 'vertexai', 'openai', 'anthropic', 'openrouter', 'xai', 'ollama', 'vllm', 'custom'])
def test_every_direct_provider_is_rejected(provider):
    from artemis.llm.router import ModelEndpoint, ModelFactory
    with pytest.raises(ValueError, match='direct AI API'):
        ModelFactory.create_model(ModelEndpoint(provider=provider, model_name='legacy'))


def test_legacy_environment_keys_neither_load_nor_persist(monkeypatch, tmp_path):
    from artemis.config.settings import Settings
    from third_party.mobile_use.config.llm import validate_vertex_ai_credentials
    for name in ('GOOGLE_API_KEY', 'GEMINI_API_KEY', 'OPENAI_API_KEY', 'OCR_API_KEY'):
        monkeypatch.setenv(name, 'fake-do-not-collect')
    monkeypatch.chdir(tmp_path)
    config = Settings()
    assert config.GOOGLE_API_KEY is None
    assert config.get_api_key('google') is None
    assert 'fake-do-not-collect' not in config.model_dump_json()
    with pytest.raises(UnsupportedCapability):
        config.set_api_key('google', 'never-persist', persist_to_env=True)
    with pytest.raises(UnsupportedCapability):
        validate_vertex_ai_credentials()
    assert not (tmp_path / '.env').exists()
    assert os.environ['GOOGLE_API_KEY'] == 'fake-do-not-collect'


@pytest.mark.parametrize('key', [None, 'legacy-key-present'])
def test_old_keys_cannot_select_native_engines(monkeypatch, key):
    from artemis.agents.explorer.explorer import Explorer
    from artemis.agents.video_analyzer.video_analyzer import VideoAnalyzer
    if key:
        monkeypatch.setenv('GOOGLE_API_KEY', key)
    else:
        monkeypatch.delenv('GOOGLE_API_KEY', raising=False)
    ctx = SimpleNamespace(llm_config=SimpleNamespace(
        explorer=SimpleNamespace(model='gemini-3.8-flash'),
        utils=SimpleNamespace(video_analyzer=SimpleNamespace(model='gemini-3.8-flash'))),
        agent_config=None, data_engine=None)
    with patch('callisto.llm_adapter.native.Client', side_effect=AssertionError('no client creation')):
        assert Explorer(ctx).use_native_gemini is False
        video = VideoAnalyzer(ctx)
    assert video.use_native_gemini is False and video.video_processing == 'static'


def test_codex_command_is_built_without_executing_provider(monkeypatch, tmp_path):
    monkeypatch.delenv('CALLISTO_FORBID_LIVE_CLI')
    monkeypatch.setattr('callisto.llm_adapter.providers.shutil.which', lambda _: 'fake-codex.exe')
    args = command_for('codex', 'gpt-6.1-sol', tmp_path, ['first.png', 'second.png'], tmp_path / 'schema.json', 'high')
    assert args[:2] == ['fake-codex.exe', 'exec'] and args[-1] == '-'
    for option in ('--ignore-rules', '--ephemeral', '--json', '--output-schema'):
        assert option in args
    assert args[args.index('--sandbox') + 1] == 'read-only'
    assert args[args.index('--image') + 1] == 'first.png'
    assert 'web_search="disabled"' in args
    assert '--ignore-user-config' not in args
    assert "--model" not in args and not any("model_reasoning_effort" in item for item in args)
    disabled = [args[i+1] for i, v in enumerate(args) if v == '--disable']
    assert {'shell_tool', 'apps', 'plugins', 'hooks', 'multi_agent'} <= set(disabled)


@pytest.mark.parametrize('item_type', ['command_execution', 'file_change', 'mcp_tool_call', 'web_search', 'collab_tool_call'])
def test_provider_side_effect_events_fail_even_after_valid_answer(item_type):
    events = [dict(type='item.completed', item=dict(type=item_type)),
        dict(type='item.completed', item=dict(type='agent_message', text='{"content":"ok","tool_calls":[]}')),
        dict(type='turn.completed')]
    with pytest.raises(CLIProtocolError, match='ARTEMIS'):
        decode_result('codex', ProcessResult(0, '\n'.join(map(json.dumps, events)), ''))


def test_unknown_and_incomplete_claude_results_cannot_succeed():
    with pytest.raises(CLIProtocolError):
        decode_result('gemini', ProcessResult(0, '{}', ''))
    with pytest.raises(CLIError):
        decode_result('claude', ProcessResult(0, '{"type":"result","subtype":"error","is_error":true}', ''))


@pytest.mark.asyncio
async def test_cli_ocr_keeps_text_and_pixel_polygons(monkeypatch):
    from artemis.utils.ocr_api import perform_ocr
    from callisto.ocr import OCRResult
    monkeypatch.setenv('CALLISTO_OCR', '1')
    expected = OCRResult(regions=[{'text': 'Battery', 'position': [{'x': 2, 'y': 3}, {'x': 20, 'y': 30}]}])
    fake = MagicMock()
    fake.with_structured_output.return_value.ainvoke = AsyncMock(return_value=expected)
    from io import BytesIO
    import base64
    from PIL import Image
    output = BytesIO()
    Image.new('RGB', (100, 100)).save(output, format='PNG')
    screenshot = base64.b64encode(output.getvalue()).decode()
    with patch('callisto.llm_adapter.model.configured_model', return_value=fake):
        assert await perform_ocr(screenshot) == [region.model_dump() for region in expected.regions]
        fake.with_structured_output.return_value.ainvoke.side_effect = UnsupportedCapability('image unavailable')
        with pytest.raises(UnsupportedCapability):
            await perform_ocr(screenshot)


def test_canonical_skill_pointer_and_bundled_configuration():
    from artemis import resources
    from importlib.metadata import version
    import artemis
    pointer = ROOT / '.agents/skills/callisto/SKILL.md'
    assert (pointer.parent / '../../../skills/callisto/SKILL.md').resolve() == ROOT / 'skills/callisto/SKILL.md'
    assert '../../../skills/callisto/SKILL.md' in pointer.read_text()
    assert artemis.__version__ == version('callisto-auto')
    bundled = resources.get_bundled_config_path('artemis.jsonc')
    assert bundled.read_bytes() == (ROOT / 'config/artemis.jsonc').read_bytes()
    assert resources.get_bundled_config_path('missing.jsonc') is None
    assert not hasattr(resources, 'get_bundled_showcase_dist')


@pytest.mark.asyncio
@pytest.mark.skipif(os.name != 'nt', reason='Windows child-tree contract runs in Windows CI')
@pytest.mark.parametrize('cancel', [False, True])
async def test_windows_timeout_and_cancel_terminate_descendants(tmp_path, cancel):
    import asyncio
    import sys
    import psutil
    script = tmp_path / 'fake_tree.py'
    pid_file = tmp_path / 'child.pid'
    script.write_text("import subprocess,sys,time\np=subprocess.Popen([sys.executable,'-c','import time; time.sleep(90)'])\nopen(sys.argv[1],'w').write(str(p.pid))\ntime.sleep(90)\n")
    task = asyncio.create_task(run_process([sys.executable, str(script), str(pid_file)], stdin='', cwd=str(tmp_path), timeout=90 if cancel else 3))
    for _ in range(200):
        if pid_file.exists() and pid_file.read_text():
            break
        await asyncio.sleep(0.01)
    assert pid_file.exists()
    pid = int(pid_file.read_text())
    if cancel:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel else TimeoutError):
        await task
    assert not psutil.pid_exists(pid)


@pytest.mark.parametrize('module', ['adb_server', 'xml_search_server'])
def test_external_mcp_modules_fail_without_starting_transport(module):
    import runpy
    with patch('mcp.server.fastmcp.FastMCP.run', side_effect=AssertionError('external server started')):
        with pytest.raises(SystemExit, match='External MCP entrypoints are disabled'):
            runpy.run_module('artemis.mcp.' + module, run_name='__main__')
