document.addEventListener('DOMContentLoaded', () => {
    const domainInput = document.getElementById('domain-input');
    const loadExamplesBtn = document.getElementById('load-examples-btn');
    const enrichBtn = document.getElementById('enrich-btn');
    const demoModeToggle = document.getElementById('demo-mode-toggle');
    const demoBadge = document.getElementById('demo-badge');
    const agentActivitySection = document.getElementById('agent-activity-section');
    const activityContainer = document.getElementById('activity-container');
    const resultsSection = document.getElementById('results-section');

    const activityTemplate = document.getElementById('activity-template');
    const resultTemplate = document.getElementById('result-template');

    // UI Interactions
    demoModeToggle.addEventListener('change', (e) => {
        demoBadge.textContent = e.target.checked ? 'ON' : 'OFF';
        demoBadge.style.background = e.target.checked ? 'var(--accent)' : 'var(--text-secondary)';
    });

    loadExamplesBtn.addEventListener('click', () => {
        domainInput.value = "postman.com\nsupabase.com\nvapi.ai";
    });

    document.getElementById('add-domain-btn').addEventListener('click', () => {
        domainInput.focus();
    });

    // Helper: Expand/Collapse
    function setupCollapsible(card) {
        const btns = card.querySelectorAll('.collapsible-btn');
        btns.forEach(btn => {
            btn.addEventListener('click', function() {
                this.classList.toggle('active');
                const content = this.nextElementSibling;
                if (content.classList.contains('active')) {
                    content.classList.remove('active');
                    this.textContent = this.textContent.replace('▲', '▼');
                } else {
                    content.classList.add('active');
                    this.textContent = this.textContent.replace('▼', '▲');
                }
            });
        });
    }

    // Main Action
    enrichBtn.addEventListener('click', async () => {
        const text = domainInput.value.trim();
        if (!text) return;

        const domains = text.split('\n').map(d => d.trim()).filter(d => d);
        if (domains.length === 0) return;

        enrichBtn.disabled = true;
        enrichBtn.textContent = 'Processing...';
        
        agentActivitySection.classList.remove('hidden');
        activityContainer.innerHTML = '';
        resultsSection.innerHTML = '';

        if (demoModeToggle.checked) {
            await runDemoMode(domains);
        } else {
            await enrichDomains(domains);
        }

        enrichBtn.disabled = false;
        enrichBtn.textContent = 'Enrich Companies';
    });

    // Future Real Backend Integration
    async function enrichDomains(domains) {
        alert("Real backend integration not implemented in Demo Mode.");
    }

    // Demo Mode Simulation
    async function runDemoMode(domains) {
        try {
            // Fetch the real output.json from the repository root
            const response = await fetch('/output/output.json');
            if (!response.ok) throw new Error("output.json not found");
            const outputData = await response.json();
            
            for (const domain of domains) {
                // Find matching data in output.json, or create a failed stub
                const dataMatch = outputData.domains.find(d => d.domain === domain) || {
                    domain: domain,
                    status: "failed",
                    error: "Domain not found in demo sample data."
                };

                await simulateAgentActivity(domain);
                renderResult(dataMatch);
            }
        } catch (e) {
            console.error(e);
            alert("Error loading demo data. Make sure python -m http.server is running from the root directory.");
        }
    }

    const STEPS = [
        "Browsing website",
        "Discovering relevant pages",
        "Cleaning / preprocessing",
        "Extracting company information",
        "Validating output"
    ];

    function delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    async function simulateAgentActivity(domain) {
        const clone = activityTemplate.content.cloneNode(true);
        const block = clone.querySelector('.activity-block');
        block.querySelector('.activity-domain').textContent = domain;
        const ul = block.querySelector('.activity-steps');
        
        activityContainer.appendChild(block);

        for (const step of STEPS) {
            const li = document.createElement('li');
            li.innerHTML = `<span>→</span> ${step}...`;
            ul.appendChild(li);
            
            // Scroll to bottom of activity container
            activityContainer.scrollTop = activityContainer.scrollHeight;
            
            await delay(400); // short delay for demo
            
            li.innerHTML = `<span>✓</span> ${step}`;
            li.classList.add('step-done');
        }

        const li = document.createElement('li');
        li.innerHTML = `<span>✓</span> Completed`;
        li.classList.add('step-done');
        li.style.fontWeight = '600';
        ul.appendChild(li);
        
        await delay(300);
    }

    function renderResult(resultData) {
        const clone = resultTemplate.content.cloneNode(true);
        const card = clone.querySelector('.result-card');
        
        card.querySelector('.result-domain').textContent = resultData.domain;
        
        const statusEl = card.querySelector('.result-status');
        if (resultData.status === 'success') {
            statusEl.textContent = '✓ SUCCESS';
            statusEl.className = 'result-status status-success';
        } else if (resultData.status === 'partial') {
            statusEl.textContent = '◐ PARTIAL';
            statusEl.className = 'result-status status-partial';
        } else {
            statusEl.textContent = '⚠ FAILED';
            statusEl.className = 'result-status status-failed';
        }

        const body = card.querySelector('.result-body');
        const errorBody = card.querySelector('.error-body');

        if (resultData.status === 'failed') {
            body.classList.add('hidden');
            errorBody.classList.remove('hidden');
            errorBody.querySelector('.error-reason').textContent = resultData.error || "Unknown error";
        } else {
            const data = resultData.data || {};
            
            // Confidence
            const confVal = (data.confidence_score !== undefined ? data.confidence_score * 100 : 0);
            card.querySelector('.confidence-value').textContent = `${confVal}%`;
            // Trigger animation shortly after insertion
            setTimeout(() => {
                card.querySelector('.confidence-bar-fill').style.width = `${confVal}%`;
                // Color grading
                if (confVal < 50) card.querySelector('.confidence-bar-fill').style.backgroundColor = 'var(--danger)';
                else if (confVal < 80) card.querySelector('.confidence-bar-fill').style.backgroundColor = 'var(--warning)';
            }, 100);

            // Sections
            if (data.company_overview) {
                card.querySelector('.company-overview').textContent = data.company_overview;
            } else {
                card.querySelector('.company-overview-section').classList.add('hidden');
            }

            if (data.target_audience) {
                card.querySelector('.target-audience').textContent = data.target_audience;
            } else {
                card.querySelector('.target-audience-section').classList.add('hidden');
            }

            // Chips
            const renderChips = (selector, arr) => {
                const container = card.querySelector(selector);
                if (!arr || arr.length === 0) {
                    container.parentElement.classList.add('hidden');
                    return;
                }
                arr.forEach(text => {
                    const el = document.createElement('span');
                    el.className = 'chip';
                    el.textContent = `[${text}]`;
                    container.appendChild(el);
                });
            };

            renderChips('.primary-contacts', data.primary_generic_contacts);
            renderChips('.other-contacts', data.other_public_contacts);

            // Leadership
            const leadContainer = card.querySelector('.leadership-list');
            if (!data.leadership || data.leadership.length === 0) {
                card.querySelector('.leadership-section').classList.add('hidden');
            } else {
                data.leadership.forEach(l => {
                    const item = document.createElement('div');
                    item.className = 'leadership-item';
                    let html = `<div class="leadership-name">${l.name}</div>`;
                    if (l.role) html += `<div class="leadership-role">${l.role}</div>`;
                    if (l.linkedin_url) {
                        html += `<a href="${l.linkedin_url}" target="_blank" class="linkedin-link">LinkedIn ↗</a>`;
                    }
                    item.innerHTML = html;
                    leadContainer.appendChild(item);
                });
            }

            // Agent Details
            const detailsHtml = `
                <div class="metrics-grid">
                    <div class="metric"><span class="metric-label">Discovery Method</span><span class="metric-value">${resultData.discovery_method || 'N/A'}</span></div>
                    <div class="metric"><span class="metric-label">Pages Discovered</span><span class="metric-value">${resultData.pages_discovered || 0}</span></div>
                    <div class="metric"><span class="metric-label">Pages Crawled</span><span class="metric-value">${resultData.pages_crawled || 0}</span></div>
                    <div class="metric"><span class="metric-label">Pages Successful</span><span class="metric-value">${resultData.pages_successful || 0}</span></div>
                    <div class="metric"><span class="metric-label">Pages Failed</span><span class="metric-value">${resultData.pages_failed || 0}</span></div>
                    <div class="metric"><span class="metric-label">Prompt Tokens</span><span class="metric-value">${resultData.prompt_tokens || 0}</span></div>
                    <div class="metric"><span class="metric-label">Completion Tokens</span><span class="metric-value">${resultData.completion_tokens || 0}</span></div>
                    <div class="metric"><span class="metric-label">Total Tokens</span><span class="metric-value">${resultData.total_tokens || 0}</span></div>
                </div>
            `;
            card.querySelector('.agent-details').innerHTML = detailsHtml;

            // Sources
            let sourcesHtml = '';
            
            const renderSourcesList = (title, urls) => {
                if (!urls || urls.length === 0) return '';
                let s = `<div class="source-title">${title}</div><ul class="source-list">`;
                urls.forEach(u => {
                    s += `<li>✓ <a href="${u}" target="_blank">${u}</a></li>`;
                });
                s += `</ul>`;
                return s;
            };

            sourcesHtml += renderSourcesList('All Sources', data.source_urls);
            sourcesHtml += renderSourcesList('Company Sources', data.company_source_urls);
            sourcesHtml += renderSourcesList('Contact Sources', data.contact_source_urls);
            sourcesHtml += renderSourcesList('Leadership Sources', data.leadership_source_urls);

            if (!sourcesHtml) sourcesHtml = 'No sources available.';
            card.querySelector('.sources-content').innerHTML = sourcesHtml;
        }

        setupCollapsible(card);
        resultsSection.appendChild(card);
    }
});
