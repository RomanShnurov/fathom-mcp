# OpenAI Agent SDK Integration

Guide for integrating file-knowledge-mcp with OpenAI Agents SDK.

## Overview

OpenAI Agents SDK has **built-in support for the MCP protocol** through the `agents.mcp` module. This means that integrating file-knowledge-mcp requires just a few lines of code without the need to create intermediate layers.

### Key Features

- ✅ **Native integration** - SDK automatically handles MCP tools
- ✅ **Automatic conversion** - MCP tools become available to the agent without additional code
- ✅ **Multiple transports** - stdio, HTTP, SSE
- ✅ **Tool filtering** - access control for tools
- ✅ **Streaming** - streaming processing of results
- ✅ **Prompts** - use dynamic prompts from MCP server

---

## Quick Start

### Step 1: Install Dependencies

```bash
# Install OpenAI Agents SDK
pip install openai-agents-python

# Install file-knowledge-mcp
pip install file-knowledge-mcp

# System dependencies
# Ubuntu/Debian:
sudo apt install ugrep poppler-utils

# macOS:
brew install ugrep poppler
```

### Step 2: Basic Integration

Create a file `knowledge_bot.py`:

```python
import asyncio
from agents import Agent, Runner
from agents.mcp import MCPServerStdio


async def main():
    """Simple bot with access to local documents."""

    # Connect to file-knowledge-mcp server
    async with MCPServerStdio(
        name="File Knowledge",
        params={
            "command": "file-knowledge-mcp",
            "args": ["--root", "./documents"]
        }
    ) as server:
        # Create agent with access to MCP tools
        agent = Agent(
            name="Knowledge Assistant",
            instructions=(
                "You are an assistant with access to a local knowledge base. "
                "Use search and document reading tools to answer questions."
            ),
            mcp_servers=[server]
        )

        # Run query
        result = await Runner.run(
            agent,
            "Find information about authentication in the documents"
        )

        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 3: Run

```bash
# Set OpenAI API key
export OPENAI_API_KEY=your-openai-api-key

# Run the bot
python knowledge_bot.py
```

Done! The agent will automatically get access to all file-knowledge-mcp tools:
- `search_documents` - search through documents
- `read_document` - read documents
- `list_collections` - navigate collections
- `find_document` - find documents by name

---

## Interactive Bot

Example of a bot with interactive mode:

```python
import asyncio
import os
from agents import Agent, Runner
from agents.mcp import MCPServerStdio


async def run_interactive_bot():
    """Interactive bot with local knowledge base."""

    async with MCPServerStdio(
        name="File Knowledge",
        params={
            "command": "file-knowledge-mcp",
            "args": [
                "--root", os.path.expanduser("~/Documents"),
                "--config", "./config.yaml"  # Optional
            ]
        }
    ) as server:
        agent = Agent(
            name="Knowledge Assistant",
            instructions=(
                "You are a smart assistant with access to user documents. "
                "Answer questions using information from documents. "
                "If the needed information is not available, say so honestly."
            ),
            model="gpt-4o",  # Use the best model
            mcp_servers=[server]
        )

        print("🤖 Bot started! Type 'exit' to quit.\n")

        while True:
            user_input = input("\n📝 You: ")

            if user_input.lower() in ["exit", "quit"]:
                print("👋 Goodbye!")
                break

            if not user_input.strip():
                continue

            try:
                result = await Runner.run(agent, user_input)
                print(f"\n🤖 Bot: {result.final_output}")
            except Exception as e:
                print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(run_interactive_bot())
```

---

## Advanced Features

### 1. Tool Filtering

Control which tools are available to the agent:

#### Static Filtering

```python
from agents.mcp import MCPServerStdio, create_static_tool_filter

async with MCPServerStdio(
    name="File Knowledge (Read Only)",
    params={
        "command": "file-knowledge-mcp",
        "args": ["--root", "./documents"]
    },
    # Allow only reading and searching
    tool_filter=create_static_tool_filter(
        allowed_tool_names=["search_documents", "read_document"]
    )
) as server:
    agent = Agent(
        name="Search Assistant",
        instructions="Help find information in documents.",
        mcp_servers=[server]
    )
```

#### Dynamic Filtering

```python
from agents.mcp import MCPServerStdio, ToolFilterContext


async def context_aware_filter(context: ToolFilterContext, tool) -> bool:
    """Filter based on agent context."""

    # Restrict access for certain agents
    if context.agent.name == "Public Assistant":
        # Public agent can only search
        return tool.name in ["search_documents", "list_collections"]

    # Other agents have full access
    return True


async with MCPServerStdio(
    name="File Knowledge",
    params={
        "command": "file-knowledge-mcp",
        "args": ["--root", "./documents"]
    },
    tool_filter=context_aware_filter
) as server:
    # Create agent with restricted access
    public_agent = Agent(
        name="Public Assistant",
        instructions="Help find publicly available information.",
        mcp_servers=[server]
    )
```

### 2. Caching Tool List

To improve performance with frequent requests:

```python
async with MCPServerStdio(
    name="File Knowledge",
    params={
        "command": "file-knowledge-mcp",
        "args": ["--root", "./documents"]
    },
    cache_tools_list=True  # Cache the tool list
) as server:
    agent = Agent(
        name="Knowledge Assistant",
        mcp_servers=[server]
    )
```

### 3. Streaming Results

Get results in real-time:

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStdio


async def streaming_example():
    async with MCPServerStdio(
        name="File Knowledge",
        params={
            "command": "file-knowledge-mcp",
            "args": ["--root", "./documents"]
        }
    ) as server:
        agent = Agent(
            name="Knowledge Assistant",
            instructions="Answer questions using documents.",
            mcp_servers=[server]
        )

        # Run with streaming
        result = Runner.run_streamed(
            agent,
            "Find and summarize all information about security API"
        )

        # Process events as they arrive
        async for event in result.stream_events():
            if event.type == "run_item_stream_event":
                print(f"📨 {event.item}")

        print(f"\n✅ Summary: {result.final_output}")


asyncio.run(streaming_example())
```

### 4. Using Multiple MCP Servers

Combine file-knowledge-mcp with other servers:

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStdio


async def multi_server_example():
    # Connect file-knowledge-mcp
    async with MCPServerStdio(
        name="File Knowledge",
        params={
            "command": "file-knowledge-mcp",
            "args": ["--root", "./documents"]
        }
    ) as knowledge_server:
        # Connect filesystem server
        async with MCPServerStdio(
            name="Filesystem",
            params={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "./workspace"]
            }
        ) as fs_server:
            agent = Agent(
                name="Multi-tool Assistant",
                instructions=(
                    "Use file-knowledge for searching documentation, "
                    "and filesystem for working with the project."
                ),
                mcp_servers=[knowledge_server, fs_server]
            )

            result = await Runner.run(
                agent,
                "Find in the documentation how to implement authentication, "
                "and create an auth.py file in the project"
            )
            print(result.final_output)


asyncio.run(multi_server_example())
```

### 5. Multi-agent workflows

Create specialized agents with different access:

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStdio


async def multi_agent_workflow():
    async with MCPServerStdio(
        name="File Knowledge",
        params={
            "command": "file-knowledge-mcp",
            "args": ["--root", "./documents"]
        }
    ) as server:
        # Researcher agent
        researcher = Agent(
            name="Researcher",
            instructions=(
                "You are a researcher. Search for information in documents "
                "and provide detailed facts."
            ),
            mcp_servers=[server]
        )

        # Analyst agent
        analyst = Agent(
            name="Analyst",
            instructions=(
                "You are an analyst. You receive facts from the researcher "
                "and make conclusions."
            ),
            # Analyst has no direct access to documents
        )

        # Orchestrator
        orchestrator = Agent(
            name="Orchestrator",
            instructions=(
                "You are a coordinator. Use researcher to gather facts, "
                "then analyst for analysis."
            ),
            tools=[
                researcher.as_tool(
                    tool_name="research",
                    tool_description="Find information in documents"
                ),
                analyst.as_tool(
                    tool_name="analyze",
                    tool_description="Analyze information"
                )
            ]
        )

        result = await Runner.run(
            orchestrator,
            "Research our security documentation and provide recommendations"
        )
        print(result.final_output)


asyncio.run(multi_agent_workflow())
```

---

## HTTP Transport

For production deployments, you can use HTTP instead of stdio:

### Option 1: Streamable HTTP

```python
from agents import Agent, Runner
from agents.mcp import MCPServerStreamableHttp


async def http_integration():
    async with MCPServerStreamableHttp(
        name="File Knowledge HTTP",
        params={
            "url": "http://localhost:8000/mcp",
            "headers": {
                "Authorization": "Bearer your-token-here"
            },
            "timeout": 30
        },
        cache_tools_list=True,
        max_retry_attempts=3
    ) as server:
        agent = Agent(
            name="Knowledge Assistant",
            instructions="Use knowledge from documents.",
            mcp_servers=[server]
        )

        result = await Runner.run(agent, "Find information about deployment")
        print(result.final_output)


asyncio.run(http_integration())
```

### Option 2: Server-Sent Events (SSE)

```python
from agents import Agent, Runner
from agents.mcp import MCPServerSse


async def sse_integration():
    async with MCPServerSse(
        name="File Knowledge SSE",
        params={
            "url": "http://localhost:8000/sse",
            "headers": {
                "X-API-Key": "your-api-key"
            }
        },
        cache_tools_list=True
    ) as server:
        agent = Agent(
            name="Knowledge Assistant",
            mcp_servers=[server]
        )

        result = await Runner.run(agent, "Search documents")
        print(result.final_output)


asyncio.run(sse_integration())
```

**Note**: HTTP transport requires a separate HTTP server wrapping file-knowledge-mcp. Stdio transport is recommended for most cases.

---

## Configuration

### Passing Configuration via Arguments

```python
async with MCPServerStdio(
    name="File Knowledge",
    params={
        "command": "file-knowledge-mcp",
        "args": [
            "--root", "/path/to/documents",
            "--config", "/path/to/config.yaml"
        ],
        "env": {
            # Override settings via environment variables
            "FKM_SEARCH__MAX_RESULTS": "100",
            "FKM_SEARCH__TIMEOUT_SECONDS": "60",
            "FKM_SECURITY__FILTER_MODE": "whitelist"
        }
    }
) as server:
    # ...
```

### Example config.yaml

```yaml
knowledge:
  root: "./documents"

search:
  context_lines: 5
  max_results: 50
  timeout_seconds: 30

security:
  enable_shell_filters: true
  filter_mode: whitelist
  allow_symlinks: false

exclude:
  patterns:
    - ".git/*"
    - "*.bak"
    - "*.tmp"
    - "*.draft.*"
```

---

## Best Practices

### 1. Use Clear Instructions

```python
agent = Agent(
    name="Knowledge Assistant",
    instructions=(
        "You are an expert assistant with access to company documentation. "
        "\n\nRULES:"
        "\n1. Always search for information in documents before answering"
        "\n2. If information is not available, say so honestly"
        "\n3. Cite sources (document names)"
        "\n4. For complex questions, use multiple searches"
    ),
    mcp_servers=[server]
)
```

### 2. Handle Errors

```python
async def safe_query(agent: Agent, query: str, max_retries: int = 3):
    """Query with error handling and retries."""
    for attempt in range(max_retries):
        try:
            result = await Runner.run(agent, query)
            return result.final_output
        except Exception as e:
            if attempt == max_retries - 1:
                return f"Failed to execute query: {e}"
            print(f"Attempt {attempt + 1} failed, retrying...")
            await asyncio.sleep(1)
```

### 3. Limit Search Scope

```python
# Instead of global search, specify collection
user_input = "Find information about API in developer documentation"

agent = Agent(
    name="Dev Assistant",
    instructions=(
        "Search for information in 'developers' collection using search_documents tool "
        "with scope parameter: {type: 'collection', path: 'developers'}"
    ),
    mcp_servers=[server]
)
```

### 4. Log Actions

```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def logged_query(agent: Agent, query: str):
    """Query with logging."""
    logger.info(f"User query: {query}")

    result = await Runner.run(agent, query)

    logger.info(f"Agent response: {result.final_output}")
    logger.info(f"Tools used: {[step.tool_name for step in result.steps if step.tool_name]}")

    return result.final_output
```

### 5. Use Context

```python
from pydantic import BaseModel
from agents import RunContextWrapper


class UserContext(BaseModel):
    user_id: str
    language: str = "en"
    max_search_results: int = 20


async def contextual_agent():
    context = RunContextWrapper(UserContext(
        user_id="user_123",
        language="en",
        max_search_results=30
    ))

    async with MCPServerStdio(
        name="File Knowledge",
        params={
            "command": "file-knowledge-mcp",
            "args": ["--root", "./documents"]
        }
    ) as server:
        agent = Agent(
            name="Contextual Assistant",
            instructions=(
                f"Answer in language: {{context.language}}. "
                f"Use up to {{context.max_search_results}} search results."
            ),
            mcp_servers=[server]
        )

        result = await Runner.run(
            agent,
            "Find documentation",
            context=context.context
        )
        print(result.final_output)
```

---

## Troubleshooting

### Issue: MCP Server Won't Start

```bash
# Check installation
which file-knowledge-mcp

# Check system dependencies
which ugrep
which pdftotext

# Check permissions
ls -la /path/to/documents
```

**Solution**: Ensure `file-knowledge-mcp` is installed in PATH and documents are readable.

### Issue: Search Timeout

```python
# Increase timeout in configuration
async with MCPServerStdio(
    name="File Knowledge",
    params={
        "command": "file-knowledge-mcp",
        "args": ["--root", "./documents"],
        "env": {
            "FKM_SEARCH__TIMEOUT_SECONDS": "120"
        }
    }
) as server:
    # ...
```

### Issue: Agent Can't Find Information

**Possible causes**:
1. Documents not in supported format (check `.txt`, `.md`, `.pdf`)
2. Search query too specific
3. Files excluded via `exclude.patterns`

**Solution**: Check search logs and try a more general query.

### Issue: Permission Denied

```bash
# Ensure documents are readable
chmod -R +r /path/to/documents

# Check symlinks
# If using symlinks, enable in config.yaml:
# security:
#   allow_symlinks: true
```

### Issue: Too Many Results

```python
# Limit number of results
async with MCPServerStdio(
    name="File Knowledge",
    params={
        "command": "file-knowledge-mcp",
        "args": ["--root", "./documents"],
        "env": {
            "FKM_SEARCH__MAX_RESULTS": "20"
        }
    }
) as server:
    # ...
```

---

## Docker Deployment

### Production Dockerfile

```dockerfile
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    ugrep \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip install --no-cache-dir \
    openai-agents-python \
    file-knowledge-mcp

# Working directory
WORKDIR /app

# Copy code and configuration
COPY knowledge_bot.py .
COPY config.yaml .

# Mount point for documents
VOLUME ["/documents"]

# Environment variables
ENV OPENAI_API_KEY=""
ENV FKM_KNOWLEDGE__ROOT="/documents"

CMD ["python", "knowledge_bot.py"]
```

### docker-compose.yml

```yaml
version: "3.8"

services:
  knowledge-bot:
    build: .
    volumes:
      - ./documents:/documents:ro
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - FKM_SECURITY__FILTER_MODE=whitelist
      - FKM_SEARCH__MAX_RESULTS=50
    restart: unless-stopped
```

---

## Use Cases

### 1. Technical Support

```python
async def tech_support_bot():
    async with MCPServerStdio(
        name="Knowledge Base",
        params={
            "command": "file-knowledge-mcp",
            "args": ["--root", "./kb"]
        }
    ) as server:
        agent = Agent(
            name="Support Agent",
            instructions=(
                "You are a technical support agent. "
                "Help solve user problems using the knowledge base. "
                "Always provide links to articles from the knowledge base."
            ),
            model="gpt-4o",
            mcp_servers=[server]
        )

        # Interactive support
        while True:
            issue = input("\n🆘 Describe the problem: ")
            if issue.lower() == "exit":
                break

            result = await Runner.run(agent, issue)
            print(f"\n💡 Solution: {result.final_output}")
```

### 2. Code Review Assistant

```python
async def code_review_assistant():
    async with MCPServerStdio(
        name="Coding Standards",
        params={
            "command": "file-knowledge-mcp",
            "args": ["--root", "./docs/standards"]
        }
    ) as server:
        agent = Agent(
            name="Code Reviewer",
            instructions=(
                "You are a code reviewer. Check code for compliance with company standards. "
                "Use documents from the knowledge base to justify comments."
            ),
            model="gpt-4o",
            mcp_servers=[server]
        )

        code = input("📄 Paste code for review: ")
        result = await Runner.run(
            agent,
            f"Review this code:\n\n{code}"
        )
        print(f"\n📝 Review: {result.final_output}")
```

### 3. Documentation Chatbot

```python
async def docs_chatbot():
    async with MCPServerStdio(
        name="Documentation",
        params={
            "command": "file-knowledge-mcp",
            "args": ["--root", "./docs"]
        }
    ) as server:
        agent = Agent(
            name="Docs Assistant",
            instructions=(
                "You are a documentation assistant. "
                "Answer questions accurately and concisely. "
                "Always cite the source of information."
            ),
            model="gpt-4o-mini",  # More economical model
            mcp_servers=[server]
        )

        print("📚 Documentation loaded. Ask questions!\n")

        while True:
            question = input("\n❓ Question: ")
            if question.lower() in ["exit", "quit"]:
                break

            result = await Runner.run(agent, question)
            print(f"\n📖 Answer: {result.final_output}")
```

---

## Comparison with Previous Approach

| Criterion | Old approach (custom bridge) | New approach (agents.mcp) |
|----------|------------------------------|---------------------------|
| Lines of code | ~200 | ~10 |
| Complexity | High | Low |
| Maintenance | Requires updates | Supported by SDK |
| Performance | Medium | High (optimized) |
| Functionality | Basic | Full (filtering, streaming, etc) |
| Reliability | Depends on implementation | Production-ready |

---

## Additional Resources

- [OpenAI Agents SDK Documentation](https://github.com/openai/openai-agents-python)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [file-knowledge-mcp Configuration](configuration.md)
- [file-knowledge-mcp Tools Reference](tools.md)
- [OpenAI Function Calling Guide](https://platform.openai.com/docs/guides/function-calling)

---

## Conclusion

Integrating file-knowledge-mcp with OpenAI Agents SDK is now extremely simple thanks to built-in MCP support. Use `MCPServerStdio` for local deployments and `MCPServerStreamableHttp` for production environments.

For questions and suggestions, create issues in the project repository.
