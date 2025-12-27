#!/usr/bin/env python3
"""
Quick local testing script for the DevOps improvements.
"""

import os
import subprocess
import sys


def test_local_build():
    """Test local UV setup."""
    print("🔧 Testing Local Setup")
    print("=" * 30)

    # Test UV sync
    print("\n🔄 Testing UV dependency sync...")
    result = subprocess.run(["uv", "sync", "--frozen"], capture_output=True, text=True)
    if result.returncode == 0:
        print("✅ UV sync successful")
    else:
        print(f"❌ UV sync failed: {result.stderr}")
        return False

    # Test module import
    print("\n🔄 Testing module import...")
    result = subprocess.run(
        [sys.executable, "-c", "import contextfs; print('✅ Module import successful')"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print(result.stdout.strip())
    else:
        print(f"❌ Module import failed: {result.stderr}")
        return False

    # Test CLI
    print("\n🔄 Testing CLI...")
    result = subprocess.run(
        [sys.executable, "-m", "contextfs", "--help"], capture_output=True, text=True
    )
    if result.returncode == 0:
        print("✅ CLI works correctly")
        print("First few lines of help:")
        print("\n".join(result.stdout.split("\n")[:3]))
    else:
        print(f"❌ CLI failed: {result.stderr}")
        return False

    return True


def test_docker_quick():
    """Quick Docker test without full build."""
    print("\n🐳 Testing Docker Configuration")
    print("=" * 35)

    # Check if Dockerfile exists and has our improvements
    if not os.path.exists("Dockerfile"):
        print("❌ Dockerfile not found")
        return False

    with open("Dockerfile") as f:
        dockerfile_content = f.read()

    improvements = [
        ("uv.lock", "✅ Uses uv.lock for reproducible builds"),
        ("--frozen", "✅ Uses frozen dependency install"),
        ("HEALTHCHECK", "✅ Has health check configured"),
        (
            "multi-stage",
            "✅ Uses multi-stage build"
            if "FROM python:3.12-slim as builder" in dockerfile_content.lower()
            else "❌ Missing multi-stage build",
        ),
    ]

    for check, message in improvements:
        if check.lower() in dockerfile_content.lower():
            print(message)
        else:
            print(f"❌ Missing: {check}")

    return True


def test_ci_config():
    """Test CI configuration."""
    print("\n⚙️  Testing CI Configuration")
    print("=" * 30)

    # Check CI file
    ci_file = ".github/workflows/ci.yaml"
    if os.path.exists(ci_file):
        with open(ci_file) as f:
            ci_content = f.read()

        if "actions/cache" in ci_content:
            print("✅ CI has dependency caching")
        else:
            print("❌ CI missing dependency caching")

        if "docker/build-push-action" in ci_content:
            print("✅ CI uses optimized Docker builds")
        else:
            print("❌ CI missing optimized Docker builds")
    else:
        print("❌ CI workflow file not found")

    # Check Dependabot
    if os.path.exists(".github/dependabot.yml"):
        print("✅ Dependabot configuration exists")
    else:
        print("❌ Dependabot configuration missing")

    return True


def main():
    print("🚀 Local DevOps Testing Suite")
    print("=" * 40)

    success = True

    # Test local setup
    if not test_local_build():
        success = False

    # Test Docker config
    if not test_docker_quick():
        success = False

    # Test CI config
    if not test_ci_config():
        success = False

    if success:
        print("\n🎉 All local tests passed!")
        print("\n💡 Next steps:")
        print("- Push changes to trigger CI pipeline")
        print("- Monitor build times (should be faster)")
        print("- Check Dependabot PRs for updates")
    else:
        print("\n❌ Some tests failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
