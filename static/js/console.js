// Console Management for AI Skills Pipeline
class ConsoleManager {
    constructor() {
        this.consoleOutput = document.getElementById('consoleOutput');
        this.consolePanel = document.querySelector('.console-panel');
        this.filterButton = document.getElementById('consoleFilter');
        this.clearButton = document.getElementById('consoleClear');
        this.filterContainer = document.getElementById('consoleFilters');
        this.logCount = document.getElementById('logCount');
        this.scrollStatus = document.getElementById('scrollStatus');
        this.autoScroll = true;
        this.currentSessionId = null;
        this.logBuffer = [];
        this.maxBuffer = 1000;
        this.currentFilter = 'all';
        this.eventSource = null;

        this.init();
    }

    init() {
        // Console functionality
        this.filterButton.addEventListener('click', () => this.toggleFilters());
        this.clearButton.addEventListener('click', () => this.clearConsole());

        // Filter chips
        this.filterContainer.addEventListener('click', (e) => {
            if (e.target.classList.contains('filter-chip')) {
                this.setFilter(e.target.dataset.level);
            }
        });

        // Check scroll position for auto-scroll indicator
        this.consoleOutput.addEventListener('scroll', () => this.checkAutoScroll());
    }

    setSession(sessionId) {
        this.currentSessionId = sessionId;
        this.clearConsole();
        this.connectStream();
    }

    toggleFilters() {
        const isVisible = this.filterContainer.style.display !== 'none';
        this.filterContainer.style.display = isVisible ? 'none' : 'flex';
    }

    setFilter(level) {
        this.currentFilter = level;

        // Update active chip
        const chips = this.filterContainer.querySelectorAll('.filter-chip');
        chips.forEach(chip => {
            chip.classList.toggle('active', chip.dataset.level === level);
        });

        // Filter displayed logs
        this.filterLogs();
    }

    filterLogs() {
        const logs = this.consoleOutput.querySelectorAll('.console-line');
        logs.forEach(log => {
            if (this.currentFilter === 'all') {
                log.style.display = 'flex';
            } else {
                log.style.display = log.classList.contains(this.currentFilter) ? 'flex' : 'none';
            }
        });
    }

    clearConsole() {
        this.logBuffer = [];
        this.consoleOutput.innerHTML = '';
        // Close any existing SSE connection when clearing
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
        this.log('Console cleared', 'info');
    }

    checkAutoScroll() {
        const isAtBottom = this.consoleOutput.scrollHeight -
                          this.consoleOutput.scrollTop ===
                          this.consoleOutput.clientHeight;

        if (isAtBottom) {
            this.autoScroll = true;
            this.scrollStatus.textContent = 'Auto-scroll';
        } else {
            this.autoScroll = false;
            this.scrollStatus.textContent = 'Manual scroll';
        }
    }

    log(message, level = 'info', stage = null, metadata = {}) {
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = {
            timestamp,
            level,
            message,
            stage,
            metadata
        };

        // Add to buffer
        this.logBuffer.push(logEntry);
        if (this.logBuffer.length > this.maxBuffer) {
            this.logBuffer = this.logBuffer.slice(-this.maxBuffer);
        }

        // Display in console
        this.displayLog(logEntry);
    }

    displayLog(logEntry) {
        const logDiv = document.createElement('div');
        logDiv.className = `console-line ${logEntry.level}`;

        // Create timestamp
        const timestampSpan = document.createElement('span');
        timestampSpan.className = 'timestamp';
        timestampSpan.textContent = new Date().toLocaleTimeString();

        // Create message
        const messageSpan = document.createElement('span');
        messageSpan.className = 'message';
        messageSpan.textContent = logEntry.message;

        logDiv.appendChild(timestampSpan);
        logDiv.appendChild(messageSpan);

        this.consoleOutput.appendChild(logDiv);

        // Update log count
        this.updateLogCount();

        // Apply filter if needed
        if (this.currentFilter !== 'all') {
            logDiv.style.display = logEntry.level === this.currentFilter ? 'flex' : 'none';
        }

        // Auto-scroll if enabled
        if (this.autoScroll) {
            this.consoleOutput.scrollTop = this.consoleOutput.scrollHeight;
        }
    }

    updateLogCount() {
        const logCount = this.consoleOutput.children.length;
        this.logCount.textContent = `${logCount} logs`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async connectStream() {
        if (!this.currentSessionId) return;

        try {
            // First, load any existing logs
            const response = await fetch(`/api/logs/${this.currentSessionId}`);
            const data = await response.json();

            if (data.logs && data.logs.length > 0) {
                data.logs.forEach(log => this.displayLog(log));
            }

            // Then connect to real-time SSE stream for updates
            this.startSSEStream();
        } catch (error) {
            console.error('Failed to connect to log stream:', error);
            this.log('Failed to connect to console stream', 'error');
        }
    }

    startSSEStream() {
        if (!this.currentSessionId) return;

        // Close any existing connection
        if (this.eventSource) {
            this.eventSource.close();
        }

        const url = `/api/logs/${this.currentSessionId}/stream`;
        this.eventSource = new EventSource(url);

        this.eventSource.onmessage = (event) => {
            try {
                const log = JSON.parse(event.data);
                this.displayLog(log);
            } catch (error) {
                console.error('Failed to parse log event:', error);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            if (this.eventSource.readyState === EventSource.CLOSED) {
                this.log('Console stream connection closed', 'warning');
                this.eventSource.close();
            }
        };
    }

    debug(message, stage = null, metadata = {}) {
        this.log(message, 'debug', stage, metadata);
    }

    info(message, stage = null, metadata = {}) {
        this.log(message, 'info', stage, metadata);
    }

    success(message, stage = null, metadata = {}) {
        this.log(message, 'success', stage, metadata);
    }

    warning(message, stage = null, metadata = {}) {
        this.log(message, 'warning', stage, metadata);
    }

    error(message, stage = null, metadata = {}) {
        this.log(message, 'error', stage, metadata);
    }
}

// Initialize console manager
const consoleManager = new ConsoleManager();