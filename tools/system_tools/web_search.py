"""
tools/system_tools/web_search.py — Web search via the system default browser.

Opens a search results page rather than scraping, so no API key or network
client is required.
"""
import asyncio
import re
import urllib.parse
import webbrowser
from typing import Optional

from core.interfaces import ITool
from core.models import ToolMetadata, ToolRequestModel, ToolResultModel
from observability.logger import logger

_ENGINES = {
    "google": "https://www.google.com/search?q=",
    "bing": "https://www.bing.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/?q=",
}


class WebSearchTool(ITool):
    """Runs a web search by opening the results page in the default browser."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="web_search",
            description="Search the web by opening a results page in the default browser.",
            capabilities=["web_search", "search", "browse"],
            permission_level="LOW",
            args_schema={
                "query": "str  — search terms",
                "engine": "str? — google | bing | duckduckgo (default: google)",
            },
        )

    async def execute(self, request: ToolRequestModel) -> ToolResultModel:
        query = str(request.args.get("query") or request.args.get("q") or "").strip()
        engine = str(request.args.get("engine") or "google").strip().lower()

        if not query:
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error="No search query provided.",
            )

        base = _ENGINES.get(engine, _ENGINES["google"])
        url = base + urllib.parse.quote_plus(query)
        logger.info(f"[WebSearchTool] Searching {engine} for '{query}' [CID: {request.correlation_id}]")

        try:
            # webbrowser.open blocks while it hands off to the shell.
            opened = await asyncio.to_thread(webbrowser.open, url)
        except Exception as exc:
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error=f"Could not open browser: {exc}",
            )

        if not opened:
            return ToolResultModel(
                request_id=request.request_id,
                correlation_id=request.correlation_id,
                status="failed",
                error="No default browser available to open the search.",
            )

        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="completed",
            result={"query": query, "engine": engine, "url": url},
        )

    async def undo(self, request: ToolRequestModel) -> ToolResultModel:
        # Opening a results tab is not meaningfully reversible.
        return ToolResultModel(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            status="undone",
            result={"note": "Search tabs are left open; nothing to reverse."},
        )
