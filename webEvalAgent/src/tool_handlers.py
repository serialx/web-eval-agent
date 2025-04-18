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
        error_msg = f"Error during browser task execution: {browser_task_error}\n{traceback.format_exc()}"
        send_log(error_msg, "❌")
        agent_final_result = f"Error: {browser_task_error}" # Provide error as result

    # Format the agent result in a more user-friendly way
    formatted_result = format_agent_result(agent_final_result, url, task)
    
    # Return a better formatted message to the MCP user
    # Including a reference to the dashboard for detailed logs
    confirmation_text = f"{formatted_result}\n\n👁️ See the 'Operative Control Center' dashboard for detailed live logs."
    send_log(confirmation_text, "✅") # Also send confirmation to dashboard

    return [TextContent(
        type="text",
        text=confirmation_text
    )]

def format_agent_result(result_str: str, url: str, task: str) -> str:
    """Format the agent result in a readable way with emojis.
    
    Args:
        result_str: Raw string representation of the agent result
        url: The URL that was evaluated
        task: The task that was executed
        
    Returns:
        str: Formatted result with steps and conclusion
    """
    # Start with a header
    formatted = f"📊 UX Evaluation Report for {url}\n"
    formatted += f"📝 Task: {task}\n\n"
    
    # Check if there's an error
    if result_str.startswith("Error:"):
        return f"{formatted}❌ {result_str}"
    
    # Try to extract action results from the string
    try:
        # Look for the all_results list in the string
        # This approach is more reliable than regex for simple extraction
        if "all_results=[" in result_str:
            # Get the part between all_results=[ and the next ]
            results_part = result_str.split("all_results=[")[1].split("]")[0]
            
            # Split by ActionResult to get individual results
            action_results = results_part.split("ActionResult(")
            
            # Skip the first empty item
            action_results = [r for r in action_results if r.strip()]
            
            # Format steps with emojis
            formatted += "🔍 Agent Steps:\n"
            
            for i, action in enumerate(action_results):
                # Extract the extracted_content which contains the step description
                if "extracted_content=" in action:
                    content_part = action.split("extracted_content=")[1].split(",")[0]
                    # Clean up the content
                    content = content_part.strip("'\"")
                    
                    # Skip None values
                    if content == "None":
                        continue
                        
                    # Check if there's an error
                    if "error=" in action and not "error=None" in action:
                        error_part = action.split("error=")[1].split(",")[0]
                        error = error_part.strip("'\"")
                        if error != "None":
                            formatted += f"  ❌ Step {i+1}: {error}\n"
                            continue
                    
                    # Add emoji if not present
                    if not content.startswith(("🔗", "🖱️", "⌨️", "🔍", "✅", "❌", "⚠️")):
                        content = f"✅ {content}"
                        
                    formatted += f"  {content}\n"
        
        # Try to extract the final conclusion (usually in the 'done' step)
        # The last action result with is_done=True usually contains the conclusion
        if "is_done=True" in result_str:
            done_parts = result_str.split("is_done=True")
            for done_part in done_parts:
                if "extracted_content=" in done_part:
                    content = done_part.split("extracted_content=")[1].split(",")[0].strip("'\"")
                    if content and content != "None":
                        formatted += f"\n🏁 Conclusion:\n{content}\n"
                        break
        
    except Exception as e:
        # If parsing fails, return a simpler message with the raw result
        return f"{formatted}⚠️ Result parsing failed: {e}\nRaw result: {result_str[:200]}...\n"
    
    return formatted
