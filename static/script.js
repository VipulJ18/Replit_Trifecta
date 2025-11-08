// DOM Elements
const analyzeForm = document.getElementById('analyze-form');
const prUrlInput = document.getElementById('pr-url');
const analyzeBtn = document.getElementById('analyze-btn');
const resultContainer = document.getElementById('result-container');
const resultContent = document.getElementById('result-content');
const loadingElement = document.getElementById('loading');
const lastCheckedElement = document.getElementById('last-checked');

// Update last checked time
function updateLastChecked() {
    const now = new Date();
    const options = { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    };
    lastCheckedElement.textContent = now.toLocaleDateString('en-US', options);
}

// Show loading state
function showLoading() {
    loadingElement.classList.remove('hidden');
    resultContainer.classList.add('hidden');
    analyzeBtn.disabled = true;
}

// Hide loading state
function hideLoading() {
    loadingElement.classList.add('hidden');
    analyzeBtn.disabled = false;
}

// Show result
function showResult(data) {
    resultContainer.classList.remove('hidden');
    loadingElement.classList.add('hidden');
    
    let icon, title, commentClass;
    switch(data.verdict) {
        case 'CRITICAL':
            icon = '🚨';
            title = 'Critical Issue';
            commentClass = 'critical';
            break;
        case 'NEEDS_REVIEW':
            icon = '👀';
            title = 'Needs Review';
            commentClass = 'review';
            break;
        case 'GOOD':
            icon = '✅';
            title = 'Approved';
            commentClass = 'good';
            break;
        default:
            icon = '❓';
            title = 'Unknown';
            commentClass = 'review';
    }
    
    resultContent.innerHTML = `
        <div class="result-header">
            <span class="result-icon ${commentClass}">${icon}</span>
            <span class="result-title">${title}</span>
        </div>
        <div class="result-comment">${data.comment}</div>
        <a href="${data.pr_url}" class="result-url" target="_blank">View Pull Request</a>
    `;
}

// Show error
function showError(message) {
    resultContainer.classList.remove('hidden');
    loadingElement.classList.add('hidden');
    
    resultContent.innerHTML = `
        <div class="result-header">
            <span class="result-icon critical">❌</span>
            <span class="result-title">Error</span>
        </div>
        <div class="result-comment">${message}</div>
    `;
}

// Analyze PR
async function analyzePR(prUrl) {
    showLoading();
    
    try {
        const response = await fetch('/api/analyze-pr', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ pr_url: prUrl })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showResult(data);
        } else {
            showError(data.message || 'An error occurred while analyzing the PR');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Failed to connect to the server');
    } finally {
        hideLoading();
    }
}

// Initialize the dashboard
document.addEventListener('DOMContentLoaded', () => {
    updateLastChecked();
    
    // Form submission
    analyzeForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const prUrl = prUrlInput.value.trim();
        if (prUrl) {
            analyzePR(prUrl);
        }
    });
    
    // Add hover effects to cards
    const cards = document.querySelectorAll('.card, .integration-card');
    cards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transform = 'translateY(-5px)';
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transform = 'translateY(0)';
        });
    });
});