(function() {
    console.log('Agent control overlay script injected');

    // Remove existing overlay if present to avoid duplicates
    const existingOverlay = document.getElementById('agent-control-overlay');
    if (existingOverlay) {
        existingOverlay.remove();
        console.log('Removed existing overlay');
    }

    // Create overlay container
    const overlay = document.createElement('div');
    overlay.id = 'agent-control-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background-color: rgba(0, 0, 0, 0.8);
        color: white;
        border-radius: 8px;
        padding: 10px;
        z-index: 9999999;
        font-family: Arial, sans-serif;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
        display: flex;
        flex-direction: column;
        min-width: 180px;
    `;

    // Create header with title and minimize button
    const header = document.createElement('div');
    header.style.cssText = `
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
        cursor: move;
    `;

    const title = document.createElement('div');
    title.textContent = 'Agent Controls';
    title.style.fontWeight = 'bold';

    const minimizeBtn = document.createElement('button');
    minimizeBtn.innerHTML = '−';
    minimizeBtn.style.cssText = `
        background: none;
        border: none;
        color: white;
        font-size: 16px;
        cursor: pointer;
        padding: 0 5px;
    `;

    header.appendChild(title);
    header.appendChild(minimizeBtn);

    // Create content container (for buttons)
    const content = document.createElement('div');
    content.id = 'agent-control-content';
    content.style.cssText = `
        display: flex;
        flex-direction: column;
        gap: 8px;
    `;

    // Create status indicator
    const statusIndicator = document.createElement('div');
    statusIndicator.id = 'agent-status';
    statusIndicator.style.cssText = `
        padding: 5px;
        text-align: center;
        border-radius: 4px;
        margin-bottom: 8px;
        font-size: 12px;
        background-color: #28a745;
    `;
    statusIndicator.textContent = 'Running';

    // Create control buttons
    const pauseBtn = document.createElement('button');
    pauseBtn.id = 'pause-agent-btn';
    pauseBtn.innerHTML = '⏸️ Pause';
    pauseBtn.style.cssText = buttonStyle('#ffc107');

    const resumeBtn = document.createElement('button');
    resumeBtn.id = 'resume-agent-btn';
    resumeBtn.innerHTML = '▶️ Resume';
    resumeBtn.style.cssText = buttonStyle('#28a745');
    resumeBtn.style.display = 'none'; // Initially hidden

    const stopBtn = document.createElement('button');
    stopBtn.id = 'stop-agent-btn';
    stopBtn.innerHTML = '⏹️ Stop';
    stopBtn.style.cssText = buttonStyle('#dc3545');

    // Add elements to the overlay
    content.appendChild(statusIndicator);
    content.appendChild(pauseBtn);
    content.appendChild(resumeBtn);
    content.appendChild(stopBtn);

    overlay.appendChild(header);
    overlay.appendChild(content);

    // Add the overlay to the page
    if (document.body) {
        document.body.appendChild(overlay);
        console.log('Added overlay to page body');
    } else {
        console.error('Cannot add overlay: document.body is not available');
        // Wait for body to be available
        const bodyCheckInterval = setInterval(() => {
            if (document.body) {
                document.body.appendChild(overlay);
                console.log('Added overlay to page body (delayed)');
                clearInterval(bodyCheckInterval);
            }
        }, 100);
    }

    // Minimize/maximize functionality
    let isMinimized = false;
    minimizeBtn.addEventListener('click', () => {
        if (isMinimized) {
            content.style.display = 'flex';
            minimizeBtn.innerHTML = '−';
            isMinimized = false;
        } else {
            content.style.display = 'none';
            minimizeBtn.innerHTML = '+';
            isMinimized = true;
        }
    });

    // Make the overlay draggable
    makeDraggable(overlay, header);

    // Add button event listeners
    pauseBtn.addEventListener('click', async () => {
        try {
            await window.pauseAgent();
            updateOverlayStatus('paused');
        } catch (e) {
            console.error('Failed to pause agent:', e);
        }
    });

    resumeBtn.addEventListener('click', async () => {
        try {
            await window.resumeAgent();
            updateOverlayStatus('running');
        } catch (e) {
            console.error('Failed to resume agent:', e);
        }
    });

    stopBtn.addEventListener('click', async () => {
        try {
            await window.stopAgent();
            updateOverlayStatus('stopped');
        } catch (e) {
            console.error('Failed to stop agent:', e);
        }
    });

    // Function to update the overlay status
    window.updateOverlayStatus = function(status) {
        const statusEl = document.getElementById('agent-status');
        const pauseBtn = document.getElementById('pause-agent-btn');
        const resumeBtn = document.getElementById('resume-agent-btn');
        const stopBtn = document.getElementById('stop-agent-btn');

        if (!statusEl || !pauseBtn || !resumeBtn || !stopBtn) return;

        if (status === 'running') {
            statusEl.textContent = 'Running';
            statusEl.style.backgroundColor = '#28a745';
            pauseBtn.style.display = 'block';
            resumeBtn.style.display = 'none';
        } else if (status === 'paused') {
            statusEl.textContent = 'Paused';
            statusEl.style.backgroundColor = '#ffc107';
            pauseBtn.style.display = 'none';
            resumeBtn.style.display = 'block';
        } else if (status === 'stopped') {
            statusEl.textContent = 'Stopped';
            statusEl.style.backgroundColor = '#dc3545';
            pauseBtn.style.display = 'none';
            resumeBtn.style.display = 'none';
            stopBtn.style.display = 'none';
        }
    };

    // Check agent state periodically
    const stateCheckInterval = setInterval(async () => {
        try {
            if (typeof window.getAgentState === 'function') {
                const state = await window.getAgentState();
                if (state.stopped) {
                    updateOverlayStatus('stopped');
                } else if (state.paused) {
                    updateOverlayStatus('paused');
                } else {
                    updateOverlayStatus('running');
                }
            }
        } catch (e) {
            console.error('Failed to get agent state:', e);
        }
    }, 1000);

    // Helper function for button styles
    function buttonStyle(bgColor) {
        return 'padding: 8px 12px; ' +
               'background-color: ' + bgColor + '; ' +
               'color: white; ' +
               'border: none; ' +
               'border-radius: 4px; ' +
               'cursor: pointer; ' +
               'font-size: 14px; ' +
               'transition: opacity 0.2s; ' +
               'display: flex; ' +
               'align-items: center; ' +
               'justify-content: center;';
    }

    // Helper function to make an element draggable
    function makeDraggable(element, handle) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;

        handle.onmousedown = dragMouseDown;

        function dragMouseDown(e) {
            e.preventDefault();
            // Get mouse position at startup
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            // Call function whenever the cursor moves
            document.onmousemove = elementDrag;
        }

        function elementDrag(e) {
            e.preventDefault();
            // Calculate new position
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            // Set element's new position
            element.style.top = (element.offsetTop - pos2) + "px";
            element.style.left = (element.offsetLeft - pos1) + "px";
            // If moved, ensure position is fixed and remove potential conflicts
            element.style.position = 'fixed';
        }

        function closeDragElement() {
            // Stop moving when mouse button is released
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }
})();
