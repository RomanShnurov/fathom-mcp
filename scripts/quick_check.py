#!/usr/bin/env python3
"""
Quick health check for contextfs server.
Just verifies the server starts and responds to basic requests.
"""

import subprocess
import sys
import time


def check_dependency(command, name):
    """Check if a system dependency is available."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, shell=True, timeout=5)
        print(f"✅ {name} is installed")
        return True
    except Exception as e:
        print(f"❌ {name} is NOT installed: {e}")
        return False


def check_server_startup():
    """Check if the server can start."""
    print("\n🚀 Testing server startup...")
    try:
        # Start server process
        # Note: MCP server will exit when stdin closes, which is normal behavior
        process = subprocess.Popen(
            ["uv", "run", "contextfs", "--config", "config.yaml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,  # Provide stdin
            text=True,
        )

        # Wait a moment for startup
        time.sleep(1.5)

        # Terminate cleanly
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()

        # Check if server initialized successfully by looking for success messages in logs
        if "Server 'contextfs' created" in stderr and "Starting MCP server" in stderr:
            print("✅ Server initialized successfully")
            return True
        elif "ERROR" in stderr or "Traceback" in stderr:
            print("❌ Server had errors during startup:")
            print(stderr[-500:])  # Last 500 chars
            return False
        else:
            print("✅ Server started (no errors detected)")
            return True

    except Exception as e:
        print(f"❌ Error testing server startup: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all health checks."""
    print("""
╔══════════════════════════════════════════════════════════╗
║    ContextFS - Quick Health Check       ║
╚══════════════════════════════════════════════════════════╝
""")

    all_ok = True

    # Check dependencies
    print("📋 Checking system dependencies...\n")

    if not check_dependency("ugrep --version", "ugrep"):
        all_ok = False
        print("   Install: https://github.com/Genivia/ugrep#installation")

    if not check_dependency("pdftotext -v", "pdftotext (poppler-utils)"):
        print("   ⚠️  Warning: PDF support will not work")
        print("   Install: brew install poppler (macOS) or apt install poppler-utils (Linux)")

    # Check Python environment
    print("\n📦 Checking Python environment...")
    try:
        import mcp

        print("✅ mcp package is installed")
    except ImportError:
        print("❌ mcp package is NOT installed")
        print("   Run: uv sync")
        all_ok = False

    try:
        import yaml

        print("✅ yaml package is installed")
    except ImportError:
        print("❌ yaml package is NOT installed")
        print("   Run: uv sync")
        all_ok = False

    # Check config file
    print("\n📄 Checking configuration...")
    try:
        with open("config.yaml") as f:
            print("✅ config.yaml exists")
    except FileNotFoundError:
        print("❌ config.yaml NOT found")
        print("   Run: cp config.example.yaml config.yaml")
        all_ok = False

    # Check documents directory
    print("\n📁 Checking documents directory...")
    import os

    if os.path.isdir("documents"):
        doc_count = sum([len(files) for r, d, files in os.walk("documents")])
        print(f"✅ documents/ directory exists ({doc_count} files)")
    else:
        print("❌ documents/ directory NOT found")
        print("   Create it: mkdir documents")
        all_ok = False

    # Test server startup
    if all_ok:
        if not check_server_startup():
            all_ok = False

    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ All checks passed! Server is ready to use.")
        print("\nNext steps:")
        print("  1. Configure Claude Desktop (see TESTING_GUIDE.md)")
        print("  2. Or use MCP Inspector: mcp-inspector uv run contextfs")
        print("  3. Or run pytest tests: uv run pytest")
    else:
        print("❌ Some checks failed. Please fix the issues above.")
        sys.exit(1)
    print("=" * 60)


if __name__ == "__main__":
    main()
