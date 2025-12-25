#!/usr/bin/env python3
"""
Interactive test script for contextfs server.
Tests all MCP tools by sending JSON-RPC requests via stdio.
"""

import asyncio
import json
import sys
from pathlib import Path


class MCPClient:
    """Simple MCP client for testing."""

    def __init__(self):
        self.process = None
        self.request_id = 0

    async def start_server(self, config_path: str):
        """Start the MCP server process."""
        print("🚀 Starting MCP server...")
        self.process = await asyncio.create_subprocess_exec(
            "uv",
            "run",
            "contextfs",
            "--config",
            config_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        print("✅ Server started\n")

    async def send_request(self, method: str, params: dict = None) -> dict:
        """Send JSON-RPC request to server."""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params or {},
        }

        # Send request
        request_json = json.dumps(request) + "\n"
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()

        # Read response
        response_line = await self.process.stdout.readline()
        if not response_line:
            raise Exception("Server closed connection")

        response = json.loads(response_line.decode())
        return response

    async def initialize(self):
        """Initialize MCP session."""
        print("🔌 Initializing MCP session...")
        response = await self.send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        )
        if "error" in response:
            raise Exception(f"Initialize failed: {response['error']}")
        print(f"✅ Session initialized: {response['result']['serverInfo']['name']}\n")

        # Send initialized notification
        notification = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        notification_json = json.dumps(notification) + "\n"
        self.process.stdin.write(notification_json.encode())
        await self.process.stdin.drain()

    async def list_tools(self) -> list:
        """Get list of available tools."""
        response = await self.send_request("tools/list")
        if "error" in response:
            raise Exception(f"List tools failed: {response['error']}")
        return response["result"]["tools"]

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Call a specific tool."""
        response = await self.send_request(
            "tools/call", {"name": tool_name, "arguments": arguments}
        )
        if "error" in response:
            return {"error": response["error"]}
        return response["result"]

    async def stop(self):
        """Stop the server process."""
        if self.process:
            self.process.terminate()
            await self.process.wait()
        print("\n🛑 Server stopped")


async def run_tests():
    """Run all test scenarios."""
    client = MCPClient()

    try:
        # Start server
        config_path = Path(__file__).parent / "config.yaml"
        await client.start_server(str(config_path))
        await asyncio.sleep(1)  # Give server time to start

        # Initialize session
        await client.initialize()

        # List available tools
        print("📋 Available tools:")
        tools = await client.list_tools()
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        print()

        # Test 1: List root collections
        print("=" * 60)
        print("TEST 1: List root collections")
        print("=" * 60)
        result = await client.call_tool("list_collections", {"path": ""})
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Root collections:")
            for content in result["content"]:
                data = json.loads(content["text"])
                print(f"\n📁 Collections: {', '.join(data.get('collections', []))}")
                print(f"📄 Documents: {len(data.get('documents', []))} files")
        print()

        # Test 2: List programming collection
        print("=" * 60)
        print("TEST 2: List 'programming' collection")
        print("=" * 60)
        result = await client.call_tool("list_collections", {"path": "programming"})
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Programming collection:")
            for content in result["content"]:
                data = json.loads(content["text"])
                for doc in data.get("documents", []):
                    print(f"  📄 {doc['name']} ({doc['size']} bytes)")
        print()

        # Test 3: Find documents
        print("=" * 60)
        print("TEST 3: Find documents with 'async'")
        print("=" * 60)
        result = await client.call_tool("find_document", {"query": "async", "limit": 10})
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Found documents:")
            for content in result["content"]:
                data = json.loads(content["text"])
                for doc in data.get("documents", []):
                    print(f"  📄 {doc['path']}")
        print()

        # Test 4: Search for "authentication"
        print("=" * 60)
        print("TEST 4: Search for 'authentication'")
        print("=" * 60)
        result = await client.call_tool(
            "search_documents",
            {"query": "authentication", "scope": {"type": "global"}},
        )
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Search results:")
            for content in result["content"]:
                data = json.loads(content["text"])
                print(f"\n📊 Total matches: {data['total_matches']}")
                print(f"🔍 Query: {data['query']}")
                for match in data.get("matches", [])[:3]:  # Show first 3
                    print(f"\n  📄 {match['document']}")
                    print(f"     Line {match['line_number']}: {match['line'][:80]}...")
        print()

        # Test 5: Boolean search (AND operator)
        print("=" * 60)
        print("TEST 5: Boolean search 'async await'")
        print("=" * 60)
        result = await client.call_tool(
            "search_documents", {"query": "async await", "scope": {"type": "global"}}
        )
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Search results:")
            for content in result["content"]:
                data = json.loads(content["text"])
                print(f"📊 Matches: {data['total_matches']}")
                for match in data.get("matches", [])[:2]:
                    print(f"  📄 {match['document']} (line {match['line_number']})")
        print()

        # Test 6: Read a document
        print("=" * 60)
        print("TEST 6: Read 'programming/python-basics.md'")
        print("=" * 60)
        result = await client.call_tool(
            "read_document", {"path": "programming/python-basics.md"}
        )
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Document content:")
            for content in result["content"]:
                text = content["text"]
                # Show first 500 chars
                print(f"{text[:500]}...")
        print()

        # Test 7: Parallel search
        print("=" * 60)
        print("TEST 7: Parallel search (multiple queries)")
        print("=" * 60)
        result = await client.call_tool(
            "search_multiple",
            {
                "queries": ["python", "async", "authentication"],
                "scope": {"type": "global"},
            },
        )
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Parallel search results:")
            for content in result["content"]:
                data = json.loads(content["text"])
                for query_result in data.get("results", []):
                    print(
                        f"\n  🔍 '{query_result['query']}': {query_result['total_matches']} matches"
                    )
        print()

        # Test 8: Get document info
        print("=" * 60)
        print("TEST 8: Get document metadata")
        print("=" * 60)
        result = await client.call_tool(
            "get_document_info", {"path": "programming/async-patterns.md"}
        )
        if "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print("✅ Document info:")
            for content in result["content"]:
                data = json.loads(content["text"])
                print(f"  📄 Path: {data['path']}")
                print(f"  📏 Size: {data['size']} bytes")
                print(f"  📝 Format: {data['format']}")
                print(f"  📅 Modified: {data['modified']}")
        print()

        print("=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()

    finally:
        await client.stop()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║         ContextFS - Test Suite          ║
╚══════════════════════════════════════════════════════════╝
""")
    asyncio.run(run_tests())
