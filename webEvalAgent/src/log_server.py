#!/usr/bin/env python3

import asyncio
import threading
import webbrowser
from flask import Flask, render_template, send_from_directory, request
from flask_socketio import SocketIO
import logging
import os
from datetime import datetime

# Import the browser manager to call its input handler
# Use a try-except block for graceful handling if the module structure changes
try:
    from .browser_manager import PlaywrightBrowserManager
except ImportError:
    PlaywrightBrowserManager = None
    logging.error("Could not import PlaywrightBrowserManager in log_server.py")

# --- Async mode selection ---
_async_mode = 'threading'

# Configure logging for Flask and SocketIO (optional, can be noisy)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) # Reduce Flask's default logging
logging.getLogger('socketio').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)

# Get the absolute path to the templates directory
templates_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../templates'))
app = Flask(__name__, template_folder=templates_dir, static_folder=os.path.join(templates_dir, 'static'))
app.config['SECRET_KEY'] = 'secret!' # Replace with a proper secret if needed

# Initialise SocketIO with chosen async_mode
socketio = SocketIO(app, cors_allowed_origins="*", async_mode=_async_mode)

# Store connected SIDs
connected_clients = set()

@app.route('/')
def index():
    """Serve the main HTML dashboard page."""
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files (like CSS, JS if added later)."""
    static_folder = os.path.join(os.path.dirname(__file__), '../templates/static')
    return send_from_directory(static_folder, path)

@socketio.on('connect')
def handle_connect():
    # Add client to connected_clients set
    connected_clients.add(request.sid)
    logging.info(f"Client connected: {request.sid}. Total clients: {len(connected_clients)}")
    
    # Send status message to dashboard
    send_log(f"Connected to log server at {datetime.now().strftime('%H:%M:%S')}", "✅", log_type='status')

@socketio.on('disconnect')
def handle_disconnect():
    # Remove client from connected_clients set
    if request.sid in connected_clients:
        connected_clients.remove(request.sid)
    
    logging.info(f"Client disconnected: {request.sid}. Remaining clients: {len(connected_clients)}")
    
    # Send status message to dashboard
    # Use try-except as send_log might fail if server isn't fully ready/shutting down
    try:
        send_log(f"Disconnected from log server at {datetime.now().strftime('%H:%M:%S')}", "❌", log_type='status')
    except Exception as e:
        logging.warning(f"Failed to send disconnect log: {e}")

def send_log(message: str, emoji: str = "➡️", log_type: str = 'agent'):
    """Sends a log message with an emoji prefix and type to all connected clients."""
    # Ensure socketio context is available. If called from a non-SocketIO thread,
    # use socketio.emit directly.
    try:
        log_entry = f"{emoji} {message}"
        # print(f"Attempting to send log ({log_type}): {log_entry}") # Debug print if needed
        # Include log_type in the emitted data
        socketio.emit('log_message', {'data': log_entry, 'type': log_type})
        # print(f"Log emitted ({log_type}): {log_entry}") # Debug print if needed
    except Exception as e:
        # Fallback print if emit fails (e.g., server not running or context issue)
        # Use logging instead of print for consistency
        logging.warning(f"LOG SERVER EMIT FAILED ({log_type}): {emoji} {message} (Error: {e})")

# --- Browser View Update Function ---
async def send_browser_view(image_data_url: str):
    """Sends the browser view image data URL to all connected clients."""
    # This function is async because it might be called from the asyncio loop
    # in browser_manager. However, socketio.emit needs to be called carefully
    # when interacting between asyncio and other threads (like Flask's).
    # socketio.emit is generally thread-safe, but ensure the event loop is handled.
    
    # More detailed logging
    data_preview = image_data_url[:50] + "..." if image_data_url else "None"
    logging.info(f"send_browser_view called. Data length: {len(image_data_url) if image_data_url else 0}")
    logging.debug(f"Data preview: {data_preview}")
    
    # Check if the data URL is valid
    if not image_data_url or not image_data_url.startswith("data:image/"):
        logging.error(f"Invalid image data URL format: {data_preview}")
        return
        
    try:
        logging.info(f"Attempting to emit 'browser_update' via SocketIO to {len(connected_clients)} clients...")
        socketio.emit('browser_update', {'data': image_data_url})
        logging.info(f"SocketIO emit 'browser_update' called successfully.")
        
        # Also send a log message to the dashboard for visibility
        send_log(f"Browser view updated ({len(image_data_url)} bytes)", "📸", log_type='status')
    except Exception as e:
        logging.error(f"BROWSER VIEW EMIT FAILED: {e}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")

# --- Browser Input Handler ---
@socketio.on('browser_input')
def handle_browser_input_event(data):
    """Handles browser interaction events received from the frontend."""
    event_type = data.get('type')
    details = data.get('details')
    logging.debug(f"Received browser_input event via SocketIO: Type={event_type}, Details={details}")

    if not PlaywrightBrowserManager:
        logging.error("PlaywrightBrowserManager not imported, cannot handle browser input.")
        return

    manager = PlaywrightBrowserManager.get_instance()
    if not manager or not manager.is_initialized or not manager.cdp_session:
        logging.warning("Browser manager not ready or no active CDP session, ignoring input.")
        return

    # Since the browser manager runs in an asyncio loop, and this handler
    # likely runs in a separate thread (Flask/SocketIO default), we need
    # to schedule the async input handler function in the manager's loop.
    try:
        # Get the asyncio loop the manager is running on (assuming it's the main one for now)
        # This might need refinement if multiple loops are involved.
        loop = asyncio.get_running_loop()
        # Schedule the coroutine call
        asyncio.run_coroutine_threadsafe(
            manager.handle_browser_input(event_type, details),
            loop
        )
        # print(f"Scheduled handle_browser_input for event: {event_type}") # Debug
    except RuntimeError:
        logging.error("No running asyncio event loop found to schedule browser input.")
    except Exception as e:
        logging.error(f"Error scheduling browser input handler: {e}")


def start_log_server(host='127.0.0.1', port=5009):
    """Starts the Flask-SocketIO server in a background thread."""
    def run_server():
        # print(f"Starting Operative Control Center server on http://{host}:{port}")
        # Use eventlet or gevent for production? For local dev, default Flask dev server is fine.
        # Setting log_output=False to reduce console noise from SocketIO itself
        socketio.run(app, host=host, port=port, log_output=False, use_reloader=False, allow_unsafe_werkzeug=True)

    # Check if templates directory exists
    template_dir = os.path.join(os.path.dirname(__file__), '../templates')
    static_dir = os.path.join(template_dir, 'static')
    
    # Create template directory if it doesn't exist
    if not os.path.exists(template_dir):
        print(f"Warning: Template directory not found at {template_dir}. Creating it.")
        os.makedirs(template_dir)
    
    # Create static directory if it doesn't exist
    if not os.path.exists(static_dir):
        print(f"Warning: Static directory not found at {static_dir}. Creating it.")
        os.makedirs(static_dir)
    
    # Create index.html if it's missing
    index_path = os.path.join(template_dir, 'index.html')
    if not os.path.exists(index_path):
        with open(index_path, 'w') as f:
            f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Operative Control Center</title>
    <link rel="icon" href="https://www.operative.sh/favicon.ico?v=2" type="image/x-icon">
    <script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        'terminal-bg': '#1C1C1C',
                        'terminal-header': '#2A2A2A',
                        'accent-green': '#27C93F',
                    },
                    fontFamily: {
                        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
                        mono: ['"SF Mono"', '"Consolas"', '"Menlo"', 'monospace'],
                    }
                }
            }
        }
    </script>
</head>
<body class="bg-black text-gray-300 font-sans flex flex-col h-screen overflow-hidden">
    <header class="bg-gray-900 border-b border-gray-800 text-white p-3 flex justify-between items-center flex-shrink-0">
        <h1 class="text-lg font-mono font-semibold flex items-center">
            <img src="https://www.operative.sh/favicon.ico?v=2" alt="Operative Favicon" class="h-5 w-5 mr-2 inline-block align-middle">
            <span><a href="https://www.operative.sh" target="_blank" class="hover:underline">Operative Control Center</a></span>
        </h1>
        <div class="flex items-center">
            <span class="mr-2 text-xs">View Mode:</span>
            <button id="view-toggle" class="bg-gray-800 hover:bg-gray-700 text-white text-xs border border-gray-600 rounded-md px-3 py-1 transition-all duration-300">
                <span class="separated-label">Separated</span>
                <span class="joined-label hidden">Joined</span>
            </button>
            <label class="ml-4 flex items-center cursor-pointer">
                <span class="text-xs mr-2">Auto-scroll:</span>
                <div class="relative">
                    <input type="checkbox" id="auto-scroll-toggle" class="sr-only" checked>
                    <div class="block bg-gray-600 w-10 h-5 rounded-full"></div>
                    <div class="dot absolute left-0.5 top-0.5 bg-white w-4 h-4 rounded-full transition-transform duration-300 transform translate-x-0"></div>
                </div>
            </label>
        </div>
    </header>
    <!-- Changed grid layout: md:grid-cols-2 -->
    <main id="separated-view" class="container mx-auto px-4 max-w-full flex-grow grid grid-cols-1 md:grid-cols-2 gap-4 py-4 overflow-hidden">
        <!-- New Browser View Column -->
        <div class="browser-column bg-terminal-bg border border-gray-800 rounded-2xl flex flex-col overflow-hidden h-full">
             <div class="log-header bg-terminal-header border-b border-gray-800 p-3 flex justify-between items-center text-sm font-medium flex-shrink-0">
                <h2 class="text-white">🌐 Browser View (Headless)</h2>
                <!-- Add any controls here later if needed -->
            </div>
            <div id="browser-view-container" class="flex-grow overflow-auto p-1 bg-gray-700 flex items-center justify-center">
                 <!-- Image will be updated by JS. Added tabindex to allow focus for keyboard events -->
                <img id="browser-view-img" src="" alt="Browser View" class="max-w-full max-h-full object-contain border border-gray-500 cursor-crosshair" tabindex="0"/>
            </div>
        </div>

        <!-- Log Columns Container (Takes the second grid column on md+) -->
        <div class="logs-wrapper flex flex-col gap-4 overflow-hidden h-full">
            <!-- Agent & Status Logs -->
            <div class="log-column bg-terminal-bg border border-gray-800 rounded-2xl flex flex-col overflow-hidden flex-1">
                 <div class="log-header bg-terminal-header border-b border-gray-800 p-3 flex justify-between items-center text-sm font-medium flex-shrink-0">
                    <h2 class="text-white">🚦 Agent & Status Logs</h2>
                    <button class="copy-button bg-transparent text-white text-xs border border-gray-600 hover:bg-white/10 rounded-md px-2 py-1" data-target="agent-log-container">📋 Copy</button>
                </div>
                <div id="agent-log-container" class="log-container flex-grow overflow-y-auto p-3 font-mono text-xs leading-relaxed"></div>
            </div>
            <!-- Console Logs -->
            <div class="log-column bg-terminal-bg border border-gray-800 rounded-2xl flex flex-col overflow-hidden flex-1">
                 <div class="log-header bg-terminal-header border-b border-gray-800 p-3 flex justify-between items-center text-sm font-medium flex-shrink-0">
                    <h2 class="text-white">🖥️ Console Logs</h2>
                    <button class="copy-button bg-transparent text-white text-xs border border-gray-600 hover:bg-white/10 rounded-md px-2 py-1" data-target="console-log-container">📋 Copy</button>
                </div>
                <div id="console-log-container" class="log-container flex-grow overflow-y-auto p-3 font-mono text-xs leading-relaxed"></div>
            </div>
            <!-- Network Activity -->
            <div class="log-column bg-terminal-bg border border-gray-800 rounded-2xl flex flex-col overflow-hidden flex-1">
                 <div class="log-header bg-terminal-header border-b border-gray-800 p-3 flex justify-between items-center text-sm font-medium flex-shrink-0">
                    <h2 class="text-white">↔️ Network Activity</h2>
                    <button class="copy-button bg-transparent text-white text-xs border border-gray-600 hover:bg-white/10 rounded-md px-2 py-1" data-target="network-log-container">📋 Copy</button>
                </div>
                <div id="network-log-container" class="log-container flex-grow overflow-y-auto p-3 font-mono text-xs leading-relaxed"></div>
            </div>
        </div> <!-- End logs-wrapper -->
    </main>

    <!-- Socket.IO Client Script -->
    <script>
        // Connect to Socket.IO server (same host/port)
        const socket = io();

        // DOM Elements
        const agentLogEl = document.getElementById('agent-log-container');
        const consoleLogEl = document.getElementById('console-log-container');
        const networkLogEl = document.getElementById('network-log-container');
        const browserViewImg = document.getElementById('browser-view-img'); // Get browser view image element

        // Auto-scroll toggle
        const autoScrollToggle = document.getElementById('auto-scroll-toggle');

        // Helper to append a log line to a container
        function appendLog(el, text) {
            const line = document.createElement('div');
            line.textContent = text;
            el.appendChild(line);
            // Keep the log length reasonable (optional)
            if (el.children.length > 2000) {
                el.firstChild.remove();
            }
            if (autoScrollToggle.checked) {
                el.scrollTop = el.scrollHeight;
            }
        }

        // Receive log messages
        socket.on('log_message', (payload) => {
            if (!payload) return;
            const { data, type } = payload;
            switch (type) {
                case 'console':
                    appendLog(consoleLogEl, data);
                    break;
                case 'network':
                    appendLog(networkLogEl, data);
                    break;
                case 'agent':
                case 'status': // fall-through – status also in agent column
                default:
                    appendLog(agentLogEl, data);
                    break;
            }
        });

        // Receive browser view updates
        socket.on('browser_update', (payload) => {
            if (payload && payload.data && browserViewImg) {
                browserViewImg.src = payload.data;
            }
        });

        // --- Input Event Handling ---
        if (browserViewImg) {
            // Helper to calculate scaled coordinates
            function getScaledCoordinates(event) {
                if (!browserViewImg.naturalWidth || !browserViewImg.naturalHeight) {
                    return null; // Image not loaded yet
                }
                const rect = browserViewImg.getBoundingClientRect();
                const scaleX = browserViewImg.naturalWidth / rect.width;
                const scaleY = browserViewImg.naturalHeight / rect.height;
                // Clamp coordinates to be within the natural bounds
                const x = Math.max(0, Math.min(browserViewImg.naturalWidth, Math.round((event.clientX - rect.left) * scaleX)));
                const y = Math.max(0, Math.min(browserViewImg.naturalHeight, Math.round((event.clientY - rect.top) * scaleY)));
                return { x, y };
            }

            // --- Mouse Click ---
            browserViewImg.addEventListener('click', (event) => {
                const coords = getScaledCoordinates(event);
                if (!coords) return;

                console.log(`Click: (${coords.x}, ${coords.y})`);
                socket.emit('browser_input', {
                    type: 'click', // Using 'click' as a shorthand for mouse down/up
                    details: {
                        x: coords.x,
                        y: coords.y,
                        button: event.button === 0 ? 'left' : event.button === 1 ? 'middle' : 'right', // Map button code
                        clickCount: event.detail // 1 for single, 2 for double, etc.
                    }
                });
                // Prevent default browser actions on the image if necessary
                event.preventDefault();
                 // Focus the image to capture subsequent key events
                browserViewImg.focus();
            });

             // --- Mouse Wheel (Scroll) ---
             browserViewImg.addEventListener('wheel', (event) => {
                const coords = getScaledCoordinates(event);
                 if (!coords) return; // Need coordinates for scroll origin

                console.log(`Scroll: dX=${event.deltaX}, dY=${event.deltaY} at (${coords.x}, ${coords.y})`);
                socket.emit('browser_input', {
                    type: 'scroll',
                    details: {
                        x: coords.x,
                        y: coords.y,
                        deltaX: event.deltaX,
                        deltaY: event.deltaY
                    }
                });
                // Prevent page scroll while interacting with the browser view
                event.preventDefault();
            });

            // --- Keyboard Input ---
            // Need to capture on the image itself after it's focused (e.g., by clicking)
            browserViewImg.addEventListener('keydown', (event) => {
                console.log(`KeyDown: Key=${event.key}, Code=${event.code}, Modifiers(A/C/M/S):${event.altKey}/${event.ctrlKey}/${event.metaKey}/${event.shiftKey}`);
                socket.emit('browser_input', {
                    type: 'keydown',
                    details: {
                        key: event.key,
                        code: event.code,
                        altKey: event.altKey,
                        ctrlKey: event.ctrlKey,
                        metaKey: event.metaKey,
                        shiftKey: event.shiftKey
                    }
                });
                 // Prevent default browser actions for keys if needed (e.g., arrow keys scrolling page)
                 // Be careful not to block essential browser shortcuts unless intended.
                 if (!event.metaKey && !event.ctrlKey && !event.altKey) { // Allow browser shortcuts
                    event.preventDefault();
                 }
            });

            browserViewImg.addEventListener('keyup', (event) => {
                 console.log(`KeyUp: Key=${event.key}, Code=${event.code}`);
                 socket.emit('browser_input', {
                    type: 'keyup',
                    details: {
                         key: event.key,
                         code: event.code,
                         altKey: event.altKey,
                         ctrlKey: event.ctrlKey,
                         metaKey: event.metaKey,
                         shiftKey: event.shiftKey
                    }
                 });
                 if (!event.metaKey && !event.ctrlKey && !event.altKey) {
                    event.preventDefault();
                 }
            });

            // TODO: Potentially add 'mousemove' if needed, but it can be very noisy.
            // TODO: Consider 'mousedown' and 'mouseup' separately if 'click' isn't sufficient (e.g., for dragging).
        }


        // View toggle: separated vs joined (Keep existing functionality)
        const viewToggleBtn = document.getElementById('view-toggle');
        const separatedView = document.getElementById('separated-view');
        // Note: This toggle might need adjustment depending on how the browser view should behave in "joined" mode.
        // For now, it will just hide/show the main grid containing browser + logs.
        let joinedMode = false;
        viewToggleBtn.addEventListener('click', () => {
            joinedMode = !joinedMode;
            if (joinedMode) {
                separatedView.classList.add('hidden'); // Hides the whole grid
                document.querySelector('.joined-label').classList.remove('hidden');
                document.querySelector('.separated-label').classList.add('hidden');
                // TODO: Implement a proper "joined" view if needed, maybe showing logs below browser?
            } else {
                separatedView.classList.remove('hidden'); // Shows the grid again
                document.querySelector('.joined-label').classList.add('hidden');
                document.querySelector('.separated-label').classList.remove('hidden');
            }
        });

        // Copy to clipboard buttons (Keep existing functionality)
        document.querySelectorAll('.copy-button').forEach(btn => {
            btn.addEventListener('click', () => {
                const targetId = btn.getAttribute('data-target');
                const targetEl = document.getElementById(targetId);
                if (!targetEl) return;
                const text = Array.from(targetEl.children).map(node => node.textContent).join('\\n');
                navigator.clipboard.writeText(text).then(() => {
                    btn.textContent = '✅ Copied';
                    setTimeout(() => (btn.textContent = '📋 Copy'), 2000);
                }).catch(() => {
                    btn.textContent = '❌ Failed';
                    setTimeout(() => (btn.textContent = '📋 Copy'), 2000);
                });
            });
        });

        console.log('Dashboard script initialised');
    </script>
</body>
</html>''')
        # print(f"Created modern index.html with Tailwind CSS at {index_path}")

    # Start the server in a separate thread.
    # run_server uses host/port from the outer scope, so no args needed here.
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    
    # print("Log server thread started.")
    # Send initial status message
    send_log("Log server thread started.", "🚀", log_type='status')

def open_log_dashboard(url='http://127.0.0.1:5009'):
    """Opens the specified URL in a new tab in the default web browser."""
    try:
        # print(f"Attempting to open dashboard in new tab at {url}...")
        # Use open_new_tab for better control
        webbrowser.open_new_tab(url)
        # print("Browser tab requested.") # Debug
        try:
            send_log(f"Opened dashboard in browser at {url}.", "🌐", log_type='status') # Add type
        except Exception as log_e:
            logging.warning(f"Failed to send dashboard open log: {log_e}")
    except Exception as e:
        # print(f"Could not open browser automatically: {e}") # Debug
        try:
            send_log(f"Could not open browser automatically: {e}", "⚠️", log_type='status') # Add type
        except Exception as log_e:
             logging.warning(f"Failed to send dashboard open error log: {log_e}")

# Example usage (for testing this module directly)
if __name__ == '__main__':
    pass
    start_log_server()
    import time
    time.sleep(2)
    open_log_dashboard()
    # Use the new log_type argument
    send_log("Server started and dashboard opened.", "✅", log_type='status')
    time.sleep(1)
    send_log("This is a test agent log message.", "🧪", log_type='agent')
    time.sleep(1)
    send_log("This is a test console log.", "🖥️", log_type='console')
    time.sleep(1)
    send_log("This is a test network request.", "➡️", log_type='network')
    time.sleep(1)
    send_log("This is a test network response.", "⬅️", log_type='network')
    # Keep the main thread alive to let the server run
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping server.")
