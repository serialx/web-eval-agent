#!/usr/bin/env python3

import io
import json
import traceback
import uuid
import re
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, List, Any

from mcp.server.fastmcp import Context
from mcp.types import TextContent

# Import the manager directly
from webEvalAgent.src.browser_manager import PlaywrightBrowserManager
# Only import run_browser_task from browser_utils
from webEvalAgent.src.browser_utils import run_browser_task
# Import your prompt function
from webEvalAgent.src.prompts import get_ux_evaluation_prompt
# Import log server functions directly
from .log_server import send_log, start_log_server, open_log_dashboard
# For sleep
import asyncio

# Function to get the singleton browser manager instance
def get_browser_manager() -> PlaywrightBrowserManager:
    """Get the singleton browser manager instance.
    
    This function provides a centralized way to access the singleton
    PlaywrightBrowserManager instance throughout the application.
    
    Returns:
        PlaywrightBrowserManager: The singleton browser manager instance
    """
    return PlaywrightBrowserManager.get_instance()

async def handle_web_app_ux_evaluation(arguments: Dict[str, Any], ctx: Context, api_key: str) -> list[TextContent]:
    """Handle web_app_ux_evaluator tool calls
    
    This function evaluates the user experience of a web application by using
    the browser-use agent to perform specific tasks and analyze the interaction flow.
    
    Args:
        arguments: The tool arguments containing 'url' and 'task'
        ctx: The MCP context for reporting progress
        api_key: The API key for authentication with the LLM service
        
    Returns:
        list[TextContent]: The evaluation results, including console logs and network requests
    """
    # Initialize log server immediately (if not already running)
    try:
        # Start the log server right away
        start_log_server()
        # Give the server a moment to start
        await asyncio.sleep(1)
        # Open the dashboard in a new tab
        open_log_dashboard()
        print("Log dashboard initialized and opened")
    except Exception as log_server_error:
        print(f"Warning: Could not start log dashboard: {log_server_error}")
    
    # Validate required arguments
    if "url" not in arguments or "task" not in arguments:
        return [TextContent(
            type="text",
            text="Error: Both 'url' and 'task' parameters are required. Please provide a URL to evaluate and a specific UX/UI task to test."
        )]
    
    url = arguments["url"]
    task = arguments["task"]
    tool_call_id = arguments.get("tool_call_id", str(uuid.uuid4()))
    
    if not url or not isinstance(url, str):
        return [TextContent(
            type="text",
            text="Error: 'url' must be a non-empty string containing the web application URL to evaluate."
        )]
        
    if not task or not isinstance(task, str):
        return [TextContent(
            type="text",
            text="Error: 'task' must be a non-empty string describing the UX/UI aspect to test."
        )]
    
    # Send initial status to dashboard
    send_log(f"🚀 Received UX evaluation task: {task}", "🚀")
    send_log(f"🔗 Target URL: {url}", "🔗")

    # Get the singleton browser manager and initialize it
    browser_manager = get_browser_manager()
    if not browser_manager.is_initialized:
        # Note: browser_manager.initialize will no longer need to start the log server
        # since we've already done it above
        await browser_manager.initialize()
        
    # Get the evaluation task prompt
    evaluation_task = get_ux_evaluation_prompt(url, task)
    send_log(f"📝 Generated evaluation prompt.", "📝")
    
    # Run the browser task
    agent_final_result = None
    try:
        # run_browser_task now only returns the final result string
        agent_final_result = await run_browser_task(
            evaluation_task,
            "claude-3-7-sonnet-latest", # This model name might need update based on browser_utils
            ctx,
            tool_call_id=tool_call_id,
            api_key=api_key
        )

        # Optional: Send the final result from the agent to the dashboard as well
        send_log(f"✅ Agent final result: {agent_final_result}", "✅")

    except Exception as browser_task_error:
        # formatted_steps = f"ERROR    [agent] Error during browser task execution: {browser_task_error}\n"
        error_msg = f"Error during browser task execution: {browser_task_error}\n{traceback.format_exc()}"
        send_log(error_msg, "❌")
        agent_final_result = f"Error: {browser_task_error}" # Provide error as result

    # Return a confirmation message to the MCP user
    # The detailed logs are available on the dashboard
    confirmation_text = f"✅ UX evaluation task initiated for {url}. Final agent state: '{agent_final_result}'. See the 'Operative Control Center' dashboard for detailed live logs."
    send_log(confirmation_text, "✅") # Also send confirmation to dashboard

    return [TextContent(
        type="text",
        text=confirmation_text
    )]
