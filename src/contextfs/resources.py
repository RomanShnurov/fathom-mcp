"""MCP Resources for knowledge base."""

import json

from mcp.server import Server
from mcp.types import Resource, ResourceTemplate

from .config import Config


def register_resources(server: Server, config: Config) -> None:
    """Register MCP resources."""

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """List available resources."""
        return [
            Resource(
                uri="knowledge://index",
                name="Knowledge Base Index",
                description="Root index of all collections",
                mimeType="application/json",
            ),
        ]

    @server.list_resource_templates()
    async def list_resource_templates() -> list[ResourceTemplate]:
        """List resource URI templates."""
        return [
            ResourceTemplate(
                uriTemplate="knowledge://{path}/index",
                name="Collection Index",
                description="List of documents in a collection",
                mimeType="application/json",
            ),
            ResourceTemplate(
                uriTemplate="knowledge://{path}/info",
                name="Document Info",
                description="Document metadata and TOC",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        """Read resource content."""
        # Parse URI: knowledge://path/type
        if not uri.startswith("knowledge://"):
            raise ValueError(f"Invalid URI scheme: {uri}")

        path_and_type = uri[len("knowledge://") :]

        if path_and_type == "index":
            return await _get_root_index(config)

        if path_and_type.endswith("/index"):
            path = path_and_type[:-6]  # Remove "/index"
            return await _get_collection_index(config, path)

        if path_and_type.endswith("/info"):
            path = path_and_type[:-5]  # Remove "/info"
            return await _get_document_info_resource(config, path)

        raise ValueError(f"Unknown resource: {uri}")


async def _get_root_index(config: Config) -> str:
    """Get root index as JSON."""
    root = config.knowledge.root

    collections = []
    for item in sorted(root.iterdir()):
        if item.is_dir() and not item.name.startswith("."):
            collections.append(
                {
                    "name": item.name,
                    "path": item.name,
                    "type": "collection",
                }
            )

    return json.dumps(
        {
            "collections": collections,
            "root": str(root),
        },
        indent=2,
    )


async def _get_collection_index(config: Config, path: str) -> str:
    """Get collection index as JSON."""
    full_path = config.knowledge.root / path

    if not full_path.exists() or not full_path.is_dir():
        raise ValueError(f"Collection not found: {path}")

    items = []
    for item in sorted(full_path.iterdir()):
        if item.name.startswith("."):
            continue

        if item.is_dir():
            items.append(
                {
                    "name": item.name,
                    "path": f"{path}/{item.name}",
                    "type": "collection",
                }
            )
        elif item.suffix.lower() in config.supported_extensions:
            items.append(
                {
                    "name": item.name,
                    "path": f"{path}/{item.name}",
                    "type": "document",
                    "format": item.suffix.lower().lstrip("."),
                }
            )

    return json.dumps({"items": items, "path": path}, indent=2)


async def _get_document_info_resource(config: Config, path: str) -> str:
    """Get document info as JSON."""
    from .tools.read import _get_document_info

    info = await _get_document_info(config, {"path": path})
    return json.dumps(info, indent=2)
