"""Keep user-facing Callisto branding separate from preserved ARTEMIS identifiers."""

from pathlib import Path

from typer.testing import CliRunner

from artemis.runtime.helper_manager import (
    DISPLAY_NAME,
    MANUAL_ENABLE_PATH,
    PACKAGE_NAME,
    SERVICE_NAME,
)
from callisto.cli import app


ROOT = Path(__file__).resolve().parents[2]


def test_cli_helper_help_and_bundle_status_show_callisto():
    runner = CliRunner()
    help_result = runner.invoke(app, ["helper", "--help"])
    assert help_result.exit_code == 0
    assert "Callisto" in help_result.output
    assert "Artemis Accessibility Helper" not in help_result.output

    bundle_status = runner.invoke(app, ["helper", "bundle-status"])
    assert bundle_status.exit_code in (0, 1)  # APK is optional in source checkouts.
    assert '"display_name": "Callisto Accessibility Helper"' in bundle_status.output


def test_helper_branding_preserves_existing_android_package_identity():
    assert DISPLAY_NAME == "Callisto Accessibility Helper"
    assert DISPLAY_NAME in MANUAL_ENABLE_PATH
    assert PACKAGE_NAME == "com.artemis.helper"
    assert SERVICE_NAME == "com.artemis.helper/.ArtemisAccessibilityService"


def test_skill_transition_and_android_app_user_facing_labels():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "CLI 스킬" in readme
    assert "기존 Pro 자동화 엔진을 유지" in readme

    resources = (ROOT / "packages/artemis-accessibility-helper/app/src/main/res/values/strings.xml").read_text(encoding="utf-8")
    assert "Callisto Accessibility Helper" in resources
    java = (ROOT / "packages/artemis-accessibility-helper/app/src/main/java/com/artemis/helper/ArtemisAccessibilityService.java").read_text(encoding="utf-8")
    assert 'setContentTitle("Callisto test helper is running")' in java
    assert "callisto helper uninstall" in java
