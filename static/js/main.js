// Global state
let currentSessionId = null;
let currentTimestamp = null;
let canIterate = false;
let statusPollInterval = null;
let pipelineStartTime = null;

// DOM Elements
const queryInput = document.getElementById('queryInput');
const startBtn = document.getElementById('startBtn');
const iterateBtn = document.getElementById('iterateBtn');
const globalStatus = document.getElementById('globalStatus');
const statusText = globalStatus ? globalStatus.querySelector('.status-text') : null;
const resultsSection = document.getElementById('resultsSection');
const iterationCount = document.getElementById('iterationCount');
const pipelineStatus = document.getElementById('pipelineStatus');
const previewBtn = document.getElementById('previewBtn');
const exportBtn = document.getElementById('exportBtn');
const templatesToggle = document.getElementById('templatesToggle');
const templatesSection = document.getElementById('templatesSection');
const templatesList = document.getElementById('templatesList');

// Tab elements
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');

// Modal elements removed - using inline indicators instead

// Event Listeners
startBtn.addEventListener('click', startPipeline);
iterateBtn.addEventListener('click', iteratePipeline);
previewBtn.addEventListener('click', openPreview);
exportBtn.addEventListener('click', exportTemplate);
templatesToggle.addEventListener('click', toggleTemplates);

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

    consoleManager.info(`Starting pipeline with query: "${query}"`, 'init');
    setLoading('Initializing pipeline...');
    disableButtons(true);
    pipelineStartTime = Date.now();

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

        // Update state IMMEDIATELY
        currentSessionId = data.session_id;
        currentTimestamp = data.timestamp;

        // Connect console IMMEDIATELY to this session to catch all logs
        consoleManager.setSession(currentSessionId);

        // Show results section with loading state
        showResultsLoading();

        // Start polling for status updates
        startStatusPolling();

    } catch (error) {
        showError(error.message);
        setLoading(false);
        disableButtons(false);
    }
}

function showResultsLoading() {
    // Show results section with skeleton loaders
    resultsSection.style.display = 'block';
    
    // Show stage indicators
    const stageIndicators = document.getElementById('stageIndicators');
    if (stageIndicators) {
        stageIndicators.style.display = 'flex';
    }
    
    // Set loading state
    pipelineStatus.textContent = 'Processing...';
    iterationCount.textContent = '0';
    
    // Show skeleton loaders in tabs
    document.getElementById('researchOutput').innerHTML = '<div class="skeleton-loader">Research in progress...</div>';
    document.getElementById('analysisOutput').innerHTML = '<div class="skeleton-loader">Waiting for research...</div>';
    document.getElementById('templateOutput').innerHTML = '<div class="skeleton-loader">Waiting for analysis...</div>';
}

function startStatusPolling() {
    // Clear any existing interval
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
    }

    // Update immediately
    updatePipelineStatus();

    // Poll every 1 second
    statusPollInterval = setInterval(updatePipelineStatus, 1000);
}

async function updatePipelineStatus() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(`/api/pipeline/status/${currentSessionId}`);
        if (!response.ok) return;

        const data = await response.json();
        
        // Update progress indicator
        updateProgressIndicator(data.current_stage);
        
        // Update elapsed time
        updateElapsedTime();
        
        // Update results as they become available
        if (data.has_research) {
            document.getElementById('researchOutput').textContent = data.research_output;
        }
        if (data.has_analysis) {
            document.getElementById('analysisOutput').textContent = data.analysis_output;
        }
        if (data.has_template) {
            document.getElementById('templateOutput').textContent = data.template_output;
        }
        
        // Check if completed
        if (data.current_stage === 'completed') {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
            
            // Update final state
            canIterate = data.can_iterate;
            currentTimestamp = data.timestamp;
            
            // Update metadata
            iterationCount.textContent = data.iteration_count;
            pipelineStatus.textContent = 'Complete';
            
            // Enable buttons
            setLoading(false);
            disableButtons(false);
            
            // Show success
            showSuccess('Pipeline completed successfully!');
            
            // Switch to template tab
            switchTab('template');
        }
        
    } catch (error) {
        console.error('Status poll error:', error);
    }
}

function updateProgressIndicator(stage) {
    const stages = {
        'initializing': { text: 'Initializing...', percent: 0, current: null },
        'researching': { text: 'Research Phase', percent: 33, current: 'research' },
        'analyzing': { text: 'Analysis Phase', percent: 66, current: 'analysis' },
        'generating_template': { text: 'Generating Template', percent: 90, current: 'template' },
        'completed': { text: 'Complete', percent: 100, current: 'template' }
    };
    
    const stageInfo = stages[stage] || stages['initializing'];
    setLoading(stageInfo.text);
    
    // Update status text
    if (statusText) {
        statusText.textContent = stageInfo.text;
    }
    
    // Update stage indicators
    updateStageIndicators(stage, stageInfo.current);
}

function updateStageIndicators(stage, currentStage) {
    const stageItems = {
        'research': document.getElementById('stage-research'),
        'analysis': document.getElementById('stage-analysis'),
        'template': document.getElementById('stage-template')
    };
    
    // Reset all
    Object.values(stageItems).forEach(item => {
        if (item) {
            item.classList.remove('active', 'completed');
        }
    });
    
    // Mark completed stages
    const stageOrder = ['research', 'analysis', 'template'];
    const currentIndex = stageOrder.indexOf(currentStage);
    
    if (currentIndex > -1) {
        // Mark all previous as completed
        for (let i = 0; i < currentIndex; i++) {
            const item = stageItems[stageOrder[i]];
            if (item) item.classList.add('completed');
        }
        
        // Mark current as active
        const currentItem = stageItems[currentStage];
        if (currentItem) currentItem.classList.add('active');
    }
    
    // If completed, mark all as completed
    if (stage === 'completed') {
        Object.values(stageItems).forEach(item => {
            if (item) {
                item.classList.remove('active');
                item.classList.add('completed');
            }
        });
    }
}

function updateElapsedTime() {
    if (!pipelineStartTime) return;
    
    const elapsed = Math.floor((Date.now() - pipelineStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    const timeStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    
    // Update in header if element exists
    const headerLoading = document.getElementById('headerLoading');
    if (headerLoading) {
        const loadingText = headerLoading.querySelector('.header-loading-text');
        if (loadingText && loadingText.textContent.indexOf('(') === -1) {
            loadingText.textContent += ` (${timeStr})`;
        } else if (loadingText) {
            loadingText.textContent = loadingText.textContent.replace(/\(\d+:\d+\)/, `(${timeStr})`);
        }
    }
}

async function iteratePipeline() {
    if (!currentSessionId) {
        showError('No active pipeline session');
        return;
    }

    setLoading('Running iteration...');
    disableButtons(true);

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

        // Update state
        canIterate = data.can_iterate;

        // Update UI
        updateResults(data);
        showSuccess('Iteration completed successfully!');

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
        disableButtons(false);
    }
}

function updateResults(data) {
    // Show results section
    resultsSection.style.display = 'block';

    // Update metadata
    iterationCount.textContent = data.iteration_count;
    pipelineStatus.textContent = data.new_instruction ? 'Complete' : 'Complete';

    // Update web search status if available
    const webSearchStatus = document.getElementById('webSearchStatus');
    if (webSearchStatus && data.web_search_provider) {
        webSearchStatus.style.display = 'flex';
        document.getElementById('webSearchProvider').textContent = data.web_search_provider;
    }

    // Update outputs
    document.getElementById('researchOutput').textContent = data.research_output;
    document.getElementById('analysisOutput').textContent = data.analysis_output;
    document.getElementById('templateOutput').textContent = data.template_output;

    // Update iterate button
    iterateBtn.disabled = !canIterate;
    iterateBtn.querySelector('.btn-text').textContent = canIterate ? 'Refine' : 'Max iterations';

    // Update export button
    if (currentTimestamp) {
        exportBtn.onclick = () => {
            window.open(`/api/template/${currentTimestamp}/export`, '_blank');
        };
    }

    // Switch to template tab
    switchTab('template');
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

async function exportTemplate() {
    if (!currentTimestamp) return;

    try {
        const response = await fetch(`/api/template/${currentTimestamp}/export`);
        if (!response.ok) throw new Error('Export failed');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `skill_template_${currentTimestamp}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showSuccess('Template exported successfully!');
    } catch (error) {
        showError(error.message);
    }
}

function toggleTemplates() {
    const isVisible = templatesSection.style.display === 'block';
    templatesSection.style.display = isVisible ? 'none' : 'block';

    if (!isVisible) {
        loadTemplates();
    }
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
        templatesList.innerHTML = '<p class="empty-state">No skills generated yet</p>';
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
                <a href="/preview/${template.timestamp}" class="btn btn-small">Preview</a>
                <a href="/api/template/${template.timestamp}/export" class="btn btn-small" target="_blank">Export</a>
            </div>
        </div>
    `).join('');
}

function setLoading(message) {
    // Completely avoid modals - just use the inline indicator
    const headerLoading = document.getElementById('headerLoading');
    const loadingTextElement = headerLoading ? headerLoading.querySelector('.header-loading-text') : null;
    const loadingModal = document.getElementById('loadingModal');

    if (message) {
        // Show only inline loading indicator
        if (headerLoading) {
            headerLoading.classList.add('show');
            if (loadingTextElement) {
                loadingTextElement.textContent = message;
            }
        }
        // Ensure global status is visible
        if (globalStatus) {
            globalStatus.style.display = 'flex';
            updateGlobalStatus('processing', message);
        }
        // Never show the modal
        if (loadingModal) {
            loadingModal.style.display = 'none';
        }
    } else {
        // Hide loading indicator
        if (headerLoading) {
            headerLoading.classList.remove('show');
        }
        // Update global status
        if (globalStatus) {
            updateGlobalStatus('active', 'Ready');
        }
        // Ensure modal is hidden
        if (loadingModal) {
            loadingModal.style.display = 'none';
        }
    }
}

function showError(message) {
    // Use global status to show errors inline, no modal
    if (globalStatus) {
        globalStatus.style.display = 'flex';
        updateGlobalStatus('', 'Error: ' + message);
    }

    // Also show in console
    if (window.consoleManager) {
        consoleManager.error(message, 'error');
    }

    // Auto-clear error after 5 seconds
    setTimeout(() => {
        if (globalStatus) {
            updateGlobalStatus('active', 'Ready');
        }
    }, 5000);
}

function showSuccess(message) {
    if (globalStatus) {
        globalStatus.style.display = 'flex';
        updateGlobalStatus('active', message);
    }
}

// closeErrorModal function removed - no longer needed

function updateGlobalStatus(statusClass, text) {
    if (globalStatus) {
        const statusDot = globalStatus.querySelector('.status-dot');
        const statusText = globalStatus.querySelector('.status-text');

        if (statusDot) {
            statusDot.className = 'status-dot';
            if (statusClass) {
                statusDot.classList.add(statusClass);
            }
        }

        if (statusText) {
            statusText.textContent = text;
        }
    }
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

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Set initial status
    updateGlobalStatus('active', 'Ready');

    // Load templates if section is visible
    if (templatesSection.style.display === 'block') {
        loadTemplates();
    }
});