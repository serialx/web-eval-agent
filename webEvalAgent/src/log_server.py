#!/usr/bin/env python3

import threading
import webbrowser
import sys
import subprocess
from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO
import logging
import os

# Configure logging for Flask and SocketIO (optional, can be noisy)
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR) # Reduce Flask's default logging
logging.getLogger('socketio').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)

app = Flask(__name__, template_folder='../templates') # Point to templates dir relative to this file
app.config['SECRET_KEY'] = 'secret!' # Replace with a proper secret if needed
socketio = SocketIO(app, cors_allowed_origins="*") # Allow all origins for local dev

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
    print("Log dashboard client connected")
    # You could add the client's SID (request.sid) to connected_clients if needed

@socketio.on('disconnect')
def handle_disconnect():
    print("Log dashboard client disconnected")
    # You could remove the client's SID from connected_clients if needed

def send_log(message: str, emoji: str = "➡️"):
    """Sends a log message with an emoji prefix to all connected clients."""
    # Ensure socketio context is available. If called from a non-SocketIO thread,
    # use socketio.emit directly.
    try:
        log_entry = f"{emoji} {message}"
        # print(f"Attempting to send log: {log_entry}") # Debug print if needed
        socketio.emit('log_message', {'data': log_entry})
        # print(f"Log emitted: {log_entry}") # Debug print if needed
    except Exception as e:
        # Fallback print if emit fails (e.g., server not running)
        print(f"LOG SERVER EMIT FAILED: {emoji} {message} (Error: {e})")


def start_log_server(host='127.0.0.1', port=5000):
    """Starts the Flask-SocketIO server in a background thread."""
    def run_server():
        print(f"Starting Operative Control Center server on http://{host}:{port}")
        # Use eventlet or gevent for production? For local dev, default Flask dev server is fine.
        # Setting log_output=False to reduce console noise from SocketIO itself
        socketio.run(app, host=host, port=port, log_output=False, use_reloader=False, allow_unsafe_werkzeug=True)

    # Check if templates directory exists
    template_dir = os.path.join(os.path.dirname(__file__), '../templates')
    if not os.path.exists(template_dir):
        print(f"Warning: Template directory not found at {template_dir}. Creating it.")
        os.makedirs(template_dir)
        # Optionally create a placeholder index.html if it's missing
        index_path = os.path.join(template_dir, 'index.html')
        if not os.path.exists(index_path):
             with open(index_path, 'w') as f:
                 f.write("<html><head><title>Operative Control Center</title></head><body><h1>Waiting for logs...</h1></body></html>")
             print(f"Created placeholder index.html at {index_path}")


    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    print("Log server thread started.")

def open_log_dashboard(url='http://127.0.0.1:5000'):
    """Opens the specified URL, attempting to use Chrome first, then falling back to default browser."""
    print(f"Attempting to open dashboard at {url}...")
    specific_browser_opened = False

    try:
        if sys.platform == 'darwin': # macOS
            try:
                print("Attempting to open with Chrome on macOS...")
                subprocess.run(['open', '-a', 'Google Chrome', url], check=True)
                specific_browser_opened = True
                print("Opened with Chrome using 'open -a' command.")
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                print(f"Could not open with Chrome using 'open -a': {e}. Trying default browser...")

        elif sys.platform.startswith('linux'): # Linux
            # Try google-chrome first, then chromium-browser
            for browser_cmd in ['google-chrome', 'chromium-browser', 'chromium']:
                try:
                    print(f"Attempting to open with {browser_cmd} on Linux...")
                    subprocess.run([browser_cmd, url], check=True)
                    specific_browser_opened = True
                    print(f"Opened with {browser_cmd} command.")
                    break # Exit loop if successful
                except (FileNotFoundError, subprocess.CalledProcessError) as e:
                    print(f"Could not open with {browser_cmd}: {e}. Trying next option...")
            if not specific_browser_opened:
                print("Could not open with specific Chrome/Chromium commands on Linux. Trying default browser...")

        elif sys.platform == 'win32': # Windows
            try:
                print("Attempting to open with Chrome on Windows...")
                # The 'start chrome' command usually works well
                subprocess.run(['start', 'chrome', url], check=True, shell=True)
                specific_browser_opened = True
                print("Opened with Chrome using 'start chrome' command.")
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                 print(f"Could not open with 'start chrome': {e}. Trying default browser...")

    except Exception as e:
        print(f"An unexpected error occurred during platform-specific browser opening: {e}")

    # Fallback to default browser if platform-specific attempt failed or wasn't applicable
    if not specific_browser_opened:
        try:
            print("Falling back to default system browser...")
            webbrowser.open(url)
            print("Browser tab requested via default mechanism.")
        except Exception as e:
            print(f"Could not open browser automatically using default mechanism: {e}")

# Example usage (for testing this module directly)
if __name__ == '__main__':
    start_log_server()
    import time
    time.sleep(2)
    open_log_dashboard()
    send_log("Server started and dashboard opened.", "✅")
    time.sleep(3)
    send_log("This is a test log message.", "🧪")
    time.sleep(3)
    send_log("Another test log with a different emoji.", "🚀")
    # Keep the main thread alive to let the server run
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping server.") 