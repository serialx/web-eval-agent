#!/usr/bin/env python3

# CRITICAL: Configure logging BEFORE any imports to prevent stdout pollution
import logging
import sys
import os

# Disable anonymized telemetry early
os.environ["ANONYMIZED_TELEMETRY"] = 'false'

# Create a null handler to discard all log messages
null_handler = logging.NullHandler()

# Configure root logger first
logging.getLogger().handlers = [null_handler]
logging.getLogger().setLevel(logging.CRITICAL)

# Override basicConfig to prevent other modules from reconfiguring
_original_basicConfig = logging.basicConfig
def no_op(*args, **kwargs):
    pass
logging.basicConfig = no_op

# Pre-configure all known loggers
for logger_name in ["browser_use", "agent", "browser", "playwright", "asyncio",
                   "urllib3", "httpx", "httpcore", "werkzeug", "socketio",
                   "engineio", "flask", "root", ""]:
    logger = logging.getLogger(logger_name)
    logger.handlers = [null_handler]
    logger.setLevel(logging.CRITICAL)
    logger.propagate = False

# Now do the rest of the imports
import asyncio
import argparse
import traceback
import uuid
from enum import Enum
from webEvalAgent.src.utils import stop_log_server
from webEvalAgent.src.log_server import send_log

# MCP imports
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent
# Removing the problematic import
# from mcp.server.tool import Tool, register_tool

# Import our modules
# from webEvalAgent.src.browser_utils import cleanup_resources # Removed import
from webEvalAgent.src.tool_handlers import handle_web_evaluation, handle_setup_browser_state

# MCP server modules

# Stop any existing log server to avoid conflicts
# This doesn't start a new server, just ensures none is running
stop_log_server()

# Create the MCP server
mcp = FastMCP("Operative")

# Define the browser tools
class BrowserTools(str, Enum):
    WEB_EVAL_AGENT = "web_eval_agent"
    SETUP_BROWSER_STATE = "setup_browser_state"  # Add new tool enum

# Parse command line arguments (keeping the parser for potential future arguments)
parser = argparse.ArgumentParser(description='Run the MCP server with browser debugging capabilities')
args = parser.parse_args()

@mcp.tool(name=BrowserTools.WEB_EVAL_AGENT)
async def web_eval_agent(url: str, task: str, ctx: Context, headless_browser: bool = False) -> list[TextContent]:
    """Evaluate the user experience / interface of a web application.

    This tool allows the AI to assess the quality of user experience and interface design
    of a web application by performing specific tasks and analyzing the interaction flow.

    Before this tool is used, the web application should already be running locally on a port.

    Args:
        url: Required. The localhost URL of the web application to evaluate, including the port number.
            Example: http://localhost:3000, http://localhost:8080, http://localhost:4200, http://localhost:5173, etc.
            Try to avoid using the path segments of the URL, and instead use the root URL.
        task: Required. The specific UX/UI aspect to test (e.g., "test the checkout flow",
             "evaluate the navigation menu usability", "check form validation feedback")
             Be as detailed as possible in your task description. It could be anywhere from 2 sentences to 2 paragraphs.
        headless_browser: Optional. Whether to hide the browser window popup during evaluation.
        If headless_browser is True, only the operative control center browser will show, and no popup browser will be shown.

    Returns:
        list[list[TextContent, ImageContent]]: A detailed evaluation of the web application's UX/UI, including
                         observations, issues found, and recommendations for improvement
                         and screenshots of the web application during the evaluation
    """
    headless = headless_browser
    try:
        # Generate a new tool_call_id for this specific tool call
        tool_call_id = str(uuid.uuid4())
        return await handle_web_evaluation(
            {"url": url, "task": task, "headless": headless, "tool_call_id": tool_call_id},
            ctx
        )
    except Exception as e:
        tb = traceback.format_exc()
        return [TextContent(
            type="text",
            text=f"Error executing web_eval_agent: {str(e)}\n\nTraceback:\n{tb}"
        )]

@mcp.tool(name=BrowserTools.SETUP_BROWSER_STATE)
async def setup_browser_state(url: str = None, ctx: Context = None) -> list[TextContent]:
    """Sets up and saves browser state for future use.

    This tool should only be called in one scenario:
    1. The user explicitly requests to set up browser state/authentication

    Launches a non-headless browser for user interaction, allows login/authentication,
    and saves the browser state (cookies, local storage, etc.) to a local file.

    Args:
        url: Optional URL to navigate to upon opening the browser.
        ctx: The MCP context (used for progress reporting, not directly here).

    Returns:
        list[TextContent]: Confirmation of state saving or error messages.
    """
    try:
        # Generate a new tool_call_id for this specific tool call
        tool_call_id = str(uuid.uuid4())
        send_log(f"Generated new tool_call_id for setup_browser_state: {tool_call_id}")
        return await handle_setup_browser_state(
            {"url": url, "tool_call_id": tool_call_id},
            ctx
        )
    except Exception as e:
        tb = traceback.format_exc()
        return [TextContent(
            type="text",
            text=f"Error executing setup_browser_state: {str(e)}\n\nTraceback:\n{tb}"
        )]

def main():
     try:
         # Run the FastMCP server
         mcp.run(transport='stdio')
     finally:
         # Ensure resources are cleaned up when server terminates
         pass

# This entry point is used when running directly
if __name__ == "__main__":
    main()
