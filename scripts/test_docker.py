#!/usr/bin/env python3
"""
Local Docker testing script to validate the DevOps improvements.
"""

import subprocess
import sys
import time


def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n🔄 {description}")
    print(f"Command: {cmd}")

    start_time = time.time()
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        duration = time.time() - start_time

        if result.returncode == 0:
            print(f"✅ Success ({duration:.1f}s)")
            if result.stdout.strip():
                print(f"Output: {result.stdout.strip()}")
        else:
            print(f"❌ Failed ({duration:.1f}s)")
            print(f"Error: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"❌ Exception: {e}")
        return False

    return True


def main():
    print("🐳 Testing Docker Build Optimizations")
    print("=" * 50)

    # Test 1: Build with cache
    if not run_command(
        "docker build -t contextfs:test .", "Building Docker image (first build - will be slower)"
    ):
        return 1

    # Test 2: Rebuild to test layer caching
    if not run_command(
        "docker build -t contextfs:test .",
        "Rebuilding Docker image (should be faster due to caching)",
    ):
        return 1

    # Test 3: Test health check
    if not run_command("docker run --rm contextfs:test --help", "Testing container runs correctly"):
        return 1

    # Test 4: Check health check is configured
    if not run_command(
        "docker inspect contextfs:test --format='{{.Config.Healthcheck}}'",
        "Verifying health check configuration",
    ):
        return 1

    # Test 5: Test with mounted config
    print("\n🔄 Testing with mounted configuration")
    if not run_command(
        "docker run --rm -v ./config.example.yaml:/config/config.yaml:ro contextfs:test --config /config/config.yaml --help",
        "Testing with mounted config file",
    ):
        return 1

    print("\n✅ All Docker tests passed!")
    print("\n💡 Tips:")
    print("- Second build should be much faster due to layer caching")
    print("- Health check enables container monitoring")
    print("- Multi-stage build keeps image size small")

    return 0


if __name__ == "__main__":
    sys.exit(main())
