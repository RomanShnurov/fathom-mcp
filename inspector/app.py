"""MCP Inspector - Streamlit UI for testing contextfs MCP server.

Run with: streamlit run inspector/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add inspector directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
from components.sidebar import render_sidebar
from components.tool_forms import render_tool_section
from mcp_client import (
    MCPClientError,
    get_log_collector,
    list_prompts,
    list_resources,
    read_resource,
)

# Page configuration
st.set_page_config(
    page_title="contextfs MCP Inspector",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize session state
if "connected" not in st.session_state:
    st.session_state["connected"] = False
if "tools" not in st.session_state:
    st.session_state["tools"] = []


def main() -> None:
    """Main application entry point."""
    # Render sidebar
    render_sidebar()

    # Main content area
    st.title("🔍 contextfs MCP Inspector")
    st.markdown("Test and inspect the contextfs MCP server tools, resources, and prompts.")

    # Create tabs
    tab_tools, tab_resources, tab_prompts, tab_logs = st.tabs(
        ["🛠️ Tools", "📁 Resources", "💬 Prompts", "📋 Logs"]
    )

    with tab_tools:
        render_tool_section()

    with tab_resources:
        _render_resources_section()

    with tab_prompts:
        _render_prompts_section()

    with tab_logs:
        _render_logs_section()


def _render_resources_section() -> None:
    """Render the resources section."""
    if not st.session_state.get("connected"):
        st.info("Please connect to an MCP server first using the sidebar.")
        return

    config = st.session_state.get("server_config")
    if not config:
        return

    # Fetch resources button
    if st.button("Refresh Resources"):
        with st.spinner("Fetching resources..."):
            try:
                resources = list_resources(config)
                st.session_state["resources"] = resources
            except MCPClientError as e:
                st.error(f"Failed to fetch resources: {e}")
                return

    resources = st.session_state.get("resources", [])

    if not resources:
        st.info("No resources loaded. Click 'Refresh Resources' to load.")
        return

    st.markdown(f"**{len(resources)} resources available**")

    # Resource list
    for resource in resources:
        with st.expander(f"`{resource.uri}`"):
            st.markdown(f"**Name:** {resource.name}")
            if resource.description:
                st.markdown(f"**Description:** {resource.description}")
            if resource.mime_type:
                st.markdown(f"**MIME Type:** {resource.mime_type}")

            # Read resource button
            if st.button("Read", key=f"read_{resource.uri}"):
                with st.spinner("Reading resource..."):
                    try:
                        content = read_resource(config, resource.uri)
                        st.code(content, language="json")
                    except MCPClientError as e:
                        st.error(f"Failed to read resource: {e}")


def _render_prompts_section() -> None:
    """Render the prompts section."""
    if not st.session_state.get("connected"):
        st.info("Please connect to an MCP server first using the sidebar.")
        return

    config = st.session_state.get("server_config")
    if not config:
        return

    # Fetch prompts button
    if st.button("Refresh Prompts"):
        with st.spinner("Fetching prompts..."):
            try:
                prompts = list_prompts(config)
                st.session_state["prompts"] = prompts
            except MCPClientError as e:
                st.error(f"Failed to fetch prompts: {e}")
                return

    prompts = st.session_state.get("prompts", [])

    if not prompts:
        st.info("No prompts loaded. Click 'Refresh Prompts' to load.")
        return

    st.markdown(f"**{len(prompts)} prompts available**")

    # Prompt list
    for prompt in prompts:
        with st.expander(f"`{prompt.name}`"):
            if prompt.description:
                st.markdown(f"**Description:** {prompt.description}")

            if prompt.arguments:
                st.markdown("**Arguments:**")
                for arg in prompt.arguments:
                    arg_name = arg.get("name", "unknown") if isinstance(arg, dict) else str(arg)
                    arg_desc = arg.get("description", "") if isinstance(arg, dict) else ""
                    arg_required = arg.get("required", False) if isinstance(arg, dict) else False
                    req_str = " (required)" if arg_required else ""
                    st.markdown(f"- `{arg_name}`{req_str}: {arg_desc}")


def _render_logs_section() -> None:
    """Render the logs section."""
    collector = get_log_collector()

    col1, col2, col3, col4 = st.columns([1, 1, 1.5, 1.5])

    with col1:
        if st.button("Refresh Logs"):
            st.rerun()

    with col2:
        if st.button("Clear Logs"):
            collector.clear()
            st.rerun()

    with col3:
        filter_level = st.selectbox(
            "Level",
            options=["All", "ERROR", "WARN", "INFO", "DEBUG"],
            index=0,
            key="log_filter_level",
        )

    with col4:
        filter_source = st.selectbox(
            "Source",
            options=["All", "client", "server"],
            index=0,
            key="log_filter_source",
        )

    st.markdown("---")

    entries = collector.get_all()

    if not entries:
        st.info("No logs yet. Connect to a server and execute some tools.")
        return

    # Filter entries by level
    if filter_level != "All":
        entries = [e for e in entries if e.level == filter_level]

    # Filter entries by source
    if filter_source != "All":
        entries = [e for e in entries if e.source == filter_source]

    st.markdown(f"**{len(entries)} log entries**")

    # Display logs in reverse order (newest first)
    log_text = "\n".join(entry.format() for entry in reversed(entries))

    st.code(log_text, language="log")


if __name__ == "__main__":
    main()
