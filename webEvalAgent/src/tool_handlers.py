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
from webEvalAgent.src.browser_utils import run_browser_task, console_log_storage, network_request_storage
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

    # Format the agent result in a more user-friendly way, including console and network errors
    formatted_result = format_agent_result(agent_final_result, url, task, console_log_storage, network_request_storage)
    
    # Determine if the task was successful
    task_succeeded = True
    if agent_final_result.startswith("Error:"):
        task_succeeded = False
    elif "success=False" in agent_final_result and "is_done=True" in agent_final_result:
        task_succeeded = False
    
    # Use appropriate status emoji
    status_emoji = "✅" if task_succeeded else "❌"
    
    # Return a better formatted message to the MCP user
    # Including a reference to the dashboard for detailed logs
    confirmation_text = f"{formatted_result}\n\n👁️ See the 'Operative Control Center' dashboard for detailed live logs."
    send_log(f"UX evaluation task completed for {url}.", status_emoji) # Also send confirmation to dashboard

    return [TextContent(
        type="text",
        text=confirmation_text
    )]

def format_agent_result(result_str: str, url: str, task: str, console_logs=None, network_requests=None) -> str:
    """Format the agent result in a readable way with emojis.
    
    Args:
        result_str: Raw string representation of the agent result
        url: The URL that was evaluated
        task: The task that was executed
        console_logs: Collected console logs from the browser
        network_requests: Collected network requests from the browser
        
    Returns:
        str: Formatted result with steps and conclusion
    """
    # Start with a header
    formatted = f"📊 UX Evaluation Report for {url}\n"
    formatted += f"📝 Task: {task}\n\n"
    
    # Check if there's an error
    if result_str.startswith("Error:"):
        return f"{formatted}❌ {result_str}"
    
    # Flag to track if the task was successful
    task_succeeded = True
    
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
            
            # Check if the final action has success=False
            for action in action_results:
                if "is_done=True" in action:
                    if "success=False" in action:
                        task_succeeded = False
                    break
            
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
                            task_succeeded = False
                            continue
                    
                    # Check if this is a final message/conclusion step
                    is_final_message = "is_done=True" in action
                    
                    # Add emoji if not present, using a different emoji for the final message
                    if not content.startswith(("🔗", "🖱️", "⌨️", "🔍", "✅", "❌", "⚠️", "🏁")):
                        if is_final_message:
                            # Use a "finished" emoji rather than a checkmark for the completion message
                            content = f"🏁 {content}"
                        else:
                            content = f"✅ {content}"
                    
                    # If it has a checkmark but is a final message, replace with completion emoji
                    if content.startswith("✅") and is_final_message:
                        content = "🏁" + content[1:]
                        
                    formatted += f"  {content}\n"
        
        # Look for the 'done' action in the model outputs to extract the conclusion
        conclusion = ""
        if "'done':" in result_str or "\"done\":" in result_str:
            # Try to find the 'done' action and its text
            done_match = None
            if "'done':" in result_str:
                done_parts = result_str.split("'done':")[1].split("}")[0]
                done_match = done_parts
            elif "\"done\":" in result_str:
                done_parts = result_str.split("\"done\":")[1].split("}")[0]
                done_match = done_parts
                
            if done_match:
                # Extract the 'text' field from the done action
                if "'text':" in done_match:
                    text_part = done_match.split("'text':")[1].split(",")[0]
                    conclusion = text_part.strip("' \"")
                elif "\"text\":" in done_match:
                    text_part = done_match.split("\"text\":")[1].split(",")[0]
                    conclusion = text_part.strip("' \"")
                
                # Also check for success field in the done action
                if "'success': False" in done_match or "\"success\": False" in done_match:
                    task_succeeded = False
        
        # If we still don't have a conclusion, try the original method as fallback
        if not conclusion and "is_done=True" in result_str:
            for action in action_results:
                if "is_done=True" in action and "extracted_content=" in action:
                    content = action.split("extracted_content=")[1].split(",")[0].strip("'\"")
                    if content and content != "None":
                        conclusion = content
                        break
        
        # Add conclusion with appropriate status emoji
        if conclusion:
            # Use a neutral conclusion emoji instead of success/failure indicator
            formatted += f"\n📋 Conclusion:\n{conclusion}\n"
        
        # Add console errors if available
        if console_logs:
            console_errors = []
            for log in console_logs:
                if log.get('type') == 'error':
                    console_errors.append(log.get('text', 'Unknown error'))
            
            if console_errors:
                formatted += f"\n🔴 Console Errors ({len(console_errors)}):\n"
                for i, error in enumerate(console_errors[:5]):  # Limit to first 5 errors
                    formatted += f"  {i+1}. {error}\n"
                if len(console_errors) > 5:
                    formatted += f"  ... and {len(console_errors) - 5} more errors\n"
        
        # Add failed network requests if available
        if network_requests:
            failed_requests = []
            for req in network_requests:
                # Check if it's an XHR/fetch request and has a failure status code (4xx or 5xx)
                is_xhr = req.get('resourceType') == 'xhr' or req.get('resourceType') == 'fetch'
                status = req.get('response_status')
                if is_xhr and status and (status >= 400):
                    failed_requests.append({
                        'url': req.get('url', 'Unknown URL'),
                        'method': req.get('method', 'GET'),
                        'status': status
                    })
            
            if failed_requests:
                formatted += f"\n🌐 Failed Network Requests ({len(failed_requests)}):\n"
                for i, req in enumerate(failed_requests[:5]):  # Limit to first 5
                    formatted += f"  {i+1}. {req['method']} {req['url']} - Status: {req['status']}\n"
                if len(failed_requests) > 5:
                    formatted += f"  ... and {len(failed_requests) - 5} more failed requests\n"
    
    except Exception as e:
        # If parsing fails, return a simpler message with the raw result
        return f"{formatted}⚠️ Result parsing failed: {e}\nRaw result: {result_str[:200]}...\n"
    
    return formatted
