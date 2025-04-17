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
    
    # Get the singleton browser manager and initialize it
    browser_manager = get_browser_manager()
    if not browser_manager.is_initialized:
        await browser_manager.initialize()
        
    # Get the evaluation task prompt
    evaluation_task = get_ux_evaluation_prompt(url, task)
    
    # Run the browser task
    log_buffer = io.StringIO()
    formatted_steps = ""
    try:
        with redirect_stdout(log_buffer), redirect_stderr(log_buffer):
            step_history, console_logs_json, network_requests_json = await run_browser_task(
                evaluation_task, 
                "claude-3-7-sonnet-latest", 
                ctx, 
                tool_call_id=tool_call_id,
                api_key=api_key
            )

        # Format the step history
        formatted_steps = "Agent Steps:\n"
        for step_data in step_history:
            step_num = step_data.get('step', 'N/A')
            url = step_data.get('url', 'N/A')
            output_str = step_data.get('output', '')
            
            # Basic formatting - we can refine this if 'output_str' has a known structure
            formatted_steps += f"\nINFO     [agent] 📍 Step {step_num}\n"
            formatted_steps += f"INFO     [agent] 🔗 URL: {url}\n"
            # Try to parse the agent_output string for more details (simple parsing)
            try:
                # Example: Assuming output looks like "AgentBrain(evaluation_previous_goal='...', memory='...', next_goal='...') action=[ActionModel(...)]"
                eval_match = re.search(r"evaluation_previous_goal='([^']*)'", output_str)
                memory_match = re.search(r"memory='([^']*)'", output_str)
                goal_match = re.search(r"next_goal='([^']*)'", output_str)
                action_match = re.search(r"action=\[(.*)\]", output_str) # Captures the content inside action=[...]
                
                if eval_match: formatted_steps += f"INFO     [agent] 🤷 Eval: {eval_match.group(1)}\n"
                if memory_match: formatted_steps += f"INFO     [agent] 🧠 Memory: {memory_match.group(1)}\n"
                if goal_match: formatted_steps += f"INFO     [agent] 🎯 Next goal: {goal_match.group(1)}\n"
                
                if action_match:
                    action_content = action_match.group(1)
                    # Split actions based on ActionModel pattern - crude but might work for simple cases
                    actions = re.findall(r"ActionModel\((.*?)\)", action_content)
                    for i, action_detail in enumerate(actions):
                        # Try to format the action detail (e.g., extract click_element, input_text)
                        action_dict_match = re.search(r"(?:click_element|input_text|send_keys|wait|go_to_url|done)=({.*?})", action_detail)
                        if action_dict_match:
                             formatted_steps += f"INFO     [agent] 🛠️  Action {i+1}/{len(actions)}: {action_dict_match.group(1)}\n"
                        else:
                            # Fallback for actions not matching the expected dict format
                            formatted_steps += f"INFO     [agent] 🛠️  Action {i+1}/{len(actions)}: {action_detail.strip()}\n"
                elif 'output' in step_data: # Fallback if no action found but output exists
                    formatted_steps += f"INFO     [agent] -> Output: {output_str}\n"

            except Exception as parse_error:
                # If parsing fails, just print the raw output
                formatted_steps += f"INFO     [agent] -> Raw Output: {output_str}\n"
                formatted_steps += f"DEBUG    [parser] Error parsing output: {parse_error}\n" # Optional debug info

    except Exception as browser_task_error:
        formatted_steps = f"ERROR    [agent] Error during browser task execution: {browser_task_error}\n"
        console_logs_json = "[]"
        network_requests_json = "[]"
    
    # Get logs captured via redirect_stdout/stderr
    debug_logs = log_buffer.getvalue()
    
    # Combine formatted steps with other logs
    final_text = f"{formatted_steps.strip()}\n\nDebug logs:\n{debug_logs}\n\nConsole logs:\n{console_logs_json}\n\nNetwork requests:\n{network_requests_json}"

    # Return the evaluation result
    return [TextContent(
        type="text",
        text=final_text
    )]
