#!/usr/bin/env python3

import threading
import webbrowser
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO
import logging
import os
from datetime import datetime

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
    # print("Log dashboard client connected")
    # Send status message to dashboard
    send_log(f"Connected to log server at {datetime.now().strftime('%H:%M:%S')}", "✅", log_type='status')

@socketio.on('disconnect')
def handle_disconnect():
    print("Log dashboard client disconnected")
    # Send status message to dashboard
    send_log(f"Disconnected from log server at {datetime.now().strftime('%H:%M:%S')}", "❌", log_type='status')

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
        # Fallback print if emit fails (e.g., server not running)
        print(f"LOG SERVER EMIT FAILED ({log_type}): {emoji} {message} (Error: {e})")


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
    <main id="separated-view" class="container mx-auto px-4 max-w-7xl flex-grow grid grid-cols-1 md:grid-cols-3 gap-4 py-4 overflow-hidden">
        <div class="log-column bg-terminal-bg border border-gray-800 rounded-2xl flex flex-col overflow-hidden">
            <div class="log-header bg-terminal-header border-b border-gray-800 p-3 flex justify-between items-center text-sm font-medium">
                <h2 class="text-white">🚦 Agent & Status Logs</h2>
                <button class="copy-button bg-transparent text-white text-xs border border-gray-600 hover:bg-white/10 rounded-md px-2 py-1" data-target="agent-log-container">📋 Copy</button>
            </div>
            <div id="agent-log-container" class="log-container flex-grow overflow-y-auto p-3 font-mono text-xs leading-relaxed"></div>
        </div>
        <div class="log-column bg-terminal-bg border border-gray-800 rounded-2xl flex flex-col overflow-hidden">
            <div class="log-header bg-terminal-header border-b border-gray-800 p-3 flex justify-between items-center text-sm font-medium">
                <h2 class="text-white">🖥️ Console Logs</h2>
                <button class="copy-button bg-transparent text-white text-xs border border-gray-600 hover:bg-white/10 rounded-md px-2 py-1" data-target="console-log-container">📋 Copy</button>
            </div>
            <div id="console-log-container" class="log-container flex-grow overflow-y-auto p-3 font-mono text-xs leading-relaxed"></div>
        </div>
        <div class="log-column bg-terminal-bg border border-gray-800 rounded-2xl flex flex-col overflow-hidden">
            <div class="log-header bg-terminal-header border-b border-gray-800 p-3 flex justify-between items-center text-sm font-medium">
                <h2 class="text-white">↔️ Network Activity</h2>
                <button class="copy-button bg-transparent text-white text-xs border border-gray-600 hover:bg-white/10 rounded-md px-2 py-1" data-target="network-log-container">📋 Copy</button>
            </div>
            <div id="network-log-container" class="log-container flex-grow overflow-y-auto p-3 font-mono text-xs leading-relaxed"></div>
        </div>
    </main>
</body>
</html>''')
        # print(f"Created modern index.html with Tailwind CSS at {index_path}")


    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    # print("Log server thread started.")
    # Send initial status message
    send_log("Log server thread started.", "🚀", log_type='status') # Add type

def open_log_dashboard(url='http://127.0.0.1:5009'):
    """Opens the specified URL in a new tab in the default web browser."""
    try:
        # print(f"Attempting to open dashboard in new tab at {url}...")
        # Use open_new_tab for better control
        webbrowser.open_new_tab(url)
        # print("Browser tab requested.")
        send_log(f"Opened dashboard in browser at {url}.", "🌐", log_type='status') # Add type
    except Exception as e:
        # print(f"Could not open browser automatically: {e}")
        send_log(f"Could not open browser automatically: {e}", "⚠️", log_type='status') # Add type

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