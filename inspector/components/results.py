"""Results display component for MCP Inspector."""

from __future__ import annotations

import json
from typing import Any

import streamlit as st


def render_result(result: dict[str, Any]) -> None:
    """Render a tool result with multiple display options."""
    # Display mode selector
    display_mode = st.radio(
        "Display Mode",
        options=["JSON", "Formatted", "Raw"],
        horizontal=True,
        key="result_display_mode",
    )

    if display_mode == "JSON":
        _render_json(result)
    elif display_mode == "Formatted":
        _render_formatted(result)
    else:
        _render_raw(result)


def _render_json(result: dict[str, Any]) -> None:
    """Render result as formatted JSON."""
    st.json(result)


def _render_raw(result: dict[str, Any]) -> None:
    """Render result as raw text."""
    st.code(json.dumps(result, indent=2, ensure_ascii=False), language="json")


def _render_formatted(result: dict[str, Any]) -> None:
    """Render result in a formatted, human-readable way."""
    # Detect result type and render appropriately
    if "matches" in result:
        _render_search_results(result)
    elif "collections" in result or "documents" in result:
        _render_browse_results(result)
    elif "content" in result:
        _render_document_content(result)
    elif "name" in result and "path" in result:
        _render_document_info(result)
    elif "results" in result:
        _render_find_results(result)
    else:
        # Fallback to JSON
        st.json(result)


def _render_search_results(result: dict[str, Any]) -> None:
    """Render search results."""
    matches = result.get("matches", [])
    total = result.get("total_matches", len(matches))
    truncated = result.get("truncated", False)

    # Summary
    st.markdown(f"**Found {total} matches**")
    if truncated:
        st.warning(f"Results truncated. Showing {len(matches)} of {total}.")

    if not matches:
        st.info("No matches found.")
        return

    # Render each match
    for i, match in enumerate(matches):
        with st.expander(
            f"**{match.get('document', 'Unknown')}** : line {match.get('line', '?')}",
            expanded=(i < 3),
        ):
            # Context before
            context_before = match.get("context_before", [])
            if context_before:
                for ctx in context_before:
                    st.text(f"  {ctx}")

            # Matched line (highlighted)
            text = match.get("text", "")
            st.markdown(f"**> {text}**")

            # Context after
            context_after = match.get("context_after", [])
            if context_after:
                for ctx in context_after:
                    st.text(f"  {ctx}")


def _render_browse_results(result: dict[str, Any]) -> None:
    """Render browse/list_collections results."""
    current_path = result.get("current_path", "/")
    st.markdown(f"**Current Path:** `{current_path}`")

    # Collections
    collections = result.get("collections", [])
    if collections:
        st.markdown("### Collections")
        for coll in collections:
            name = coll.get("name", "Unknown")
            path = coll.get("path", "")
            doc_count = coll.get("document_count", 0)
            sub_count = coll.get("subcollection_count", 0)
            st.markdown(f"- **{name}** (`{path}`) - {doc_count} docs, {sub_count} subcollections")

    # Documents
    documents = result.get("documents", [])
    if documents:
        st.markdown("### Documents")
        for doc in documents:
            name = doc.get("name", "Unknown")
            size = doc.get("size_bytes", 0)
            modified = doc.get("modified", "")
            size_str = _format_size(size)
            st.markdown(f"- **{name}** ({size_str}) - {modified}")

    if not collections and not documents:
        st.info("Empty collection.")


def _render_document_content(result: dict[str, Any]) -> None:
    """Render read_document results."""
    content = result.get("content", "")
    pages_read = result.get("pages_read", [])
    total_pages = result.get("total_pages", 0)
    truncated = result.get("truncated", False)

    # Metadata
    if pages_read:
        st.markdown(f"**Pages read:** {pages_read} of {total_pages}")
    if truncated:
        st.warning("Content was truncated due to size limits.")

    # Content
    st.markdown("### Content")
    st.text_area(
        "Document content",
        value=content,
        height=400,
        label_visibility="collapsed",
    )


def _render_document_info(result: dict[str, Any]) -> None:
    """Render get_document_info results."""
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Document Info")
        st.markdown(f"**Name:** {result.get('name', 'Unknown')}")
        st.markdown(f"**Path:** `{result.get('path', '')}`")
        st.markdown(f"**Collection:** `{result.get('collection', '')}`")
        st.markdown(f"**Format:** {result.get('format', 'unknown')}")

    with col2:
        st.markdown("### Metadata")
        st.markdown(f"**Size:** {_format_size(result.get('size_bytes', 0))}")
        st.markdown(f"**Modified:** {result.get('modified', '')}")
        if "pages" in result:
            st.markdown(f"**Pages:** {result.get('pages', 0)}")

    # Table of contents
    toc = result.get("toc", [])
    if toc:
        st.markdown("### Table of Contents")
        _render_toc(toc)


def _render_toc(toc: list[dict[str, Any]], level: int = 0) -> None:
    """Render table of contents recursively."""
    indent = "  " * level
    for item in toc:
        title = item.get("title", "Untitled")
        page = item.get("page", "?")
        st.markdown(f"{indent}- **{title}** (p. {page})")

        children = item.get("children", [])
        if children:
            _render_toc(children, level + 1)


def _render_find_results(result: dict[str, Any]) -> None:
    """Render find_document results."""
    results = result.get("results", [])

    if not results:
        st.info("No documents found.")
        return

    st.markdown(f"**Found {len(results)} documents**")

    for doc in results:
        name = doc.get("name", "Unknown")
        path = doc.get("path", "")
        score = doc.get("score", 0)

        st.markdown(f"- **{name}** (`{path}`) - score: {score:.2f}")


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
