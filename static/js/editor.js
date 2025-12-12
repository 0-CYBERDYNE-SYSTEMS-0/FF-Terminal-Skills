// Editor state
let isPreviewVisible = false;
let originalContent = '';
let hasUnsavedChanges = false;

// DOM Elements
const editor = document.getElementById('editor');
const previewToggle = document.getElementById('previewToggle');
const saveBtn = document.getElementById('saveBtn');
const previewPane = document.getElementById('previewPane');
const previewContent = document.getElementById('previewContent');

// Event Listeners
previewToggle.addEventListener('click', togglePreview);
saveBtn.addEventListener('click', saveTemplate);
editor.addEventListener('input', handleEditorChange);

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    originalContent = editor.value;
    updatePreview();
});

function togglePreview() {
    isPreviewVisible = !isPreviewVisible;

    if (isPreviewVisible) {
        previewPane.style.display = 'block';
        previewToggle.textContent = 'Hide Preview';
        updatePreview();
    } else {
        previewPane.style.display = 'none';
        previewToggle.textContent = 'Show Preview';
    }
}

function handleEditorChange() {
    hasUnsavedChanges = editor.value !== originalContent;
    saveBtn.textContent = hasUnsavedChanges ? 'Save Changes*' : 'Save Changes';
    saveBtn.disabled = !hasUnsavedChanges;

    if (isPreviewVisible) {
        updatePreview();
    }
}

async function updatePreview() {
    const content = editor.value;

    // Simple markdown to HTML conversion
    const html = markdownToHtml(content);
    previewContent.innerHTML = html;
}

function markdownToHtml(markdown) {
    // This is a simple markdown parser for basic preview
    // In production, use a proper library like marked.js
    let html = markdown;

    // Headers
    html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

    // Bold
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

    // Italic
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Code blocks
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre><code class="language-${lang || 'text'}">${escapeHtml(code.trim())}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`(.+?)`/g, '<code>$1</code>');

    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

    // Line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = '<p>' + html + '</p>';

    // List items
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

    // Clean up empty paragraphs
    html = html.replace(/<p><\/p>/g, '');
    html = html.replace(/<p>(<h[1-6]>)/g, '$1');
    html = html.replace(/(<\/h[1-6]>)<\/p>/g, '$1');

    return html;
}

async function saveTemplate() {
    if (!hasUnsavedChanges) {
        showToast('No changes to save');
        return;
    }

    const content = editor.value;

    try {
        const response = await fetch(`/api/template/${TIMESTAMP}/save`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ content })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to save');
        }

        originalContent = content;
        hasUnsavedChanges = false;
        saveBtn.textContent = 'Save Changes';
        saveBtn.disabled = true;

        showToast('Changes saved successfully!');

    } catch (error) {
        showError(error.message);
    }
}

function showToast(message) {
    const toast = document.getElementById('successToast');
    const messageEl = document.getElementById('successMessage');

    messageEl.textContent = message;
    toast.style.display = 'block';

    setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}

function showError(message) {
    alert(message); // Simple error display
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + S to save
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (hasUnsavedChanges) {
            saveTemplate();
        }
    }

    // Ctrl/Cmd + P to toggle preview
    if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
        e.preventDefault();
        togglePreview();
    }
});

// Warn before leaving if there are unsaved changes
window.addEventListener('beforeunload', (e) => {
    if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = '';
    }
});

// Auto-save functionality (optional)
let autoSaveTimer;
function setupAutoSave() {
    editor.addEventListener('input', () => {
        clearTimeout(autoSaveTimer);
        autoSaveTimer = setTimeout(() => {
            if (hasUnsavedChanges) {
                saveTemplate();
            }
        }, 30000); // Auto-save after 30 seconds of inactivity
    });
}

// Uncomment to enable auto-save
// setupAutoSave();