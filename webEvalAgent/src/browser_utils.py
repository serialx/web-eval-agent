#!/usr/bin/env python3

import asyncio
import io
import json
import logging
import uuid
import warnings
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, Any, Tuple, List, Optional
from collections import deque

# Import log server function
from .log_server import send_log

# Import Playwright types
from playwright.async_api import async_playwright, Error as PlaywrightError, Browser as PlaywrightBrowser, BrowserContext as PlaywrightBrowserContext

# Local imports (assuming browser_manager is potentially still used for singleton logic elsewhere, or can be removed if fully replaced)
# from browser_manager import PlaywrightBrowserManager # Commented out if not needed

# Browser-use imports
from browser_use.agent.service import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext # Import BrowserContext

# Langchain/MCP imports
from langchain_anthropic import ChatAnthropic
from mcp.server.fastmcp import Context
from langchain.globals import set_verbose

# Global variable to store agent instance - might be less necessary if Agent is created per task run
agent_instance = None
# Global variable to store the original patched method if patching class-level
original_create_context: Optional[callable] = None

# Define the maximum number of logs/requests to keep
MAX_LOG_ENTRIES = 10

# --- Log Storage (Global within this module using deque) ---
console_log_storage: deque = deque(maxlen=MAX_LOG_ENTRIES)
network_request_storage: deque = deque(maxlen=MAX_LOG_ENTRIES)

# --- Log Handlers (Use deque's append) ---
async def handle_console_message(message):
    try:
        text = message.text
        log_entry = { "type": message.type, "text": text, "location": message.location, "timestamp": asyncio.get_event_loop().time() }
        # Appending to deque automatically handles maxlen
        console_log_storage.append(log_entry)
        # print(f"-> CONSOLE LOG ({len(console_log_storage)}/{MAX_LOG_ENTRIES}): {log_entry['type']} - {log_entry['text'][:150]}") # Updated debug print
        # Send to dashboard
        send_log(f"🖥️ CONSOLE [{log_entry['type']}]: {log_entry['text']}", "🖥️")
    except Exception as e:
        # print(f"Error handling console message: {e} - Args: {message.args}")
        send_log(f"❌ Error handling console message: {e}", "❌")

async def handle_request(request):
    try:
        try: headers = await request.all_headers()
        except PlaywrightError as e: headers = {"error": f"Req Header Error: {e}"}
        except Exception as e: headers = {"error": f"Unexpected Req Header Error: {e}"}

        post_data = None
        try:
            if request.post_data:
                 post_data_buffer = await request.post_data_buffer()
                 if post_data_buffer:
                     try: post_data = post_data_buffer.decode('utf-8', errors='replace')
                     except Exception: post_data = repr(post_data_buffer)
                 else: post_data = ""
            else: post_data = None
        except PlaywrightError as e: post_data = f"Post Data Error: {e}"
        except Exception as e: post_data = f"Unexpected Post Data Error: {e}"

        request_entry = { "url": request.url, "method": request.method, "headers": headers, "postData": post_data, "timestamp": asyncio.get_event_loop().time(), "resourceType": request.resource_type, "is_navigation": request.is_navigation_request(), "id": id(request) }
        # Appending to deque automatically handles maxlen
        network_request_storage.append(request_entry)
        # print(f"-> NETWORK REQ ({len(network_request_storage)}/{MAX_LOG_ENTRIES}): {request_entry['method']} {request_entry['url']}") # Updated debug print
        # Send to dashboard
        send_log(f"➡️ NET REQ [{request_entry['method']}]: {request_entry['url']}", "➡️")
    except Exception as e:
        # print(f"Error handling request event for {request.url if request else 'Unknown URL'}: {e}")
        url = request.url if request else 'Unknown URL'
        send_log(f"❌ Error handling request event for {url}: {e}", "❌")

async def handle_response(response):
    req_id = id(response.request)
    url = response.url
    try:
        try: headers = await response.all_headers()
        except PlaywrightError as e: headers = {"error": f"Resp Header Error: {e}"}
        except Exception as e: headers = {"error": f"Unexpected Resp Header Error: {e}"}
        status = response.status

        body_size = -1
        try:
            body_buffer = await response.body()
            body_size = len(body_buffer) if body_buffer else 0
        except PlaywrightError as e: print(f"Warning: Could not get response body size for {url}: {e}")
        except Exception as e: print(f"Warning: Unexpected error getting response body size for {url}: {e}")

        # Iterate through the deque (which contains dicts)
        # Note: Modifying items in a deque while iterating isn't ideal,
        # but finding the specific request dict should be okay here.
        # For very high traffic, a dict lookup might be better.
        for req in network_request_storage:
            if req.get("id") == req_id and "response_status" not in req:
                req["response_status"] = status
                req["response_headers"] = headers
                req["response_body_size"] = body_size
                req["response_timestamp"] = asyncio.get_event_loop().time()
                # print(f"-> NETWORK RESP ({len(network_request_storage)}/{MAX_LOG_ENTRIES}): {status} for {url}") # Updated debug print
                # Send to dashboard
                send_log(f"⬅️ NET RESP [{status}]: {url}", "⬅️")
                break
        else: # If loop finishes without break (request not found/already has response)
            # Log response even if request wasn't matched in our deque (e.g., redirect, cached)
            send_log(f"⬅️ NET RESP* [{status}]: {url} (req not matched/updated)", "⬅️")
    except Exception as e:
        # print(f"Error handling response event for {url}: {e}")
        send_log(f"❌ Error handling response event for {url}: {e}", "❌")


async def run_browser_task(task: str, model: str = "gemini-2.0-flash-001", ctx: Context = None, tool_call_id: str = None, api_key: str = None) -> str:
    """
    Run a task using browser-use agent, sending logs to the dashboard.

    Args:
        task: The task to run.
        model: The model identifier (not directly used for LLM here, taken from ChatAnthropic).
        ctx: The MCP context for progress reporting.
        tool_call_id: The tool call ID for API headers.
        api_key: The API key for authentication.

    Returns:
        str: Agent's final result (stringified).
    """
    global agent_instance, console_log_storage, network_request_storage, original_create_context

    # --- Clear Logs for this Run ---
    # Deques are cleared like lists
    console_log_storage.clear()
    network_request_storage.clear()

    # Local Playwright variables for this run
    playwright = None
    playwright_browser = None
    agent_browser = None # browser-use Browser instance
    local_original_create_context = None # To store original method for this run's finally block

    # Configure logging suppression
    logging.basicConfig(level=logging.CRITICAL) # Set root logger level first
    # Then configure specific loggers
    for logger_name in ['browser_use', 'root', 'agent', 'browser']:
        # Get the logger for the current name and set its level
        current_logger = logging.getLogger(logger_name)
        current_logger.setLevel(logging.CRITICAL)

    warnings.filterwarnings("ignore", category=UserWarning)
    set_verbose(False)

    try:
        # --- Initialize Playwright Directly ---
        playwright = await async_playwright().start()
        playwright_browser = await playwright.chromium.launch(headless=False)
        # print("Playwright initialized directly.")
        send_log("🎭 Playwright initialized for task.", "🎭")

        # --- Create browser-use Browser ---
        browser_config = BrowserConfig(disable_security=True, headless=False)
        agent_browser = Browser(config=browser_config)
        agent_browser.playwright = playwright
        agent_browser.playwright_browser = playwright_browser
        # print("Assigned direct Playwright objects to agent_browser.")
        send_log("🔗 Linked Playwright to agent browser.", "🔗")

        # --- Patch BrowserContext._create_context ---
        # Store original only if not already stored (first run)
        if original_create_context is None:
            original_create_context = BrowserContext._create_context
            local_original_create_context = original_create_context # Also store for finally block
        else:
            # Already patched, just ensure we have a reference for finally
            local_original_create_context = original_create_context


        async def patched_create_context(self: BrowserContext, browser_pw: PlaywrightBrowser) -> PlaywrightBrowserContext:
            # Use the globally stored original method
            if original_create_context is None:
                 raise RuntimeError("Original _create_context not stored correctly") # Should not happen

            # print("Patched BrowserContext._create_context called...") # Reduce noise
            raw_playwright_context: PlaywrightBrowserContext = await original_create_context(self, browser_pw)
            # print(f"Original _create_context created raw context: {raw_playwright_context}") # Reduce noise
            send_log("🔧 BrowserContext patched, attaching log handlers...", "🔧")

            if raw_playwright_context:
                raw_playwright_context.on("console", handle_console_message)
                raw_playwright_context.on("request", handle_request)
                raw_playwright_context.on("response", handle_response)
                # print("Listeners attached to raw Playwright context.") # Reduce noise
                send_log("👂 Log listeners attached.", "👂")
            else:
                 # print("!!! Warning: Original _create_context did not return a context.")
                 send_log("⚠️ Original _create_context did not return a context.", "⚠️")

            return raw_playwright_context

        # Apply the patch (idempotent if already patched)
        BrowserContext._create_context = patched_create_context
        # print("Patched BrowserContext._create_context.") # Reduce noise

        # --- Ensure Tool Call ID ---
        if tool_call_id is None:
            tool_call_id = str(uuid.uuid4())
            # print(f"Generated new tool_call_id in run_browser_task: {tool_call_id}")
            send_log(f"🆔 Generated tool_call_id: {tool_call_id}", "🆔")

        # --- LLM Setup ---
        llm = ChatAnthropic(model="claude-3-5-sonnet-20240620",
            base_url="https://operative-backend.onrender.com/v1beta/models/claude-3-5-sonnet-20240620",
            extra_headers={
                "x-operative-api-key": api_key,
                "x-operative-tool-call-id": tool_call_id
            })
        send_log(f"🤖 LLM ({llm.model}) configured.", "🤖")

        # --- Agent Callback ---
        async def state_callback(browser_state, agent_output, step_number):
            # Instead of appending, send log directly
            # step_history.append({
            #     "step": step_number,
            #     "url": browser_state.url,
            #     "output": agent_output
            # })
            send_log(f"📍 Step {step_number}", "📍")
            send_log(f"🔗 URL: {browser_state.url}", "🔗")
            send_log(f"💬 Agent Output: {agent_output}", "💬")

        # --- Initialize and Run Agent ---
        agent = Agent(
            task=task,
            llm=llm,
            browser=agent_browser,
            register_new_step_callback=state_callback
        )
        agent_instance = agent # Store globally if needed elsewhere

        # print(f"Agent starting task: {task}")
        send_log(f"🏃 Agent starting task: {task}", "🏃")
        agent_result = await agent.run() # Agent returns AgentHistoryList
        send_log(f"🏁 Agent run finished.", "🏁")

        # --- Final Log Summary (Remove, logs are live) ---
        # print("\n--- Final Log Summary ---")
        # final_console_logs = list(console_log_storage)
        # final_network_requests = list(network_request_storage)
        # print(f"Total Console Logs Captured (max {MAX_LOG_ENTRIES}): {len(final_console_logs)}")
        # print(f"Total Network Requests Captured (max {MAX_LOG_ENTRIES}): {len(final_network_requests)}")
        # if final_console_logs: print("\nSample Console Logs (Last 5):\n" + "\n".join([f"- {l.get('type','?').ljust(8)}: {l.get('text','?')[:150]}" for l in final_console_logs[-5:]]))
        # if final_network_requests: print("\nSample Network Requests (Last 5):\n" + "\n".join([f"- {r.get('method','?').ljust(4)} {r.get('response_status','???')} {r.get('url','?')}" for r in final_network_requests[-5:]]))

        # --- Prepare Combined Results ---
        # Convert AgentHistoryList to a serializable format (just stringify)
        serialized_result = str(agent_result)

        # Remove old log returns
        # console_logs_json = json.dumps(final_console_logs, default=str) # Use default=str for non-serializable items
        # network_requests_json = json.dumps(final_network_requests, default=str)

        # Return only the agent result
        return serialized_result

    except Exception as e:
        # print(f"Error in run_browser_task: {e}")
        # print(traceback.format_exc())
        error_message = f"Error in run_browser_task: {e}\n{traceback.format_exc()}"
        send_log(error_message, "❌")
        # Return error message instead of logs
        return error_message
    finally:
        # --- Cleanup ---
        # Ensure patch is restored
        if local_original_create_context:
            BrowserContext._create_context = local_original_create_context
            # print("Restored original BrowserContext._create_context.")
            send_log("🔧 Original BrowserContext restored.", "🔧")

        # Close the browser created specifically for this task
        if agent_browser:
            await agent_browser.close()
            agent_browser = None
            send_log("🧹 Agent browser resources cleaned up.", "🧹")
        # Close the playwright instance started for this task
        if playwright:
            await playwright.stop()
            playwright = None
            send_log("🧹 Playwright instance for task stopped.", "🧹")

        # Clear the global instance if it was set
        agent_instance = None

# Note: Removed cleanup_resources() function as cleanup is now in finally block
# async def cleanup_resources() -> None:
#     ...
