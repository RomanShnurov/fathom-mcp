"""Sidebar component for MCP Inspector."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

# Add inspector directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_client import MCPClientError, ServerConfig, list_tools


def render_sidebar() -> None:
    """Render the sidebar with connection settings and status."""
    st.sidebar.title("MCP Inspector")
    st.sidebar.markdown("---")

    # Server configuration
    st.sidebar.subheader("Server Configuration")

    root_path = st.sidebar.text_input(
        "Knowledge Root",
        value=st.session_state.get("root_path", "./documents"),
        help="Path to the documents directory",
        key="root_path_input",
    )

    # Connect button
    col1, col2 = st.sidebar.columns(2)

    with col1:
        if st.button("Connect", use_container_width=True):
            _connect_to_server(root_path)

    with col2:
        if st.button("Disconnect", use_container_width=True):
            _disconnect()

    st.sidebar.markdown("---")

    # Connection status
    _render_status()

    # Tool list
    if st.session_state.get("connected"):
        st.sidebar.markdown("---")
        _render_tool_list()


def _connect_to_server(root_path: str) -> None:
    """Attempt to connect to the MCP server."""
    config = ServerConfig(root_path=root_path)
    st.session_state["server_config"] = config
    st.session_state["root_path"] = root_path

    with st.spinner("Connecting to MCP server..."):
        try:
            tools = list_tools(config)
            st.session_state["tools"] = tools
            st.session_state["connected"] = True
            st.session_state["error"] = None
            st.toast(f"Connected! {len(tools)} tools available", icon="✅")
        except MCPClientError as e:
            st.session_state["connected"] = False
            st.session_state["error"] = str(e)
            st.toast(f"Connection failed: {e}", icon="❌")


def _disconnect() -> None:
    """Disconnect from the server."""
    st.session_state["connected"] = False
    st.session_state["tools"] = []
    st.session_state["server_config"] = None
    st.session_state["error"] = None
    st.toast("Disconnected", icon="👋")


def _render_status() -> None:
    """Render connection status indicator."""
    if st.session_state.get("connected"):
        st.sidebar.success("Connected")
        config = st.session_state.get("server_config")
        if config:
            st.sidebar.caption(f"Root: `{config.root_path}`")
    elif st.session_state.get("error"):
        st.sidebar.error("Connection Error")
        st.sidebar.caption(st.session_state["error"])
    else:
        st.sidebar.warning("Not connected")


def _render_tool_list() -> None:
    """Render the list of available tools."""
    tools = st.session_state.get("tools", [])

    st.sidebar.subheader(f"Available Tools ({len(tools)})")

    for tool in tools:
        with st.sidebar.expander(f"`{tool.name}`"):
            st.caption(tool.description)
