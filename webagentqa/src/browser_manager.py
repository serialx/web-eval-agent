#!/usr/bin/env python3

import asyncio
from typing import Dict, List, Optional
import logging

class PlaywrightBrowserManager:
    # Class variable to hold the singleton instance
    _instance: Optional['PlaywrightBrowserManager'] = None
    
    @classmethod
    def get_instance(cls) -> 'PlaywrightBrowserManager':
        """Get or create the singleton instance of PlaywrightBrowserManager."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        # Check if an instance already exists
        if PlaywrightBrowserManager._instance is not None:
            logging.warning("PlaywrightBrowserManager is a singleton. Use get_instance() instead.")
            return
            
        # Set this instance as the singleton
        PlaywrightBrowserManager._instance = self
        
        self.playwright = None
        self.browser = None
        self.page = None
        self.console_logs = []
        self.network_requests = []
        self.is_initialized = False

    async def initialize(self) -> None:
        """Initialize the Playwright browser if not already initialized."""
        if self.is_initialized:
            return
            
        # Import here to avoid module import issues
        import asyncio
        from playwright.async_api import async_playwright

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()
        self.is_initialized = True

    async def close(self) -> None:
        """Close the browser and Playwright instance."""
        if self.page:
            await self.page.close()
            self.page = None
            
        if self.browser:
            await self.browser.close()
            self.browser = None
            
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
            
        self.is_initialized = False
        self.console_logs = []
        self.network_requests = []

    async def open_url(self, url: str) -> str:
        """Open a URL in the browser and start monitoring console and network.
        The browser will stay open for user interaction."""
        if not self.is_initialized:
            await self.initialize()
            
        # Close existing page if any
        if self.page:
            await self.page.close()
            
        # Clear previous logs and requests
        self.console_logs = []
        self.network_requests = []
        
        # Create a new page
        self.page = await self.browser.new_page()
        
        # Set up console log listener
        self.page.on("console", lambda message: asyncio.create_task(self._handle_console_message(message)))
        
        # Set up network request listener
        self.page.on("request", lambda request: asyncio.create_task(self._handle_request(request)))
        self.page.on("response", lambda response: asyncio.create_task(self._handle_response(response)))
        
        # Navigate to the URL
        await self.page.goto(url, wait_until="networkidle")
        
        return f"Opened {url} successfully. The browser window will remain open for you to interact with."

    async def _handle_console_message(self, message) -> None:
        """Handle console messages from the page."""
        log_entry = {
            "type": message.type,
            "text": message.text,
            "location": message.location,
            "timestamp": asyncio.get_event_loop().time()
        }
        self.console_logs.append(log_entry)

    async def _handle_request(self, request) -> None:
        """Handle network requests."""
        request_entry = {
            "url": request.url,
            "method": request.method,
            "headers": request.headers,
            "timestamp": asyncio.get_event_loop().time(),
            "resourceType": request.resource_type,
            "id": id(request)
        }
        self.network_requests.append(request_entry)

    async def _handle_response(self, response) -> None:
        """Handle network responses."""
        # Find the matching request and update it with response data
        for request in self.network_requests:
            if request.get("url") == response.url and "response" not in request:
                request["response"] = {
                    "status": response.status,
                    "statusText": response.status_text,
                    "headers": response.headers,
                    "timestamp": asyncio.get_event_loop().time()
                }
                break

    async def get_console_logs(self, last_n: int) -> List[Dict]:
        """Get console logs collected so far with deduplication of repeated messages."""
        if not self.console_logs:
            return []
            
        # Create a deduplicated version of the logs
        deduplicated_logs = []
        current_group = None
        
        # Sort logs by timestamp to ensure proper grouping
        sorted_logs = sorted(self.console_logs, key=lambda x: x.get('timestamp', 0))
        
        for log in sorted_logs:
            # If we have no current group or this log is different from the current group
            if (current_group is None or 
                log['type'] != current_group['type'] or 
                log['text'] != current_group['text']):
                
                # Start a new group
                current_group = {
                    'type': log['type'],
                    'text': log['text'],
                    'location': log['location'],
                    'timestamp': log['timestamp'],
                    'count': 1,
                    'timestamps': [log['timestamp']]
                }
                deduplicated_logs.append(current_group)
            else:
                # This is a repeated message, increment count and add timestamp
                current_group['count'] += 1
                current_group['timestamps'].append(log['timestamp'])
                # Update the text to show repetition count for repeated messages
                if current_group['count'] > 1:
                    current_group['text'] = f"{log['text']} (repeated {current_group['count']} times)"
        
        # Return only the last N entries
        # Sort by timestamp (descending) to get the most recent logs first
        deduplicated_logs.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        deduplicated_logs = deduplicated_logs[:last_n]
        # Sort back by timestamp (ascending) for consistent output
        deduplicated_logs.sort(key=lambda x: x.get('timestamp', 0))
        
        return deduplicated_logs

    async def get_network_requests(self, last_n: int) -> List[Dict]:
        """Get network requests collected so far."""
        if not self.network_requests:
            return []
            
        # Sort by timestamp (descending) to get the most recent requests first
        sorted_requests = sorted(self.network_requests, key=lambda x: x.get('timestamp', 0), reverse=True)
        # Take only the last N entries
        limited_requests = sorted_requests[:last_n]
        # Sort back by timestamp (ascending) for consistent output
        limited_requests.sort(key=lambda x: x.get('timestamp', 0))
        
        return limited_requests
        
    def get_browser(self):
        """Get the browser instance to pass to the Agent."""
        if not self.is_initialized:
            raise RuntimeError("Browser manager not initialized. Call initialize() first.")
        return self.browser
