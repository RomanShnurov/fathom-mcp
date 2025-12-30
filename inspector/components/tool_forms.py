"""Tool forms component for MCP Inspector."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import streamlit as st

# Add inspector directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from components.results import render_result
from mcp_client import MCPClientError, ToolInfo, call_tool


def render_tool_section() -> None:
    """Render the tools section with forms and results."""
    if not st.session_state.get("connected"):
        st.info("Please connect to an MCP server first using the sidebar.")
        return

    tools: list[ToolInfo] = st.session_state.get("tools", [])
    if not tools:
        st.warning("No tools available from the server.")
        return

    # Tool selector
    tool_names = [t.name for t in tools]
    selected_name = st.selectbox(
        "Select Tool",
        options=tool_names,
        key="selected_tool",
    )

    if not selected_name:
        return

    # Find selected tool
    tool = next((t for t in tools if t.name == selected_name), None)
    if not tool:
        return

    # Tool description
    st.markdown(f"**Description:** {tool.description}")

    # Schema viewer
    with st.expander("View Schema"):
        st.json(tool.schema)

    st.markdown("---")

    # Build form based on tool
    st.subheader("Parameters")
    _render_tool_form(tool)


def _render_tool_form(tool: ToolInfo) -> None:
    """Render the form for a specific tool."""
    form_key = f"form_{tool.name}"

    with st.form(key=form_key):
        args = _build_form_fields(tool.schema, tool.name)

        submitted = st.form_submit_button("Execute", use_container_width=True)

        if submitted:
            _execute_tool(tool.name, args)


def _build_form_fields(schema: dict[str, Any], tool_name: str) -> dict[str, Any]:
    """Build form fields from JSON schema and return collected values."""
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    args: dict[str, Any] = {}

    for prop_name, prop_schema in properties.items():
        is_required = prop_name in required
        value = _render_field(prop_name, prop_schema, is_required, tool_name)

        # Only include non-empty values
        if value is not None and value != "" and value != []:
            args[prop_name] = value

    return args


def _render_field(name: str, schema: dict[str, Any], required: bool, parent_key: str) -> Any:
    """Render a single form field based on its schema."""
    field_type = schema.get("type", "string")
    description = schema.get("description", "")
    default = schema.get("default")
    label = f"{name}{'*' if required else ''}"
    key = f"{parent_key}_{name}"

    # Handle special cases first
    if name == "scope" and field_type == "object":
        return _render_scope_field(key)

    if name == "pages" and field_type == "array":
        return _render_pages_field(key, description)

    if name == "terms" and field_type == "array":
        return _render_terms_field(key, description)

    # Standard field types
    if field_type == "string":
        if "enum" in schema:
            return st.selectbox(label, options=schema["enum"], help=description, key=key)
        return st.text_input(label, value=default or "", help=description, key=key)

    if field_type == "integer":
        return st.number_input(
            label, value=default if default is not None else 0, step=1, help=description, key=key
        )

    if field_type == "boolean":
        return st.checkbox(label, value=default or False, help=description, key=key)

    if field_type == "array":
        return _render_generic_array_field(name, schema, label, description, key)

    if field_type == "object":
        return _render_generic_object_field(name, schema, label, description, key)

    # Fallback to text input
    return st.text_input(label, help=description, key=key)


def _render_scope_field(key: str) -> dict[str, Any]:
    """Render the scope field for search tools."""
    st.markdown("**Scope**")

    col1, col2 = st.columns(2)

    with col1:
        scope_type = st.selectbox(
            "Type",
            options=["global", "collection", "document"],
            help="Search scope type",
            key=f"{key}_type",
        )

    scope: dict[str, Any] = {"type": scope_type}

    with col2:
        if scope_type in ("collection", "document"):
            path = st.text_input(
                "Path",
                help="Path relative to knowledge root",
                key=f"{key}_path",
            )
            if path:
                scope["path"] = path

    return scope


def _render_pages_field(key: str, description: str) -> list[int]:
    """Render the pages field for read_document."""
    text = st.text_input(
        "pages",
        help=f"{description} (comma-separated integers, e.g., 1,2,3)",
        key=key,
    )

    if not text:
        return []

    try:
        return [int(x.strip()) for x in text.split(",") if x.strip()]
    except ValueError:
        st.warning("Invalid page numbers. Please enter comma-separated integers.")
        return []


def _render_terms_field(key: str, description: str) -> list[str]:
    """Render the terms field for search_multiple."""
    text = st.text_area(
        "terms*",
        help=f"{description} (one term per line, max 10)",
        key=key,
        height=100,
    )

    if not text:
        return []

    terms = [line.strip() for line in text.split("\n") if line.strip()]
    if len(terms) > 10:
        st.warning("Maximum 10 terms allowed. Only first 10 will be used.")
        return terms[:10]

    return terms


def _render_generic_array_field(
    name: str, schema: dict[str, Any], label: str, description: str, key: str
) -> list[Any]:
    """Render a generic array field."""
    text = st.text_input(
        label,
        help=f"{description} (comma-separated)",
        key=key,
    )

    if not text:
        return []

    item_type = schema.get("items", {}).get("type", "string")
    items = [x.strip() for x in text.split(",") if x.strip()]

    if item_type == "integer":
        try:
            return [int(x) for x in items]
        except ValueError:
            st.warning(f"Invalid values for {name}. Expected integers.")
            return []

    return items


def _render_generic_object_field(
    name: str, schema: dict[str, Any], label: str, description: str, key: str
) -> dict[str, Any]:
    """Render a generic object field as JSON input."""
    st.markdown(f"**{label}**")
    st.caption(description)

    json_text = st.text_area(
        f"{name} (JSON)",
        help="Enter JSON object",
        key=key,
        height=100,
    )

    if not json_text:
        return {}

    import json

    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        st.warning(f"Invalid JSON for {name}")
        return {}


def _execute_tool(tool_name: str, args: dict[str, Any]) -> None:
    """Execute a tool and store the result."""
    config = st.session_state.get("server_config")
    if not config:
        st.error("No server configuration found.")
        return

    with st.spinner(f"Executing {tool_name}..."):
        try:
            result = call_tool(config, tool_name, args)
            st.session_state["last_result"] = result
            st.session_state["last_tool"] = tool_name
            st.session_state["last_error"] = None
            st.toast(f"{tool_name} executed successfully", icon="✅")
        except MCPClientError as e:
            st.session_state["last_result"] = None
            st.session_state["last_error"] = str(e)
            st.toast(f"Error: {e}", icon="❌")

    # Render result below the form
    st.markdown("---")
    st.subheader("Result")

    if st.session_state.get("last_error"):
        st.error(st.session_state["last_error"])
    elif st.session_state.get("last_result") is not None:
        render_result(st.session_state["last_result"])
