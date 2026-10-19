"""Offline package smoke test in a fresh venv, outside the checkout.

Only Python/pip/Callisto help processes are launched, never AI-provider CLIs.
Dependency installation needs the package index; inference/device calls are forbidden.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile
import venv
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('wheel', type=Path)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--require-helper', action='store_true')
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for required in ('artemis/graph/graph.py', 'artemis/mcp/action_session.py',
                         'artemis/resources/config/artemis.jsonc', 'third_party/mobile_use/NOTICE',
                         'artemis_client/__init__.py'):
            assert required in names, required
        assert any(n.endswith('/share/callisto/skills/callisto/SKILL.md') for n in names)
        assert any(n.endswith('/share/callisto/helper/helper_manifest.json') for n in names)
        forbidden = ('showcase_ui', 'admin_console', 'mcp_server/', 'artemis/agents/flash/flash.py')
        assert not any(any(marker in name for marker in forbidden) for name in names)
        for module in ('adb_server', 'xml_search_server'):
            source = archive.read(f'artemis/mcp/{module}.py')
            assert b'External MCP entrypoints are disabled' in source
            assert b'mcp.run(' not in source
        bundled_apk = any(n.endswith('.apk') for n in names)
        if args.require_helper:
            assert bundled_apk, 'Helper APK expected in this distribution'
    environment = dict(os.environ, CALLISTO_FORBID_LIVE_CLI='1')
    environment.pop('PYTHONPATH', None)
    with tempfile.TemporaryDirectory(prefix='callisto-wheel-') as temp:
        root = Path(temp)
        target = root / 'venv'
        venv.EnvBuilder(with_pip=True).create(target)
        bindir = target / ('Scripts' if os.name == 'nt' else 'bin')
        python = bindir / ('python.exe' if os.name == 'nt' else 'python')
        cli = bindir / ('callisto.exe' if os.name == 'nt' else 'callisto')
        def run(command):
            subprocess.run([str(v) for v in command], cwd=root, env=environment, check=True)
        run([python, '-m', 'pip', 'install', wheel])
        run([python, '-m', 'pip', 'check'])
        for flags in (['--help'], ['run', '--help'], ['helper', '--help'], ['trace', '--help'], ['skill', '--help'],
                      ['setup', '--help'], ['setup', 'check', '--help'], ['setup', 'repair', '--help'], ['--version']):
            run([cli, *flags])
        skill_dir = root / 'external-user-skills'
        run([cli, 'skill', 'install', '--directory', skill_dir])
        run([cli, 'skill', 'update', '--directory', skill_dir])
        run([cli, 'skill', 'status', '--directory', skill_dir])
        if args.require_helper:
            run([cli, 'helper', 'bundle-status'])
        run([python, '-c', '''from artemis.config.llm import get_default_llm_config
from artemis.graph.graph import get_graph
from artemis.interfaces.cli.commands.run import execute_task
from artemis.interfaces.sdk.client import ArtemisClient
from artemis.resources import get_bundled_config_path
from artemis.runtime.helper_manager import load_bundled_helper
import artemis
from callisto.settings import effective_settings
from callisto.llm_adapter.image_policy import prepare_image
from callisto.setup import setup_report
from importlib.metadata import distribution
get_default_llm_config().validate_providers()
assert get_bundled_config_path('artemis.jsonc').is_file()
assert artemis.__version__ != '0+unknown'
assert effective_settings().image_policy == 'balanced'
dist = distribution('callisto-auto')
skill = next(p for p in dist.files if str(p).endswith('share/callisto/skills/callisto/SKILL.md'))
assert dist.locate_file(skill).is_file()
print('isolated Pro/config/skill imports OK; helper APK available:', load_bundled_helper() is not None)
'''])
    report = {'wheel': wheel.name, 'installed': True, 'pip_check': 'passed',
              'pro_import': 'passed', 'cli_help': 'passed', 'canonical_skill': 'included',
              'skill_install_update_status': 'passed', 'host_skill_recognition': 'not_run',
              'helper_manifest': 'included', 'helper_apk_bundled': bundled_apk,
              'live_cli': 'not_run', 'android': 'not_run', 'platform': os.name}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
