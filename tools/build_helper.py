"""Build the original Java Helper with Android SDK tools on Linux or Windows.

No Gradle downloads, shell interpolation, AI CLI, ADB or device operations.
The existing debug keystore preserves debug upgrade identity. These artifacts
are development builds, not a production-signed release.
"""

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages/artemis-accessibility-helper"


def build(sdk: Path, build_tools="35.0.0", platform="android-35"):
    sdk = sdk.resolve()
    tools = sdk / "build-tools" / build_tools
    android_jar = sdk / "platforms" / platform / "android.jar"
    suffix = ".exe" if os.name == "nt" else ""
    java_home = os.environ.get("JAVA_HOME")

    def java_tool(name):
        path = str(Path(java_home) / "bin" / (name + suffix)) if java_home else shutil.which(name)
        if not path or not Path(path).is_file():
            raise ValueError(f"Missing {name}; configure JAVA_HOME or PATH")
        return path

    java, javac = java_tool("java"), java_tool("javac")
    required = [android_jar, tools / ("aapt2" + suffix), tools / ("zipalign" + suffix),
                tools / "lib/d8.jar", tools / "lib/apksigner.jar", PACKAGE / "debug.keystore"]
    for path in required:
        if not path.is_file():
            raise ValueError(f"Missing build prerequisite: {path}")
    gradle = (PACKAGE / "app/build.gradle.kts").read_text(encoding="utf-8")
    version_code = int(re.search(r"versionCode\s*=\s*(\d+)", gradle).group(1))
    version_name = re.search(r'versionName\s*=\s*"([^"]+)"', gradle).group(1)
    work = PACKAGE / "build/callisto"
    if work.exists():
        shutil.rmtree(work)
    for name in ("gen", "obj", "dex"):
        (work / name).mkdir(parents=True)

    def run(args):
        subprocess.run([str(arg) for arg in args], cwd=PACKAGE, check=True, timeout=180)

    resources = work / "res.zip"
    unsigned = work / "unsigned.apk"
    aligned = work / "aligned.apk"
    final = work / "ArtemisAccessibilityHelper.apk"
    run([tools / ("aapt2" + suffix), "compile", "--dir", PACKAGE / "app/src/main/res", "-o", resources])
    run([tools / ("aapt2" + suffix), "link", "-I", android_jar,
         "--manifest", PACKAGE / "app/src/main/AndroidManifest.xml",
         "--min-sdk-version", "24", "--target-sdk-version", "35",
         "--version-code", version_code, "--version-name", version_name,
         "--java", work / "gen", "-o", unsigned, resources])
    sources = sorted((PACKAGE / "app/src/main/java").rglob("*.java")) + sorted((work / "gen").rglob("*.java"))
    # javac argfiles handle spaces and avoid the Windows command-length limit.
    source_list = work / "sources.txt"
    source_list.write_text("\n".join('"' + p.as_posix() + '"' for p in sources), encoding="utf-8")
    run([javac, "-encoding", "UTF-8", "-source", "8", "-target", "8", "-Xlint:-options",
         "-cp", android_jar, "-d", work / "obj", "@" + str(source_list)])
    classes = work / "classes.jar"
    with zipfile.ZipFile(classes, "w") as archive:
        for path in sorted((work / "obj").rglob("*.class")):
            archive.write(path, path.relative_to(work / "obj").as_posix())
    run([java, "-cp", tools / "lib/d8.jar", "com.android.tools.r8.D8", "--lib", android_jar,
         "--output", work / "dex", "--min-api", "24", classes])
    with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(work / "dex/classes.dex", "classes.dex")
    run([tools / ("zipalign" + suffix), "-f", "-p", "4", unsigned, aligned])
    run([java, "-jar", tools / "lib/apksigner.jar", "sign", "--ks", PACKAGE / "debug.keystore",
         "--ks-pass", "pass:android", "--key-pass", "pass:android", "--ks-key-alias", "androiddebugkey",
         "--out", final, aligned])
    run([java, "-jar", tools / "lib/apksigner.jar", "verify", "--verbose", final])
    data = {"package": "com.artemis.helper", "version_code": version_code, "version_name": version_name,
            "sha256": hashlib.sha256(final.read_bytes()).hexdigest(),
            "built_at": datetime.datetime.now(datetime.UTC).replace(microsecond=0).isoformat()}
    shutil.copyfile(final, PACKAGE / final.name)
    (PACKAGE / "helper_manifest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, default=os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT"))
    parser.add_argument("--build-tools", default="35.0.0")
    parser.add_argument("--platform", default="android-35")
    args = parser.parse_args()
    if not args.sdk:
        parser.error("Set ANDROID_HOME or pass --sdk with Android SDK Platform 35 and Build Tools 35.0.0")
    try:
        build(args.sdk, args.build_tools, args.platform)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Helper build failed: {error}\n")


if __name__ == "__main__":
    main()
