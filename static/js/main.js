// Global state
let currentSessionId = null;
let currentTimestamp = null;
let canIterate = false;
let statusPoller = null;
let logSource = null;

// DOM Elements
const queryInput = document.getElementById('queryInput');
const startBtn = document.getElementById('startBtn');
const iterateBtn = document.getElementById('iterateBtn');
const statusEl = document.getElementById('status');
const statusText = statusEl.querySelector('.status-text');
const resultsSection = document.querySelector('.results-section');
const iterationCount = document.getElementById('iterationCount');
const timestampEl = document.getElementById('timestamp');
const previewBtn = document.getElementById('previewBtn');
const exportSkillBtn = document.getElementById('exportSkillBtn');
const exportBundleBtn = document.getElementById('exportBundleBtn');
const refreshBtn = document.getElementById('refreshBtn');
const templatesList = document.getElementById('templatesList');

// Process stream elements
const processStream = document.getElementById('processStream');
const currentStageEl = document.getElementById('currentStage');
const progressFill = document.getElementById('progressFill');
const logStream = document.getElementById('logStream');

// Tab elements
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');

// Error modal elements (keeping for errors)
const errorModal = document.getElementById('errorModal');
const errorMessage = document.getElementById('errorMessage');

// Event Listeners
startBtn.addEventListener('click', startPipeline);
iterateBtn.addEventListener('click', iteratePipeline);
previewBtn.addEventListener('click', openPreview);
exportSkillBtn.addEventListener('click', exportSkill);
exportBundleBtn.addEventListener('click', exportBundle);
refreshBtn.addEventListener('click', loadTemplates);

// Tab switching
tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;
        switchTab(tabName);
    });
});

// Copy buttons
document.addEventListener('click', (e) => {
    if (e.target.classList.contains('copy-btn')) {
        const targetId = e.target.dataset.target;
        const text = document.getElementById(targetId).textContent;
        copyToClipboard(text);
        showToast('Copied to clipboard!');
    }
});

// Functions
async function startPipeline() {
    const query = queryInput.value.trim();
    if (!query) {
        showError('Please enter a query');
        return;
    }

    // Show process stream
    showProcessStream();
    updateStage('Initializing pipeline...');
    updateProgress(0);
    disableButtons(true);
    clearProcessLog();

    // Add initial log entry
    addLogEntry('Starting AI skill generation pipeline...', 'info');
    addLogEntry(`Query: "${query}"`, 'info');

    try {
        const response = await fetch('/api/pipeline/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Pipeline failed');
        }

        // Update state
        currentSessionId = data.session_id;
        currentTimestamp = data.timestamp;
        canIterate = false;

        // Start status polling + logs
        startStatusPolling();
        startLogStream();

    } catch (error) {
        showError(error.message);
        stopStatusPolling();
        stopLogStream();
        hideProcessStream();
        disableButtons(false);
    }
}

async function iteratePipeline() {
    if (!currentSessionId) {
        showError('No active pipeline session');
        return;
    }

    // Show process stream
    showProcessStream();
    updateStage('Running iteration...');
    updateProgress(0);
    disableButtons(true);
    clearProcessLog();

    // Add iteration log entry
    addLogEntry('Starting pipeline iteration...', 'info');

    try {
        const response = await fetch('/api/pipeline/iterate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ session_id: currentSessionId })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Iteration failed');
        }

        // Start status polling + logs
        startStatusPolling();
        startLogStream();

    } catch (error) {
        showError(error.message);
        stopStatusPolling();
        stopLogStream();
        hideProcessStream();
        disableButtons(false);
    }
}

function updateResults(data) {
    // Show results section
    resultsSection.style.display = 'block';

    // Update metadata
    iterationCount.textContent = data.iteration_count;
    timestampEl.textContent = data.timestamp;

    // Update outputs
    document.getElementById('researchOutput').textContent = data.research_output;
    document.getElementById('analysisOutput').textContent = data.analysis_output;
    document.getElementById('templateOutput').textContent = data.template_output;

    // Update iterate button
    iterateBtn.disabled = !canIterate;
    iterateBtn.textContent = canIterate ? 'Iterate' : 'Max iterations reached';

    // Update export buttons
    if (currentTimestamp) {
        exportSkillBtn.onclick = () => {
            window.open(`/api/template/${currentTimestamp}/export?type=skill`, '_blank');
        };
        exportBundleBtn.onclick = () => {
            window.open(`/api/template/${currentTimestamp}/export?type=bundle`, '_blank');
        };
    }

    const bundleTreeEl = document.getElementById('bundleTree');
    if (bundleTreeEl) {
        bundleTreeEl.textContent = data.bundle_tree || 'Bundle not available yet.';
    }

    // Switch to template tab
    switchTab('template');
}

async function pollStatus() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`/api/pipeline/status?session_id=${currentSessionId}`);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to fetch status');
        }

        if (data.status === 'running' || data.status === 'queued') {
            // Update stage and progress based on pipeline stage
            updateStageFromPipeline(data.stage);
            return;
        }

        if (data.status === 'error') {
            stopStatusPolling();
            stopLogStream();
            addLogEntry('Pipeline failed: ' + (data.error || 'Unknown error'), 'error');
            hideProcessStream();
            disableButtons(false);
            showError(data.error || 'Pipeline failed');
            return;
        }

        if (data.status === 'completed') {
            stopStatusPolling();
            stopLogStream();
            updateStage('Complete!', 100);
            addLogEntry('Pipeline completed successfully! Your AI skill is ready.', 'success');

            // Hide process stream after a delay
            setTimeout(() => {
                hideProcessStream();
                resultsSection.style.display = 'block';
                switchTab('template');
                // Show chat interface for refinement
                showChatInterface();
            }, 2000);

            canIterate = data.can_iterate;
            updateResults(data);
            showSuccess('Pipeline completed successfully!');
            loadTemplates();
            disableButtons(false);

            // If this was a refinement, update chat
            if (isProcessingChat) {
                isProcessingChat = false;
                addAIMessage("✅ Your skill has been refined! Check the updated template above.");
            }
        }
    } catch (error) {
        stopStatusPolling();
        hideProcessStream();
        disableButtons(false);
        showError(error.message);
    }
}

function startStatusPolling() {
    stopStatusPolling();
    pollStatus();
    statusPoller = setInterval(pollStatus, 1500);
}

function stopStatusPolling() {
    if (statusPoller) {
        clearInterval(statusPoller);
        statusPoller = null;
    }
}

function startLogStream() {
    if (!currentSessionId) return;

    stopLogStream();

    logSource = new EventSource(`/api/pipeline/logs?session_id=${currentSessionId}`);
    logSource.onmessage = (event) => {
        if (!event.data) return;
        try {
            const entry = JSON.parse(event.data);
            appendLogEntry(entry);
        } catch (error) {
            console.warn('Invalid log entry', error);
        }
    };
    logSource.onerror = () => {
        stopLogStream();
    };
}

function stopLogStream() {
    if (logSource) {
        logSource.close();
        logSource = null;
    }
}

function appendLogEntry(entry) {
    // Add to legacy log output for compatibility
    const logOutput = document.getElementById('logOutput');
    if (logOutput) {
        const timestamp = entry.timestamp ? `[${entry.timestamp}] ` : '';
        logOutput.textContent += `${timestamp}${entry.message}\n`;
        logOutput.scrollTop = logOutput.scrollHeight;
    }

    // Add to process stream if it's visible
    if (processStream && processStream.style.display !== 'none') {
        // Determine log level from message content
        let level = 'info';
        const message = entry.message.toLowerCase();

        if (message.includes('error') || message.includes('failed') || message.includes('exception')) {
            level = 'error';
        } else if (message.includes('success') || message.includes('completed') || message.includes('finished')) {
            level = 'success';
        } else if (message.includes('warning') || message.includes('deprecated')) {
            level = 'warning';
        } else if (message.includes('stage') || message.includes('starting') || message.includes('beginning')) {
            level = 'stage';
        }

        addLogEntry(entry.message, level, entry.timestamp);
    }
}

function clearLogOutput() {
    const logOutput = document.getElementById('logOutput');
    if (logOutput) {
        logOutput.textContent = '';
    }
}

function switchTab(tabName) {
    // Update buttons
    tabBtns.forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });

    // Update panes
    tabPanes.forEach(pane => {
        pane.classList.toggle('active', pane.id === `${tabName}-tab`);
    });
}

function openPreview() {
    if (currentTimestamp) {
        window.open(`/preview/${currentTimestamp}`, '_blank');
    }
}

function exportSkill() {
    if (!currentTimestamp) return;
    window.open(`/api/template/${currentTimestamp}/export?type=skill`, '_blank');
}

function exportBundle() {
    if (!currentTimestamp) return;
    window.open(`/api/template/${currentTimestamp}/export?type=bundle`, '_blank');
}

async function loadTemplates() {
    try {
        const response = await fetch('/api/templates');
        const data = await response.json();

        if (!response.ok) throw new Error('Failed to load templates');

        renderTemplates(data.templates);
    } catch (error) {
        console.error('Failed to load templates:', error);
    }
}

function renderTemplates(templates) {
    if (templates.length === 0) {
        templatesList.innerHTML = '<p class="no-templates">No templates generated yet</p>';
        return;
    }

    templatesList.innerHTML = templates.map(template => `
        <div class="template-card">
            <h3>${escapeHtml(template.query)}</h3>
            <div class="meta">
                <div>Generated: ${template.timestamp}</div>
                <div>Iterations: ${template.iteration_count}</div>
                <div>Created: ${new Date(template.created_at).toLocaleString()}</div>
            </div>
            <div class="actions">
                <a href="/preview/${template.timestamp}" class="btn btn-small btn-outline">Preview</a>
                <a href="/api/template/${template.timestamp}/export?type=bundle" class="btn btn-small btn-outline" target="_blank">Export Bundle</a>
            </div>
        </div>
    `).join('');
}


function showError(message) {
    errorMessage.textContent = message;
    errorModal.style.display = 'flex';
    statusEl.classList.add('error');
    statusText.textContent = 'Error';
}

function showSuccess(message) {
    statusEl.classList.remove('processing', 'error');
    statusText.textContent = message;
}

function closeErrorModal() {
    errorModal.style.display = 'none';
    statusEl.classList.remove('error');
    statusText.textContent = 'Ready';
}

function disableButtons(disabled) {
    startBtn.disabled = disabled;
    iterateBtn.disabled = disabled || !canIterate;
}

function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text);
    } else {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
    }
}

function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast success';
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.remove();
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Process Stream Functions
function showProcessStream() {
    if (processStream) {
        processStream.style.display = 'block';
        processStream.classList.add('active');
    }
}

function hideProcessStream() {
    if (processStream) {
        processStream.classList.remove('active');
        processStream.style.display = 'none';
    }
}

function updateStage(stageText, progress) {
    if (currentStageEl) {
        currentStageEl.textContent = stageText;
    }
    if (progress !== undefined) {
        updateProgress(progress);
    }
}

function updateStageFromPipeline(stage) {
    const stageMap = {
        'research': { text: '📚 Researching Domain Knowledge', progress: 33 },
        'analysis': { text: '🔍 Analyzing Patterns & Opportunities', progress: 66 },
        'template': { text: '🛠️ Generating Skill Template', progress: 100 }
    };

    const stageInfo = stageMap[stage] || { text: 'Processing...', progress: 0 };
    updateStage(stageInfo.text, stageInfo.progress);
}

function updateProgress(percentage) {
    if (progressFill) {
        progressFill.style.width = `${percentage}%`;
    }
}

function addLogEntry(message, level = 'info', timestamp = null) {
    if (!logStream) return;

    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${level}`;

    const timestampEl = document.createElement('span');
    timestampEl.className = 'log-timestamp';
    timestampEl.textContent = timestamp || new Date().toLocaleTimeString();

    const messageEl = document.createElement('span');
    messageEl.textContent = message;

    logEntry.appendChild(timestampEl);
    logEntry.appendChild(messageEl);

    logStream.appendChild(logEntry);

    // Scroll to bottom
    logStream.parentElement.scrollTop = logStream.parentElement.scrollHeight;

    // Trigger animation
    requestAnimationFrame(() => {
        logEntry.classList.add('visible');
    });
}

function clearProcessLog() {
    if (logStream) {
        logStream.innerHTML = '';
    }
}

// Remove the old setLoading function since we're not using modal
function setLoading(message) {
    if (message) {
        statusEl.classList.add('processing');
        statusText.textContent = message;
        // Update stage if process stream is visible
        if (processStream && processStream.style.display !== 'none') {
            updateStage(message);
        }
    } else {
        statusEl.classList.remove('processing');
        statusText.textContent = 'Ready';
    }
}

// Chat Refinement Functions
let chatHistory = [];
let isProcessingChat = false;

// Show chat interface after pipeline completes
function showChatInterface() {
    const chatRefinement = document.getElementById('chatRefinement');
    if (chatRefinement) {
        chatRefinement.style.display = 'block';
        addAIMessage("Your skill is ready! 🎉 You can chat with me to refine it further. What would you like to change or add?");
    }
}

// Add user message to chat
function addUserMessage(message) {
    const chatMessages = document.getElementById('chatMessages');
    const messageEl = document.createElement('div');
    messageEl.className = 'chat-message user';
    messageEl.innerHTML = `<div class="chat-bubble">${escapeHtml(message)}</div>`;
    chatMessages.appendChild(messageEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add AI message to chat
function addAIMessage(message) {
    const chatMessages = document.getElementById('chatMessages');
    const messageEl = document.createElement('div');
    messageEl.className = 'chat-message ai';
    messageEl.innerHTML = `<div class="chat-bubble">${escapeHtml(message)}</div>`;
    chatMessages.appendChild(messageEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Send chat message for refinement
async function sendChatMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();

    if (!message || isProcessingChat) return;

    addUserMessage(message);
    chatInput.value = '';
    isProcessingChat = true;

    addAIMessage("🔄 Working on your request...");

    try {
        const response = await fetch('/api/pipeline/refine', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                message: message
            })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Refinement failed');
        }

        // Show process stream for refinement
        showProcessStream();
        startLogStream();

    } catch (error) {
        addAIMessage(`❌ Sorry, something went wrong: ${error.message}`);
        isProcessingChat = false;
    }
}

// Chat send button handler
document.getElementById('chatSendBtn').addEventListener('click', sendChatMessage);

// Enter to send (Shift+Enter for new line)
document.getElementById('chatInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendChatMessage();
    }
});

// Refine button handler
document.getElementById('refineBtn').addEventListener('click', () => {
    const chatRefinement = document.getElementById('chatRefinement');
    chatRefinement.scrollIntoView({ behavior: 'smooth' });
    document.getElementById('chatInput').focus();
});

// Initialize
loadTemplates();
