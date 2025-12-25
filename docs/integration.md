# Integration Guide

How to integrate contextfs with various MCP clients and applications.

---

## Claude Desktop

The most common integration is with Claude Desktop, Anthropic's official desktop application.

### Configuration Location

The Claude Desktop configuration file is located at:

**macOS:**
```
~/Library/Application Support/Claude/claude_desktop_config.json
```

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

### Basic Setup

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "contextfs",
      "args": ["--root", "/path/to/your/documents"]
    }
  }
}
```

### Using uv (Development)

If you're running from source with uv:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/contextfs",
        "run",
        "contextfs",
        "--root",
        "/path/to/documents"
      ]
    }
  }
}
```

### Using a Config File

Point to a configuration file instead of passing CLI arguments:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "contextfs",
      "args": ["--config", "/path/to/config.yaml"]
    }
  }
}
```

### Multiple Knowledge Bases

You can configure multiple knowledge bases with different scopes:

```json
{
  "mcpServers": {
    "work-docs": {
      "command": "contextfs",
      "args": ["--root", "~/Documents/Work"]
    },
    "personal-notes": {
      "command": "contextfs",
      "args": ["--root", "~/Documents/Personal"]
    },
    "research": {
      "command": "contextfs",
      "args": ["--root", "~/Research/Papers"]
    }
  }
}
```

### Environment Variables

Set environment variables for configuration:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "contextfs",
      "args": ["--root", "/path/to/documents"],
      "env": {
        "CFS_SEARCH__MAX_RESULTS": "100",
        "CFS_SEARCH__CONTEXT_LINES": "10",
        "CFS_SECURITY__FILTER_MODE": "whitelist"
      }
    }
  }
}
```

### Restart Claude Desktop

After modifying the configuration:

1. Save `claude_desktop_config.json`
2. Quit Claude Desktop completely
3. Restart Claude Desktop
4. The server should now be available in conversations

### Verify Installation

In Claude Desktop, try:
```
Can you list my document collections?
```

Claude should use the `list_collections` tool to show your document structure.

---

## Claude Code

Claude Code (CLI) can also use MCP servers.

### Installation

```bash
# Install Claude Code CLI
npm install -g @anthropic/claude-code

# Or use npx
npx @anthropic/claude-code
```

### Configuration

Claude Code uses the same configuration as Claude Desktop. Follow the Claude Desktop setup above.

### Usage

```bash
# Start Claude Code
claude-code

# Ask questions about your documents
> Search my documents for authentication examples
> What does the API guide say about rate limiting?
> Summarize the tutorial.pdf file
```

---

## Custom Python Client

You can build custom MCP clients in Python using the `mcp` library.

### Installation

```bash
pip install mcp
```

### Basic Client

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="contextfs",
        args=["--root", "./documents"],
        env=None
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()

            # List tools
            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools])

            # Call a tool
            result = await session.call_tool(
                "list_collections",
                arguments={"path": ""}
            )
            print("Collections:", result)

            # Search documents
            search_result = await session.call_tool(
                "search_documents",
                arguments={
                    "query": "authentication",
                    "scope": {"type": "global"}
                }
            )
            print("Search results:", search_result)

if __name__ == "__main__":
    asyncio.run(main())
```

### Advanced Client with Error Handling

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def search_knowledge(query: str, scope_path: str = ""):
    """Search the knowledge base and return results."""
    server_params = StdioServerParameters(
        command="contextfs",
        args=["--root", "./documents"]
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                scope = {"type": "global"}
                if scope_path:
                    scope = {"type": "collection", "path": scope_path}

                result = await session.call_tool(
                    "search_documents",
                    arguments={
                        "query": query,
                        "scope": scope,
                        "max_results": 10
                    }
                )

                return result

    except Exception as e:
        print(f"Error: {e}")
        return None

async def main():
    # Search for content
    results = await search_knowledge("async patterns", "programming/python")

    if results:
        print(f"Found {results.get('total_matches', 0)} matches")
        for match in results.get('matches', []):
            print(f"\n{match['document']}:{match['line']}")
            print(f"  {match['text']}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## Docker Integration

Run the MCP server in a Docker container.

### Basic Docker Run

```bash
docker run -i \
  -v /path/to/documents:/knowledge:ro \
  contextfs
```

### Docker Compose

Create `docker-compose.yaml`:

```yaml
version: "3.8"

services:
  contextfs:
    image: contextfs:latest
    stdin_open: true
    tty: true
    volumes:
      - ./documents:/knowledge:ro
      - ./config.yaml:/config/config.yaml:ro
```

Run:
```bash
docker-compose up
```

### Claude Desktop with Docker

Configure Claude Desktop to use the Docker container:

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v",
        "/path/to/documents:/knowledge:ro",
        "contextfs"
      ]
    }
  }
}
```

---

## REST API Wrapper (Optional)

You can wrap the MCP server with a REST API for HTTP access.

### Using FastAPI

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio

app = FastAPI()

class SearchRequest(BaseModel):
    query: str
    collection: str | None = None
    max_results: int = 20

async def call_mcp_tool(tool_name: str, arguments: dict):
    """Call an MCP tool and return results."""
    server_params = StdioServerParameters(
        command="contextfs",
        args=["--root", "./documents"]
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments=arguments)

@app.post("/search")
async def search(request: SearchRequest):
    """Search documents via REST API."""
    scope = {"type": "global"}
    if request.collection:
        scope = {"type": "collection", "path": request.collection}

    try:
        result = await call_mcp_tool(
            "search_documents",
            {
                "query": request.query,
                "scope": scope,
                "max_results": request.max_results
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/collections")
async def list_collections(path: str = ""):
    """List collections via REST API."""
    try:
        result = await call_mcp_tool(
            "list_collections",
            {"path": path}
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run with: uvicorn rest_wrapper:app --reload
```

---

## Cloud Storage Integration

Since the MCP server only reads local files, you need to sync cloud documents locally first.

### Option 1: rclone mount (Recommended)

Mount cloud storage as a local directory:

```bash
# Mount Google Drive
rclone mount gdrive:Knowledge /data/knowledge --read-only --vfs-cache-mode full --daemon

# Configure MCP server to use mount point
contextfs --root /data/knowledge
```

**Claude Desktop config:**
```json
{
  "mcpServers": {
    "knowledge": {
      "command": "contextfs",
      "args": ["--root", "/data/knowledge"]
    }
  }
}
```

### Option 2: Cloud Desktop Clients

Use official sync clients (Google Drive Desktop, Dropbox, OneDrive):

```json
{
  "mcpServers": {
    "knowledge": {
      "command": "contextfs",
      "args": ["--root", "~/Google Drive/Knowledge"]
    }
  }
}
```

### Option 3: Scheduled Sync

Set up periodic sync with cron:

```bash
# Add to crontab: sync every 30 minutes
*/30 * * * * rclone sync gdrive:Knowledge /data/knowledge --log-file=/var/log/rclone.log
```

Then point the MCP server at the synced directory.

See [cloud-sync-guide.md](cloud-sync-guide.md) for detailed setup instructions.

---

## Systemd Service (Linux)

Run the MCP server as a systemd service.

### Create Service File

`/etc/systemd/system/contextfs.service`:

```ini
[Unit]
Description=File Knowledge MCP Server
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser
ExecStart=/usr/local/bin/contextfs --root /data/knowledge
Restart=on-failure
RestartSec=10

# Environment variables
Environment="CFS_SEARCH__MAX_RESULTS=100"
Environment="CFS_SECURITY__FILTER_MODE=whitelist"

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Enable and Start

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable contextfs

# Start service
sudo systemctl start contextfs

# Check status
sudo systemctl status contextfs

# View logs
journalctl -u contextfs -f
```

---

## Environment-Specific Configurations

### Development

```yaml
# config.dev.yaml
knowledge:
  root: "./test_docs"

server:
  log_level: "DEBUG"

search:
  max_results: 10

security:
  filter_mode: "whitelist"
```

Run:
```bash
contextfs --config config.dev.yaml
```

### Production

```yaml
# config.prod.yaml
knowledge:
  root: "/data/knowledge"

server:
  log_level: "WARNING"

search:
  max_results: 100
  timeout_seconds: 60

limits:
  max_concurrent_searches: 8

security:
  filter_mode: "whitelist"
  filter_timeout: 30
  allow_symlinks: false

exclude:
  patterns:
    - ".git/*"
    - "*.bak"
    - "*.tmp"
    - "_archive/*"
```

---

## Monitoring and Logging

### Logging Levels

Set via config or environment:

```yaml
server:
  log_level: "INFO"  # DEBUG | INFO | WARNING | ERROR
```

Or:
```bash
export CFS_SERVER__LOG_LEVEL=DEBUG
contextfs --root ./documents
```

### Log Output

Logs go to stderr in structured format:

```
2024-01-15T10:30:00.123Z [INFO] Server initialized with root: /data/knowledge
2024-01-15T10:30:05.456Z [DEBUG] Search query: authentication, scope: global
2024-01-15T10:30:05.789Z [INFO] Search completed: 12 matches in 333ms
```

### Health Checks

For monitoring in production:

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def health_check():
    """Check if MCP server is responding."""
    try:
        server_params = StdioServerParameters(
            command="contextfs",
            args=["--root", "./documents"]
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                # Try a simple operation
                await session.call_tool("list_collections", arguments={"path": ""})
                return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

# Run periodically
asyncio.run(health_check())
```

---

## Troubleshooting

### Server Not Appearing in Claude Desktop

1. Check configuration file syntax (valid JSON)
2. Verify command path: `which contextfs`
3. Test command manually: `contextfs --root ./documents`
4. Check Claude Desktop logs (Help → View Logs)
5. Restart Claude Desktop completely

### Permission Errors

```bash
# Ensure documents are readable
chmod -R +r /path/to/documents

# Ensure MCP binary is executable
chmod +x $(which contextfs)
```

### Path Issues

- Use absolute paths in configuration
- Avoid spaces in paths or quote them properly
- Check that knowledge root exists and is a directory

### Search Not Working

1. Verify ugrep is installed: `which ugrep`
2. Check filter commands are whitelisted
3. Increase search timeout in config
4. Check exclude patterns aren't too broad

### Docker Issues

```bash
# Check volume mounts
docker run -it --rm -v /path/to/docs:/knowledge:ro contextfs ls /knowledge

# Check container logs
docker logs <container-id>
```

---

## Best Practices

1. **Use absolute paths** in production configurations
2. **Enable whitelist mode** for security
3. **Mount documents read-only** in Docker
4. **Set appropriate timeouts** for your use case
5. **Use structured logging** for monitoring
6. **Keep sync separate** from the MCP server
7. **Test configuration** before deploying
8. **Monitor resource usage** in production

---

## Additional Resources

- [Configuration Reference](configuration.md)
- [Tools Reference](tools.md)
- [Cloud Sync Guide](cloud-sync-guide.md)
- [MCP Documentation](https://modelcontextprotocol.io/)
- [Claude Desktop](https://claude.ai/download)
