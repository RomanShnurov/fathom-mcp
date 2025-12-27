#!/usr/bin/env python3
"""
Test dependency management improvements.
"""

import os
import subprocess
import sys


def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n🔄 {description}")
    print(f"Command: {cmd}")

    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ Success")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
        else:
            print("❌ Failed")
            print(f"Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

    return True


def main():
    print("📦 Testing Dependency Management")
    print("=" * 40)

    # Check if uv.lock exists
    if not os.path.exists("uv.lock"):
        print("❌ uv.lock file not found!")
        return 1

    print("✅ uv.lock file exists")

    # Test frozen install
    if not run_command(
        "uv sync --frozen --no-dev", "Testing frozen dependency install (production)"
    ):
        return 1

    # Test with dev dependencies
    if not run_command(
        "uv sync --frozen --extra dev", "Testing frozen dependency install (with dev deps)"
    ):
        return 1

    # Check lock file is up to date
    if not run_command("uv lock --check", "Verifying lock file is up to date"):
        print("⚠️  Lock file might be outdated. Run 'uv lock' to update.")

    print("\n✅ Dependency tests passed!")
    print("\n💡 Benefits:")
    print("- Frozen installs ensure reproducible builds")
    print("- Lock file prevents dependency drift")
    print("- Faster installs in CI/CD")

    return 0


if __name__ == "__main__":
    sys.exit(main())
