#!/usr/bin/env python3

import asyncio
import os
import argparse
import traceback
import uuid
from enum import Enum

# Set the API key to a fake key to avoid error in backend
os.environ["ANTHROPIC_API_KEY"] = 'not_a_real_key'

# MCP imports
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent

# Import our modules
from src.browser_manager import PlaywrightBrowserManager
from src.browser_utils import cleanup_resources
from src.api_utils import validate_api_key
from src.tool_handlers import handle_web_app_ux_evaluation

# Create the MCP server
mcp = FastMCP("Operative")

# Define the browser tools
class BrowserTools(str, Enum):
    WEB_APP_UX_EVALUATOR = "web_app_ux_evaluator"

# Parse command line arguments
parser = argparse.ArgumentParser(description='Run the MCP server with browser debugging capabilities')
parser.add_argument('--api-key', type=str, help='API key for Anthropic Claude')
args = parser.parse_args()

# Store API key
if args.api_key:
    api_key = args.api_key
    
    # Validate the API key
    is_valid = asyncio.run(validate_api_key(api_key))
    if not is_valid:
        print("Error: Invalid API key. Please provide a valid OperativeAI API key.")
        exit(1)
else:
    print("Error: No API key provided. Please provide an API key using --api-key.")
    exit(1)

@mcp.tool(name=BrowserTools.WEB_APP_UX_EVALUATOR)
async def web_app_ux_evaluator(url: str, task: str, ctx: Context) -> list[TextContent]:
    """Evaluate the user experience of a web application.
    
    This tool allows the AI to assess the quality of user experience and interface design
    of a web application by performing specific tasks and analyzing the interaction flow.
    
    Args:
        url: Required. The URL of the web application to evaluate
        task: Required. The specific UX/UI aspect to test (e.g., "test the checkout flow", 
             "evaluate the navigation menu usability", "check form validation feedback")
    
    Returns:
        list[TextContent]: A detailed evaluation of the web application's UX/UI, including
                         observations, issues found, and recommendations for improvement
    """
    try:
        # Generate a new tool_call_id for this specific tool call
        tool_call_id = str(uuid.uuid4())
        print(f"Generated new tool_call_id for web_app_ux_evaluator: {tool_call_id}")
        return await handle_web_app_ux_evaluation(
            {"url": url, "task": task, "tool_call_id": tool_call_id}, 
            ctx, 
            api_key
        )
    except Exception as e:
        tb = traceback.format_exc()
        return [TextContent(
            type="text",
            text=f"Error executing web_app_ux_evaluator: {str(e)}\n\nTraceback:\n{tb}"
        )]

if __name__ == "__main__":
    try:
        # Run the FastMCP server
        mcp.run(transport='stdio')
    finally:
        # Ensure resources are cleaned up
        asyncio.run(cleanup_resources())