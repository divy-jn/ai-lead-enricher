const MOCK_DATA = {
  "postman.com": {
    "domain": "postman.com",
    "status": "success",
    "data": {
      "domain": "postman.com",
      "company_overview": "Postman provides an AI‑native API platform that enables developers to design, test, manage, and distribute APIs at enterprise scale. The platform streamlines every stage of the API lifecycle and offers tools such as AI Engineer, API governance, and collaborative workspaces.",
      "target_audience": "Postman's primary audience includes software developers, engineering teams, and enterprises that build, test, and operate APIs.",
      "primary_generic_contacts": ["info@postman.com", "info-jp@postman.com"],
      "other_public_contacts": [],
      "contact_points": ["info-jp@postman.com", "info@postman.com"],
      "leadership": [
        {
          "name": "Abhinav Asthana",
          "role": "CEO and Co‑Founder",
          "linkedin_url": null
        }
      ],
      "confidence_score": 0.9
    },
    "error": null,
    "discovery_method": "homepage_links",
    "pages_discovered": 4,
    "pages_crawled": 5,
    "pages_successful": 5,
    "pages_failed": 0,
    "prompt_tokens": 6968,
    "completion_tokens": 812,
    "total_tokens": 7780
  },
  "supabase.com": {
    "domain": "supabase.com",
    "status": "success",
    "data": {
      "domain": "supabase.com",
      "company_overview": "Supabase is an open‑source Postgres development platform that provides a full managed database with built‑in authentication, real‑time sync, storage, edge functions and vector embeddings. It enables developers to build and scale applications quickly, offering a free tier and paid plans for production workloads.",
      "target_audience": "Developers building applications—from indie projects and startups to enterprise AI and innovation teams—who need a complete Postgres‑based backend.",
      "primary_generic_contacts": [],
      "other_public_contacts": ["abuse@supabase.com", "legal@supabase.com", "privacy@supabase.com", "security@supabase.com"],
      "contact_points": ["abuse@supabase.com", "legal@supabase.com", "privacy@supabase.com", "security@supabase.com"],
      "leadership": [],
      "confidence_score": 0.7
    },
    "error": null,
    "discovery_method": "homepage_links",
    "pages_discovered": 8,
    "pages_crawled": 9,
    "pages_successful": 9,
    "pages_failed": 0,
    "prompt_tokens": 15250,
    "completion_tokens": 377,
    "total_tokens": 15627
  },
  "vapi.ai": {
    "domain": "vapi.ai",
    "status": "success",
    "data": {
      "domain": "vapi.ai",
      "company_overview": "Vapi provides a platform for building, deploying, and managing advanced voice AI agents with ultra‑low latency and enterprise‑grade features. The service offers scalable infrastructure, compliance certifications (SOC 2, HIPAA, PCI) and tools for developers and large organizations to create voice‑first experiences.",
      "target_audience": "Enterprises and developers building voice AI agents across industries such as automotive, healthcare, and finance.",
      "primary_generic_contacts": ["Talent@vapi.ai"],
      "other_public_contacts": [],
      "contact_points": ["Talent@vapi.ai"],
      "leadership": [
        {
          "name": "Jason Mitura",
          "role": "VP of Software Development",
          "linkedin_url": null
        }
      ],
      "confidence_score": 0.9
    },
    "error": null,
    "discovery_method": "homepage_links",
    "pages_discovered": 6,
    "pages_crawled": 7,
    "pages_successful": 7,
    "pages_failed": 0,
    "prompt_tokens": 6623,
    "completion_tokens": 846,
    "total_tokens": 7469
  }
};

// DOM Elements
const btnLoadExamples = document.getElementById('btn-load-examples');
const btnEnrich = document.getElementById('btn-enrich');
const inputDomains = document.getElementById('domains-input');
const demoModeCheckbox = document.getElementById('demo-mode');
const progressSection = document.getElementById('progress-section');
const progressContainer = document.getElementById('progress-container');
const resultsSection = document.getElementById('results-section');
const resultsContainer = document.getElementById('results-container');
const tplProgressCard = document.getElementById('tpl-progress-card');
const agentStatusIndicator = document.getElementById('agent-status-indicator');
const agentStatusDot = agentStatusIndicator.querySelector('.dot');

// Event Listeners
btnLoadExamples.addEventListener('click', () => {
    inputDomains.value = "postman.com\nsupabase.com\nvapi.ai";
});

btnEnrich.addEventListener('click', async () => {
    const text = inputDomains.value.trim();
    if (!text) return;

    const domains = text.split('\n').map(d => d.trim()).filter(d => d);
    if (domains.length === 0) return;

    // Reset UI
    btnEnrich.disabled = true;
    inputDomains.disabled = true;
    resultsSection.classList.add('hidden');
    resultsContainer.innerHTML = '';
    progressContainer.innerHTML = '';
    progressSection.classList.remove('hidden');
    
    // Status Indicator Update
    agentStatusDot.className = 'dot busy';
    agentStatusIndicator.childNodes[1].nodeValue = ' Agent Running';

    // Start Enrichment
    const results = await enrichDomains(domains);
    
    // Show Results
    renderResults(results);
    
    // Reset State
    btnEnrich.disabled = false;
    inputDomains.disabled = false;
    agentStatusDot.className = 'dot ready';
    agentStatusIndicator.childNodes[1].nodeValue = ' Agent Ready';
});

/**
 * Main API function to enrich domains.
 * Currently uses Demo Mode logic if enabled.
 */
async function enrichDomains(domains) {
    const isDemo = demoModeCheckbox.checked;
    
    if (isDemo) {
        return await simulateDemoEnrichment(domains);
    } else {
        // FUTURE: Real API integration goes here.
        // const response = await fetch('/enrich', {
        //     method: 'POST',
        //     headers: { 'Content-Type': 'application/json' },
        //     body: JSON.stringify({ domains })
        // });
        // return await response.json();
        
        alert("Real API integration is not yet connected. Please enable Demo Mode.");
        return [];
    }
}

/**
 * Simulates the enrichment process sequentially for Loom demonstration.
 */
async function simulateDemoEnrichment(domains) {
    const results = [];

    // Create a progress card for each domain first (Waiting state)
    const domainCards = {};
    for (const domain of domains) {
        const clone = tplProgressCard.content.cloneNode(true);
        const card = clone.querySelector('.progress-card');
        card.querySelector('.domain-name').textContent = domain;
        progressContainer.appendChild(card);
        domainCards[domain] = card;
    }

    // Process each domain one by one to show realistic sequential activity
    for (const domain of domains) {
        const card = domainCards[domain];
        const statusBadge = card.querySelector('.status-badge');
        const steps = Array.from(card.querySelectorAll('.progress-steps li'));

        // Start processing this domain
        card.classList.remove('waiting');
        card.classList.add('running');
        statusBadge.textContent = 'Running';

        const mockResult = MOCK_DATA[domain] || {
            domain: domain,
            status: "failed",
            error: "Domain not found in mock data. Real API would attempt to process this."
        };

        const willFail = mockResult.status === "failed";

        // Helper to delay
        const delay = (ms) => new Promise(r => setTimeout(r, ms));

        // Step 1: Browsing
        steps[0].classList.add('active');
        await delay(800 + Math.random() * 500);
        steps[0].classList.remove('active');
        steps[0].classList.add('done');

        // Step 2: Discovering
        steps[1].classList.add('active');
        await delay(600 + Math.random() * 500);
        steps[1].classList.remove('active');
        steps[1].classList.add('done');

        if (willFail) {
            steps[2].classList.add('error');
            card.classList.remove('running');
            card.classList.add('failed');
            statusBadge.textContent = 'Failed';
            results.push(mockResult);
            continue;
        }

        // Step 3: Preprocessing
        steps[2].classList.add('active');
        await delay(700 + Math.random() * 400);
        steps[2].classList.remove('active');
        steps[2].classList.add('done');

        // Step 4: Extracting (LLM) - Takes longer
        steps[3].classList.add('active');
        await delay(1500 + Math.random() * 1000);
        steps[3].classList.remove('active');
        steps[3].classList.add('done');

        // Step 5: Validating
        steps[4].classList.add('active');
        await delay(500 + Math.random() * 300);
        steps[4].classList.remove('active');
        steps[4].classList.add('done');

        card.classList.remove('running');
        card.classList.add('success');
        statusBadge.textContent = 'Success';
        
        results.push(mockResult);
    }
    
    // Add a final short pause before showing results
    await new Promise(r => setTimeout(r, 600));
    return results;
}

/**
 * Renders the final results array into HTML cards.
 */
function renderResults(results) {
    resultsSection.classList.remove('hidden');

    for (const res of results) {
        const resultCard = document.createElement('div');
        resultCard.className = 'result-card';
        
        if (res.status === 'failed') {
            resultCard.innerHTML = `
                <div class="result-header">
                    <h3>${res.domain}</h3>
                    <div class="status-badge" style="background:#fef2f2; color:#ef4444">Failed</div>
                </div>
                <div class="result-error">
                    <strong>⚠ Enrichment failed</strong><br><br>
                    Reason: ${res.error || "Unknown error"}
                </div>
            `;
            resultsContainer.appendChild(resultCard);
            continue;
        }

        const data = res.data;
        const confidencePercent = Math.round(data.confidence_score * 100);
        
        let primaryContactsHtml = '';
        if (data.primary_generic_contacts && data.primary_generic_contacts.length > 0) {
            primaryContactsHtml = `
                <div class="result-section">
                    <h4>Primary Generic Contacts</h4>
                    <div class="chips">
                        ${data.primary_generic_contacts.map(email => `<span class="chip">${email}</span>`).join('')}
                    </div>
                </div>
            `;
        }
        
        let otherContactsHtml = '';
        if (data.other_public_contacts && data.other_public_contacts.length > 0) {
            otherContactsHtml = `
                <div class="result-section">
                    <h4>Other Public Contacts (Legal/Privacy)</h4>
                    <div class="chips">
                        ${data.other_public_contacts.map(email => `<span class="chip">${email}</span>`).join('')}
                    </div>
                </div>
            `;
        }

        let leadershipHtml = '';
        if (data.leadership && data.leadership.length > 0) {
            leadershipHtml = `
                <div class="result-section">
                    <h4>Leadership</h4>
                    <div class="leadership-grid">
                        ${data.leadership.map(person => `
                            <div class="person-card">
                                <div class="person-name">${person.name}</div>
                                <div class="person-role">${person.role}</div>
                                ${person.linkedin_url ? `<a href="${person.linkedin_url}" class="person-link" target="_blank">LinkedIn Profile →</a>` : ''}
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        } else {
            leadershipHtml = `
                <div class="result-section">
                    <h4>Leadership</h4>
                    <p style="color:var(--text-muted); font-size:0.9rem;">Not found</p>
                </div>
            `;
        }

        resultCard.innerHTML = `
            <div class="result-header">
                <h3>${res.domain}</h3>
                <div class="confidence">
                    Confidence: ${confidencePercent}%
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${confidencePercent}%"></div>
                    </div>
                </div>
            </div>
            
            <div class="result-section">
                <h4>Company Overview</h4>
                <p>${data.company_overview}</p>
            </div>
            
            <div class="result-section">
                <h4>Target Audience / ICP</h4>
                <p>${data.target_audience}</p>
            </div>
            
            ${primaryContactsHtml}
            ${otherContactsHtml}
            ${leadershipHtml}
            
            <!-- Agent Details Collapsible -->
            <div class="collapsible">
                <div class="collapsible-header">
                    Agent Details
                    <span class="arrow">▼</span>
                </div>
                <div class="collapsible-content">
                    <div class="metadata-grid">
                        <div class="metadata-item">
                            <span class="metadata-label">Discovery Method</span>
                            <span class="metadata-value">${res.discovery_method || 'N/A'}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="metadata-label">Pages Discovered</span>
                            <span class="metadata-value">${res.pages_discovered}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="metadata-label">Pages Crawled</span>
                            <span class="metadata-value">${res.pages_crawled}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="metadata-label">Pages Successful</span>
                            <span class="metadata-value">${res.pages_successful}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="metadata-label">Pages Failed</span>
                            <span class="metadata-value">${res.pages_failed}</span>
                        </div>
                        <div class="metadata-item">
                            <span class="metadata-label">Total Tokens</span>
                            <span class="metadata-value">${res.total_tokens}</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Sources Used Collapsible (Placeholder as output.json doesn't contain individual crawled URLs) -->
            <div class="collapsible">
                <div class="collapsible-header">
                    Sources Used
                    <span class="arrow">▼</span>
                </div>
                <div class="collapsible-content">
                    <p style="color:var(--text-muted); font-style:italic;">Detailed source URLs are tracked internally during the crawl phase.</p>
                </div>
            </div>
        `;
        
        // Add listeners for collapsibles
        const collapsibles = resultCard.querySelectorAll('.collapsible-header');
        collapsibles.forEach(header => {
            header.addEventListener('click', () => {
                header.parentElement.classList.toggle('open');
            });
        });

        resultsContainer.appendChild(resultCard);
    }
}
