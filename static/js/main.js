// Global state
let currentSessionId = null;
let currentTimestamp = null;
let canIterate = false;

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
const exportBtn = document.getElementById('exportBtn');
const refreshBtn = document.getElementById('refreshBtn');
const templatesList = document.getElementById('templatesList');

// Tab elements
const tabBtns = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');

// Modal elements
const loadingModal = document.getElementById('loadingModal');
const loadingText = document.getElementById('loadingText');
const errorModal = document.getElementById('errorModal');
const errorMessage = document.getElementById('errorMessage');

// Event Listeners
startBtn.addEventListener('click', startPipeline);
iterateBtn.addEventListener('click', iteratePipeline);
previewBtn.addEventListener('click', openPreview);
exportBtn.addEventListener('click', exportTemplate);
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

    setLoading('Running pipeline...');
    disableButtons(true);

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
        canIterate = data.can_iterate;

        // Update UI
        updateResults(data);
        showSuccess('Pipeline completed successfully!');
        loadTemplates(); // Refresh templates list

    } catch (error) {
        showError(error.message);
    } finally {
        setLoading(false);
        disableButtons(false);
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
        loadTemplates(); // Refresh templates list

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
    timestampEl.textContent = data.timestamp;

    // Update outputs
    document.getElementById('researchOutput').textContent = data.research_output;
    document.getElementById('analysisOutput').textContent = data.analysis_output;
    document.getElementById('templateOutput').textContent = data.template_output;

    // Update iterate button
    iterateBtn.disabled = !canIterate;
    iterateBtn.textContent = canIterate ? 'Iterate' : 'Max iterations reached';

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
                <a href="/api/template/${template.timestamp}/export" class="btn btn-small btn-outline" target="_blank">Export</a>
            </div>
        </div>
    `).join('');
}

function setLoading(message) {
    if (message) {
        loadingText.textContent = message;
        loadingModal.style.display = 'flex';
        statusEl.classList.add('processing');
        statusText.textContent = message;
    } else {
        loadingModal.style.display = 'none';
        statusEl.classList.remove('processing');
        statusText.textContent = 'Ready';
    }
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

// Initialize
loadTemplates();