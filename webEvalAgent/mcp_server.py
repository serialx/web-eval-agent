#!/usr/bin/env python3

import asyncio
import os
import argparse
import traceback
import uuid
from enum import Enum
from webEvalAgent.src.utils import stop_log_server

# Set the API key to a fake key to avoid error in backend
os.environ["ANTHROPIC_API_KEY"] = 'not_a_real_key'
os.environ["ANONYMIZED_TELEMETRY"] = 'false'

# MCP imports
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent

# Import our modules
from webEvalAgent.src.browser_manager import PlaywrightBrowserManager
# from webEvalAgent.src.browser_utils import cleanup_resources # Removed import
from webEvalAgent.src.api_utils import validate_api_key
from webEvalAgent.src.tool_handlers import handle_web_evaluation

stop_log_server() # Stop the log server before starting the MCP server

# Create the MCP server
mcp = FastMCP("Operative")

# Define the browser tools
class BrowserTools(str, Enum):
    WEB_EVAL_AGENT = "web_eval_agent"

# Parse command line arguments (keeping the parser for potential future arguments)
parser = argparse.ArgumentParser(description='Run the MCP server with browser debugging capabilities')
args = parser.parse_args()

# Get API key from environment variable
api_key = os.environ.get('OPERATIVE_API_KEY')

# Validate the API key
if api_key:
    is_valid = asyncio.run(validate_api_key(api_key))
    if not is_valid:
        print("Error: Invalid API key. Please provide a valid OperativeAI API key in the OPERATIVE_API_KEY environment variable.")
else:
    print("Error: No API key provided. Please set the OPERATIVE_API_KEY environment variable.")

@mcp.tool(name=BrowserTools.WEB_EVAL_AGENT)
async def web_eval_agent(url: str, task: str, working_directory: str, ctx: Context) -> list[TextContent]:
    """Evaluate the user experience / interface of a web application.

    This tool allows the AI to assess the quality of user experience and interface design
    of a web application by performing specific tasks and analyzing the interaction flow.

    Before this tool is used, the web application should already be running locally in a separate terminal.

    Args:
        url: Required. The localhost URL of the web application to evaluate, including the port number.
        task: Required. The specific UX/UI aspect to test (e.g., "test the checkout flow",
             "evaluate the navigation menu usability", "check form validation feedback")
             Be as detailed as possible in your task description. It could be anywhere from 2 sentences to 2 paragraphs.
        working_directory: Required. The root directory of the project
        external_browser: Optional. Whether to show the browser window externally during evaluation. Defaults to False. 

    Returns:
        list[list[TextContent, ImageContent]]: A detailed evaluation of the web application's UX/UI, including
                         observations, issues found, and recommendations for improvement
                         and screenshots of the web application during the evaluation
    """
    external_browser = True
    # Convert external_browser to headless parameter (inverse logic)
    headless = not external_browser
    is_valid = await validate_api_key(api_key)

    if not is_valid:
        error_message_str = "❌ Error: API Key validation failed when running the tool.\n"
        error_message_str += "   Reason: Free tier limit reached.\n"
        error_message_str += "   👉 Please subscribe at https://operative.sh to continue."
        return [TextContent(type="text", text=error_message_str)]
    try:
        # Generate a new tool_call_id for this specific tool call
        tool_call_id = str(uuid.uuid4())
        print(f"Generated new tool_call_id for web_eval_agent: {tool_call_id}")
        return await handle_web_evaluation(
            {"url": url, "task": task, "headless": headless, "tool_call_id": tool_call_id},
            ctx,
            api_key
        )
    except Exception as e:
        tb = traceback.format_exc()
        return [TextContent(
            type="text",
            text=f"Error executing web_eval_agent: {str(e)}\n\nTraceback:\n{tb}"
        )]

if __name__ == "__main__":
    try:
        # Run a test evaluation on localhost:5173
        import asyncio
        
        async def run_test_eval():
            await web_eval_agent(
                url="http://localhost:5173", 
                task="general eval", 
                working_directory=".", 
                ctx="fdafdaf"
            )
        
        # Run the evaluation
        asyncio.run(run_test_eval())
    finally:
        # Ensure resources are cleaned up
        # asyncio.run(cleanup_resources()) # Cleanup now handled in browser_utils
        pass # Keep finally block structure if needed later

def main():
     try:
         # Run the FastMCP server
         mcp.run(transport='stdio')
     finally:
         # Ensure resources are cleaned up
         # asyncio.run(cleanup_resources()) # Cleanup now handled in browser_utils
         pass # Keep finally block structure if needed later
