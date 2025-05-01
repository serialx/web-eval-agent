#!/usr/bin/env python3

import asyncio
import asyncio
import io
import json
import logging
import uuid
import warnings
from contextlib import redirect_stdout, redirect_stderr
from typing import Dict, Any, Tuple, List, Optional
from collections import deque
import pathlib # Added for file reading

# Import log server function
from .log_server import send_log

# Import Playwright types
from playwright.async_api import async_playwright, Error as PlaywrightError, Browser as PlaywrightBrowser, BrowserContext as PlaywrightBrowserContext, Page as PlaywrightPage

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

# This prevents the browser window from stealing focus during execution.
async def _no_bring_to_front(self, *args, **kwargs):
    return None

PlaywrightPage.bring_to_front = _no_bring_to_front
# --- End Patch ---

# Global variable to store agent instance - might be less necessary if Agent is created per task run
agent_instance = None
# Global variable to store the original patched method if patching class-level
original_create_context: Optional[callable] = None

# Define the maximum number of logs/requests to keep
MAX_LOG_ENTRIES = 10

# --- URL Filtering for Network Requests ---
def should_log_network_request(url: str) -> bool:
    """Determine if a network request should be logged based on its URL.
    
    Args:
        url: The URL of the request
        
    Returns:
        bool: True if the request should be logged, False if it should be filtered out
    """
    # Filter out common static assets that aren't usually relevant
    # Add or remove patterns based on your specific needs
    
    # Skip node_modules requests (usually library code)
    if '/node_modules/' in url:
        return False
        
    # Skip common static file types
    extensions_to_filter = [
        '.js', '.css', '.woff', '.woff2', '.ttf', '.eot', '.svg', '.png', 
        '.jpg', '.jpeg', '.gif', '.ico', '.map'
    ]
    
    for ext in extensions_to_filter:
        if url.endswith(ext) or f"{ext}?" in url:  # Handle URLs with query params
            return False
    
    # Always log API endpoints (usually important)
    if '/api/' in url or '/graphql' in url:
        return True
        
    # Log navigation requests (page loads)
    if '?' not in url and '.' not in url.split('/')[-1]:
        return True
    
    # By default, log everything that wasn't filtered
    return True

# --- Log Storage (Global within this module using deque) ---
console_log_storage: deque = deque(maxlen=MAX_LOG_ENTRIES)
network_request_storage: deque = deque(maxlen=MAX_LOG_ENTRIES)

# --- Log Handlers (Use deque's append and send_log with type) ---
async def handle_console_message(message):
    try:
        text = message.text
        log_entry = { "type": message.type, "text": text, "location": message.location, "timestamp": asyncio.get_event_loop().time() }
        console_log_storage.append(log_entry)
        # Send to dashboard with type 'console'
        send_log(f"CONSOLE [{log_entry['type']}]: {log_entry['text']}", "🖥️", log_type='console')
    except Exception as e:
        # Send to dashboard with type 'status' or 'agent' for errors
        send_log(f"Error handling console message: {e}", "❌", log_type='status')

async def handle_request(request):
    try:
        if not should_log_network_request(request.url):
            return
            
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
        network_request_storage.append(request_entry)
        # Send to dashboard with type 'network'
        send_log(f"NET REQ [{request_entry['method']}]: {request_entry['url']}", "➡️", log_type='network')
    except Exception as e:
        url = request.url if request else 'Unknown URL'
        # Send error to dashboard with type 'status' or 'agent'
        send_log(f"Error handling request event for {url}: {e}", "❌", log_type='status')

async def handle_response(response):
    req_id = id(response.request)
    url = response.url
    
    if not should_log_network_request(url):
        return
        
    try:
        try: headers = await response.all_headers()
        except PlaywrightError as e: headers = {"error": f"Resp Header Error: {e}"}
        except Exception as e: headers = {"error": f"Unexpected Resp Header Error: {e}"}
        status = response.status

        body_size = -1
        try:
            body_buffer = await response.body()
            body_size = len(body_buffer) if body_buffer else 0
        except Exception as e: print(f"Warning: Unexpected error getting response body size for {url}: {e}")

        for req in network_request_storage:
            if req.get("id") == req_id and "response_status" not in req:
                req["response_status"] = status
                req["response_headers"] = headers
                req["response_body_size"] = body_size
                req["response_timestamp"] = asyncio.get_event_loop().time()
                # Send to dashboard with type 'network'
                send_log(f"NET RESP [{status}]: {url}", "⬅️", log_type='network')
                break
        else:
            # Send unmatched response to dashboard with type 'network'
             send_log(f"NET RESP* [{status}]: {url} (req not matched/updated)", "⬅️", log_type='network')
    except Exception as e:
        # Send error to dashboard with type 'status' or 'agent'
        send_log(f"Error handling response event for {url}: {e}", "❌", log_type='status')

# Read the JavaScript overlay code from the file
try:
    overlay_js_path = pathlib.Path(__file__).parent / 'agent_overlay.js'
    AGENT_CONTROL_OVERLAY_JS = overlay_js_path.read_text(encoding='utf-8')
except Exception as e:
    send_log(f"CRITICAL ERROR: Failed to read agent_overlay.js: {e}", "🚨", log_type='status')
    AGENT_CONTROL_OVERLAY_JS = "console.error('Failed to load agent overlay script');" # Fallback

# Function to inject the agent control overlay into a page
async def inject_agent_control_overlay(page: PlaywrightPage):
    """Inject the agent control overlay into a page."""
    try:
        # First try with evaluate
        try:
            # send_log("Attempting to inject overlay with page.evaluate()...", "🔄", log_type='status')
            await page.evaluate(AGENT_CONTROL_OVERLAY_JS)
            # send_log("Agent control overlay injected with page.evaluate().", "🎮", log_type='status')
            return
        except Exception as e1:
            send_log(f"Failed to inject with page.evaluate(): {e1}", "⚠️", log_type='status')
            
        # Try with add_script_tag as fallback
        try:
            # send_log("Attempting to inject overlay with page.add_script_tag()...", "🔄", log_type='status')
            await page.add_script_tag(content=AGENT_CONTROL_OVERLAY_JS)
            # send_log("Agent control overlay injected with page.add_script_tag().", "🎮", log_type='status')
            return
        except Exception as e2:
            send_log(f"Failed to inject with page.add_script_tag(): {e2}", "⚠️", log_type='status')
            
        # Try with evaluate_handle as last resort
        try:
            # send_log("Attempting to inject overlay with page.evaluate_handle()...", "🔄", log_type='status')
            await page.evaluate_handle(f"() => {{ {AGENT_CONTROL_OVERLAY_JS} }}")
            # send_log("Agent control overlay injected with page.evaluate_handle().", "🎮", log_type='status')
            return
        except Exception as e3:
            send_log(f"Failed to inject with page.evaluate_handle(): {e3}", "⚠️", log_type='status')
            raise Exception(f"All injection methods failed: {e1}, {e2}, {e3}")
            
    except Exception as e:
        send_log(f"Failed to inject agent control overlay: {e}", "❌", log_type='status')

# Function to set up agent control functions for a page
async def setup_page_agent_controls(page: PlaywrightPage):
    """Set up agent control functions for a page."""
    global agent_instance
    
    try:
        # Expose agent control functions to the page
        await page.expose_function('pauseAgent', lambda: pause_agent())
        await page.expose_function('resumeAgent', lambda: resume_agent())
        await page.expose_function('stopAgent', lambda: stop_agent())
        await page.expose_function('getAgentState', lambda: get_agent_state())
        
        # Inject the agent control overlay
        await inject_agent_control_overlay(page)
        
        # Add navigation listener to re-inject overlay after navigation
        async def handle_frame_navigation(frame):
            if frame is page.main_frame:
                send_log(f"Page navigated to: {page.url}", "🧭", log_type='status')
                # Wait a bit for the page to stabilize after navigation
                await asyncio.sleep(0.5)
                await inject_agent_control_overlay(page)
        
        # Listen for framenavigated events
        page.on("framenavigated", lambda frame: asyncio.create_task(handle_frame_navigation(frame)))
        send_log("Added navigation listener to page", "🔄", log_type='status')
        
        # Also listen for load events to re-inject the overlay
        async def handle_load():
            send_log(f"Page load event on: {page.url}", "🔄", log_type='status')
            await asyncio.sleep(0.5)  # Wait a bit for the page to stabilize
            await inject_agent_control_overlay(page)
            
        page.on("load", lambda: asyncio.create_task(handle_load()))
        send_log("Added load event listener to page", "🔄", log_type='status')
        
    except Exception as e:
        send_log(f"Failed to set up agent controls: {e}", "❌", log_type='status')

# Agent control functions
def pause_agent():
    """Pause the agent."""
    global agent_instance
    if agent_instance:
        agent_instance.pause()
        send_log("Agent paused by user via overlay", "⏸️", log_type='status')
        return True
    return False

def resume_agent():
    """Resume the agent."""
    global agent_instance
    if agent_instance:
        agent_instance.resume()
        send_log("Agent resumed by user via overlay", "▶️", log_type='status')
        return True
    return False

def stop_agent():
    """Stop the agent."""
    global agent_instance
    if agent_instance:
        agent_instance.stop()
        send_log("Agent stopped by user via overlay", "⏹️", log_type='status')
        return True
    return False

def get_agent_state():
    """Get the agent state."""
    global agent_instance
    if agent_instance:
        return {
            'paused': agent_instance.state.paused,
            'stopped': agent_instance.state.stopped
        }
    return {
        'paused': False,
        'stopped': False
    }

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
    import traceback # Make sure traceback is imported for error logging

    # --- Clear Logs for this Run ---
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
        send_log("Playwright initialized for task.", "🎭", log_type='status') # Type: status

        # --- Create browser-use Browser ---
        browser_config = BrowserConfig(disable_security=True, headless=False)
        agent_browser = Browser(config=browser_config)
        agent_browser.playwright = playwright
        agent_browser.playwright_browser = playwright_browser
        send_log("Linked Playwright to agent browser.", "🔗", log_type='status') # Type: status

        # --- Patch BrowserContext._create_context ---
        # Store original only if not already stored (first run)
        if original_create_context is None:
            original_create_context = BrowserContext._create_context
            local_original_create_context = original_create_context # Also store for finally block
        else:
            # Already patched, just ensure we have a reference for finally
            local_original_create_context = original_create_context

        async def patched_create_context(self: BrowserContext, browser_pw: PlaywrightBrowser) -> PlaywrightBrowserContext:
            if original_create_context is None:
                 raise RuntimeError("Original _create_context not stored correctly")

            raw_playwright_context: PlaywrightBrowserContext = await original_create_context(self, browser_pw)
            # send_log("BrowserContext patched, attaching log handlers...", "🔧", log_type='status') # Type: status

            if raw_playwright_context:
                raw_playwright_context.on("console", handle_console_message) # Handlers now send correct type
                raw_playwright_context.on("request", handle_request)         # Handlers now send correct type
                raw_playwright_context.on("response", handle_response)       # Handlers now send correct type
                
                # Set up agent controls for existing pages
                for page in raw_playwright_context.pages:
                    await setup_page_agent_controls(page)
                
                # Set up agent controls for new pages
                raw_playwright_context.on("page", lambda page: asyncio.create_task(setup_page_agent_controls(page)))
                
                send_log("Log listeners and agent controls attached.", "👂", log_type='status') # Type: status
            else:
                 send_log("Original _create_context did not return a context.", "⚠️", log_type='status') # Type: status

            return raw_playwright_context

        BrowserContext._create_context = patched_create_context

        # --- Ensure Tool Call ID ---
        if tool_call_id is None:
            tool_call_id = str(uuid.uuid4())
            send_log(f"Generated tool_call_id: {tool_call_id}", "🆔", log_type='status') # Type: status

        # --- LLM Setup ---
        from .env_utils import get_backend_url
        
        llm = ChatAnthropic(model="claude-3-5-sonnet-20240620",
            base_url=get_backend_url(f"v1beta/models/claude-3-5-sonnet-20240620"),
            extra_headers={
                "x-operative-api-key": api_key,
                "x-operative-tool-call-id": tool_call_id
            })
        send_log(f"LLM ({llm.model}) configured.", "🤖", log_type='status') # Type: status

        # --- Agent Callback ---
        async def state_callback(browser_state, agent_output, step_number):
            global agent_instance # Ensure we have access to the agent

            # Send agent output with type 'agent'
            send_log(f"Step {step_number}", "📍", log_type='agent')
            send_log(f"URL: {browser_state.url}", "🔗", log_type='agent')

            # Re-inject the overlay after each step using the agent's current page
            try:
                if agent_instance and agent_instance.browser_context:
                    # Use the provided helper method to get the current page
                    current_page: Optional[PlaywrightPage] = await agent_instance.browser_context.get_current_page()

                    if current_page:
                        send_log(f"Re-injecting overlay after step {step_number} into page {current_page.url}", "🔄", log_type='status')
                        await inject_agent_control_overlay(current_page)
                    else:
                        send_log(f"Could not get current page from agent context for step {step_number}", "⚠️", log_type='status')
                else:
                     send_log(f"Agent instance or browser context not available for step {step_number}", "⚠️", log_type='status')

            except Exception as e:
                # Add traceback for debugging other potential errors
                import traceback
                tb_str = traceback.format_exc()
                send_log(f"Failed to re-inject overlay after step: {e}\n{tb_str}", "⚠️", log_type='status')

            # Ensure agent_output is a string before logging
            output_str = str(agent_output)
            send_log(f"Agent Output: {output_str}", "💬", log_type='agent')

        # --- Initialize and Run Agent ---
        agent = Agent(
            task=task,
            llm=llm,
            browser=agent_browser,
            register_new_step_callback=state_callback
        )
        agent_instance = agent

        send_log(f"Agent starting task: {task}", "🏃", log_type='agent') # Type: agent
        agent_result = await agent.run()
        send_log(f"Agent run finished.", "🏁", log_type='agent') # Type: agent

        # --- Prepare Combined Results ---
        # Convert AgentHistoryList to a serializable format (just stringify)
        serialized_result = str(agent_result)

        # Return only the agent result
        return serialized_result

    except Exception as e:
        error_message = f"Error in run_browser_task: {e}\n{traceback.format_exc()}"
        send_log(error_message, "❌", log_type='status') # Type: status
        return error_message
    finally:
        # --- Cleanup ---
        # Ensure patch is restored
        if local_original_create_context:
            BrowserContext._create_context = local_original_create_context
            send_log("Original BrowserContext restored.", "🔧", log_type='status') # Type: status

        # Close the browser created specifically for this task
        if agent_browser:
            await agent_browser.close()
            agent_browser = None
            send_log("Agent browser resources cleaned up.", "🧹", log_type='status') # Type: status
        # Close the playwright instance started for this task
        if playwright:
            await playwright.stop()
            playwright = None
            send_log("Playwright instance for task stopped.", "🧹", log_type='status') # Type: status

        # Clear the global instance if it was set
        agent_instance = None

# Note: Removed cleanup_resources() function as cleanup is now in finally block
# async def cleanup_resources() -> None:
#     ...
