// State Management
let currentTab = 'installed-tools';
let allTools = [];
let selectedToolId = null;
let drawerLogType = 'run'; // 'run' or 'setup'
let logPollInterval = null;
let dashboardPollInterval = null;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    switchTab(currentTab);
    
    // Set up hotkeys for main menu (1 to 5)
    document.addEventListener('keydown', (e) => {
        // Skip hotkeys if input elements are focused
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement.tagName)) {
            return;
        }
        if (e.key === '1') switchTab('installed-tools');
        if (e.key === '2') switchTab('add-tool');
        if (e.key === '3') switchTab('containers');
        if (e.key === '4') switchTab('logs');
        if (e.key === '5') switchTab('settings');
        if (e.key === '0' && selectedToolId) closeDrawer();
    });

    // Start auto polling for dashboard status updates (runs every 3 seconds)
    dashboardPollInterval = setInterval(pollDashboardStatuses, 3000);
});

// Tab Switching
function switchTab(tabId) {
    currentTab = tabId;
    
    // Update active nav button
    document.querySelectorAll('.nav-item').forEach(btn => {
        btn.classList.remove('active');
    });
    
    const navBtn = Array.from(document.querySelectorAll('.nav-item')).find(btn => 
        btn.onclick.toString().includes(`'${tabId}'`)
    );
    if (navBtn) navBtn.classList.add('active');

    // Update tab view visibility
    document.querySelectorAll('.tab-view').forEach(view => {
        view.classList.remove('active');
    });
    document.getElementById(`${tabId}-view`).classList.add('active');

    // Update Header Title
    const headerTitleMap = {
        'installed-tools': 'INSTALLED TOOLS',
        'add-tool': 'ADD TOOL SANDBOX',
        'containers': 'ISOLATION CONTAINERS',
        'logs': 'GLOBAL LOGS CONSOLE',
        'settings': 'SYSTEM SETTINGS'
    };
    document.getElementById('tab-title').innerText = headerTitleMap[tabId];

    // Trigger tab-specific loads
    if (tabId === 'installed-tools') {
        loadToolsGrid();
    } else if (tabId === 'containers') {
        loadContainersReport();
    } else if (tabId === 'logs') {
        loadLogsToolsSelect();
    } else if (tabId === 'settings') {
        loadSettings();
    }
}

// Fetch Tools List
async function fetchTools() {
    try {
        const response = await fetch('/api/tools');
        if (!response.ok) throw new Error("Failed to fetch tools.");
        allTools = await response.json();
        return allTools;
    } catch (err) {
        console.error("Error loading tools:", err);
        return [];
    }
}

// Load and Render Tools Grid
async function loadToolsGrid() {
    const grid = document.getElementById('tools-grid');
    const noToolsMsg = document.getElementById('no-tools-message');
    grid.innerHTML = '<div style="color:var(--text-muted)">Loading tools...</div>';
    
    const tools = await fetchTools();
    grid.innerHTML = '';
    
    if (tools.length === 0) {
        noToolsMsg.style.display = 'flex';
        grid.style.display = 'none';
        return;
    }
    
    noToolsMsg.style.display = 'none';
    grid.style.display = 'grid';
    
    tools.forEach(tool => {
        const card = createToolCard(tool);
        grid.appendChild(card);
    });
    
    // Apply filters if search input has text
    filterTools();
}

// Dynamic Card Builder
function createToolCard(tool) {
    const card = document.createElement('div');
    card.className = 'cyber-card';
    card.onclick = () => openToolDrawer(tool.id);
    
    // Status color class
    let pulseClass = 'gray';
    let statusText = 'Stopped';
    
    if (tool.status === 'Running') {
        pulseClass = 'green';
        statusText = 'Running';
    } else if (tool.status === 'Installing' || tool.status === 'Updating') {
        pulseClass = 'yellow';
        statusText = tool.status === 'Installing' ? 'Installing...' : 'Updating...';
    } else if (tool.status === 'Setup Error') {
        pulseClass = 'red';
        statusText = 'Setup Error';
    } else if (tool.status === 'Installed') {
        pulseClass = 'gray';
        statusText = 'Installed';
    }
    
    let langBadgeClass = '';
    const langLower = tool.language.toLowerCase();
    if (langLower.includes(',')) {
        langBadgeClass = 'multi';
    } else if (langLower === 'python') {
        langBadgeClass = 'python';
    } else if (langLower === 'rust') {
        langBadgeClass = 'rust';
    } else if (langLower === 'c' || langLower === 'c++') {
        langBadgeClass = 'c';
    }
    
    card.innerHTML = `
        <div class="card-header">
            <h3 class="card-title">${tool.name}</h3>
            <span class="card-lang-badge ${langBadgeClass}">${tool.language.toUpperCase()}</span>
        </div>
        <p class="card-desc">${tool.description || 'No description provided.'}</p>
        <div class="card-footer">
            <div class="card-status-wrapper">
                <span class="pulse-indicator ${pulseClass}"></span>
                <span class="card-status-text ${tool.status.toLowerCase()}">${statusText}</span>
            </div>
            <button class="cyber-btn" onclick="event.stopPropagation(); openToolDrawer('${tool.id}')">
                MANAGE <i class="fa-solid fa-angle-right"></i>
            </button>
        </div>
    `;
    
    return card;
}

// Filter Tools via Search Input
function filterTools() {
    const query = document.getElementById('search-input').value.toLowerCase();
    const cards = document.querySelectorAll('.tools-grid .cyber-card');
    
    cards.forEach((card, index) => {
        const tool = allTools[index];
        if (!tool) return;
        
        const matchName = tool.name.toLowerCase().includes(query);
        const matchDesc = tool.description.toLowerCase().includes(query);
        const matchLang = tool.language.toLowerCase().includes(query);
        const matchStatus = tool.status.toLowerCase().includes(query);
        
        if (matchName || matchDesc || matchLang || matchStatus) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
}

// Polling updates for main screen
async function pollDashboardStatuses() {
    if (currentTab !== 'installed-tools' && currentTab !== 'containers') return;
    
    try {
        const response = await fetch(currentTab === 'installed-tools' ? '/api/tools' : '/api/containers');
        if (!response.ok) return;
        
        if (currentTab === 'installed-tools') {
            const freshTools = await response.json();
            allTools = freshTools;
            
            // Check if tool counts changed, if so full re-render
            const cards = document.querySelectorAll('.tools-grid .cyber-card');
            if (cards.length !== freshTools.length) {
                loadToolsGrid();
                return;
            }
            
            // Update individual cards fields to avoid complete DOM re-generation blink
            freshTools.forEach((tool, idx) => {
                const card = cards[idx];
                if (!card) return;
                
                // Update status indicator ring class
                const pulse = card.querySelector('.pulse-indicator');
                const statusTxt = card.querySelector('.card-status-text');
                if (pulse && statusTxt) {
                    pulse.className = 'pulse-indicator';
                    statusTxt.className = 'card-status-text';
                    
                    if (tool.status === 'Running') {
                        pulse.classList.add('green');
                        statusTxt.classList.add('running');
                        statusTxt.innerText = 'Running';
                    } else if (tool.status === 'Installing' || tool.status === 'Updating') {
                        pulse.classList.add('yellow');
                        statusTxt.classList.add('installing');
                        statusTxt.innerText = tool.status === 'Installing' ? 'Installing...' : 'Updating...';
                    } else if (tool.status === 'Setup Error') {
                        pulse.classList.add('red');
                        statusTxt.classList.add('setup_error');
                        statusTxt.innerText = 'Setup Error';
                    } else {
                        pulse.classList.add('gray');
                        statusTxt.classList.add('installed');
                        statusTxt.innerText = tool.status;
                    }
                }
            });
        } else {
            // Re-render containers report table silently
            const report = await response.json();
            renderContainersTable(report);
        }
    } catch (e) {
        console.warn("Poll failed", e);
    }
}

// Add Tool Handler
async function handleAddTool(event) {
    event.preventDefault();
    const submitBtn = document.getElementById('add-submit-btn');
    
    const name = document.getElementById('tool-name').value;
    const source = document.getElementById('tool-source').value;
    const description = document.getElementById('tool-desc').value;
    const language = document.getElementById('tool-lang').value;
    const container_path = document.getElementById('tool-container-path').value;
    
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> CREATING SANDBOX...';
    
    try {
        const response = await fetch('/api/tools', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, source, description, language, container_path })
        });
        
        const resData = await response.json();
        
        if (response.ok) {
            alert(`Success: ${resData.message}`);
            // Reset form
            document.getElementById('add-tool-form').reset();
            // Redirect to dashboard
            switchTab('installed-tools');
        } else {
            alert(`Error: ${resData.error}`);
        }
    } catch (err) {
        alert(`Request failed: ${err}`);
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<i class="fa-solid fa-box-open"></i> CREATE ISOLATED SANDBOX';
    }
}

// Containers tab loader
async function loadContainersReport() {
    const tbody = document.getElementById('containers-table-body');
    tbody.innerHTML = '<tr><td colspan="5" style="color:var(--text-muted)">Loading report...</td></tr>';
    
    try {
        const response = await fetch('/api/containers');
        if (!response.ok) throw new Error("Containers load failed.");
        const data = await response.json();
        renderContainersTable(data);
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" style="color:var(--primary-color)">Error: ${e.message}</td></tr>`;
    }
}

function renderContainersTable(data) {
    const tbody = document.getElementById('containers-table-body');
    tbody.innerHTML = '';
    
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted)">No containers built yet.</td></tr>';
        return;
    }
    
    data.forEach(item => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${item.tool_name}</strong></td>
            <td><code>${item.language.toUpperCase()}_ENV</code></td>
            <td><code>${item.container_path}</code></td>
            <td>${item.size_mb} MB</td>
            <td>
                <span class="pulse-indicator ${item.status === 'Running' ? 'green' : (item.status === 'Setup Error' ? 'red' : 'gray')}" style="vertical-align:middle; margin-right:5px"></span>
                <span style="font-family:var(--font-mono); font-size:11px">${item.status}</span>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

// Logs Select Dropdown Populating
async function loadLogsToolsSelect() {
    const select = document.getElementById('logs-tool-select');
    select.innerHTML = '<option value="">-- Loading Tools --</option>';
    
    const tools = await fetchTools();
    select.innerHTML = '<option value="">-- Select Installed Tool --</option>';
    
    tools.forEach(tool => {
        const opt = document.createElement('option');
        opt.value = tool.id;
        opt.innerText = tool.name;
        select.appendChild(opt);
    });
}

// Global Logs View Loader
async function loadGlobalLogs() {
    const toolId = document.getElementById('logs-tool-select').value;
    const logType = document.getElementById('logs-type-select').value;
    const consoleBox = document.getElementById('global-terminal-console');
    const terminalTitle = document.getElementById('terminal-log-title');
    const cliContainer = document.getElementById('global-cli-container');
    
    if (!toolId) {
        consoleBox.innerText = 'Select a tool above to view sandboxed execution output.';
        terminalTitle.innerText = 'CONSOLE_STREAM: None';
        if (cliContainer) cliContainer.style.display = 'none';
        return;
    }
    
    if (cliContainer) cliContainer.style.display = 'flex';
    
    terminalTitle.innerText = `CONSOLE_STREAM: ${toolId}_${logType}.log`;
    
    try {
        const response = await fetch(`/api/tools/${toolId}/logs/${logType}`);
        if (!response.ok) throw new Error("Logs retrieval failed.");
        const data = await response.json();
        
        consoleBox.innerText = data.logs || 'Console stream is currently empty.';
        // Auto scroll to bottom
        consoleBox.scrollTop = consoleBox.scrollHeight;
    } catch (e) {
        consoleBox.innerText = `[ZEROSPACE ERROR] Failed to fetch log contents: ${e.message}`;
    }
}

// Drawer Controller Functionality
async function openToolDrawer(toolId) {
    selectedToolId = toolId;
    drawerLogType = 'run'; // default
    
    // Toggle active state on overlays
    document.getElementById('drawer-overlay').classList.add('active');
    document.getElementById('tool-drawer').classList.add('active');
    
    // Clear any active timers
    if (logPollInterval) clearInterval(logPollInterval);
    
    // Reset toggle button displays
    document.getElementById('toggle-run-logs').classList.add('active');
    document.getElementById('toggle-setup-logs').classList.remove('active');
    
    const drawerCli = document.getElementById('drawer-cli-container');
    if (drawerCli) drawerCli.style.display = 'flex';
    
    await refreshDrawerDetails();
    
    // Setup log polling loop (every 1.5 seconds)
    logPollInterval = setInterval(pollDrawerLogs, 1500);
}

function closeDrawer() {
    selectedToolId = null;
    document.getElementById('drawer-overlay').classList.remove('active');
    document.getElementById('tool-drawer').classList.remove('active');
    
    const drawerCli = document.getElementById('drawer-cli-container');
    if (drawerCli) drawerCli.style.display = 'none';
    const drawerCliInput = document.getElementById('drawer-cli-input');
    if (drawerCliInput) drawerCliInput.value = '';
    
    if (logPollInterval) {
        clearInterval(logPollInterval);
        logPollInterval = null;
    }
    
    // Reload main views to sync changes
    if (currentTab === 'installed-tools') loadToolsGrid();
    else if (currentTab === 'containers') loadContainersReport();
}

// Refresh Drawer Content
async function refreshDrawerDetails() {
    if (!selectedToolId) return;
    
    try {
        const response = await fetch(`/api/tools/${selectedToolId}`);
        if (!response.ok) throw new Error("Failed to load details.");
        const tool = await response.json();
        
        // Header Status Pulse
        const pulse = document.getElementById('drawer-status-pulse');
        pulse.className = 'pulse-indicator';
        if (tool.status === 'Running') pulse.classList.add('green');
        else if (tool.status === 'Installing' || tool.status === 'Updating') pulse.classList.add('yellow');
        else if (tool.status === 'Setup Error') pulse.classList.add('red');
        else pulse.classList.add('gray');
        
        // Details
        document.getElementById('drawer-tool-name').innerText = tool.name;
        document.getElementById('info-status').innerText = tool.status;
        document.getElementById('info-lang').innerText = `${tool.language.toUpperCase()} (Sandbox environment)`;
        document.getElementById('info-source').innerText = tool.source;
        document.getElementById('info-source').title = tool.source;
        document.getElementById('info-container').innerText = tool.container_path;
        document.getElementById('info-container').title = tool.container_path;
        document.getElementById('info-entry').innerText = tool.entrypoint;
        document.getElementById('info-dep-file').innerText = tool.dependencies_file || 'None';
        document.getElementById('tool-args').value = tool.last_args || '';
        
        // Hide run button if tool is currently running
        const runBtn = document.getElementById('btn-run-tool');
        const stopBtn = document.getElementById('btn-stop-tool');
        if (tool.status === 'Running') {
            runBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            runBtn.disabled = false;
            stopBtn.disabled = true;
        }
        
        // Disable Run/Stop if environment is installing/updating
        if (tool.status === 'Installing' || tool.status === 'Updating') {
            runBtn.disabled = true;
            stopBtn.disabled = true;
        }
        
        // Dependencies badges
        const badgesContainer = document.getElementById('drawer-dependencies-list');
        badgesContainer.innerHTML = '';
        if (tool.dependencies && tool.dependencies.length > 0) {
            tool.dependencies.forEach(dep => {
                const span = document.createElement('span');
                span.className = 'dep-badge';
                span.innerText = dep;
                badgesContainer.appendChild(span);
            });
        } else {
            badgesContainer.innerHTML = '<span style="color:var(--text-muted); font-size:12px">No static dependencies declared.</span>';
        }
        
        // Set initial logs
        await pollDrawerLogs();
    } catch (e) {
        console.error(e);
        document.getElementById('drawer-console-output').innerText = `Error: ${e.message}`;
    }
}

// Logs polling inside drawer
async function pollDrawerLogs() {
    if (!selectedToolId) return;
    
    try {
        const response = await fetch(`/api/tools/${selectedToolId}/logs/${drawerLogType}`);
        if (!response.ok) return;
        const data = await response.json();
        
        const consoleOut = document.getElementById('drawer-console-output');
        consoleOut.innerText = data.logs || 'Console output empty.';
        // Auto scroll to bottom
        consoleOut.scrollTop = consoleOut.scrollHeight;
    } catch (e) {
        console.warn("Logs poll failed", e);
    }
}

function setDrawerLogType(type) {
    drawerLogType = type;
    
    const runBtn = document.getElementById('toggle-run-logs');
    const setupBtn = document.getElementById('toggle-setup-logs');
    
    if (type === 'run') {
        runBtn.classList.add('active');
        setupBtn.classList.remove('active');
    } else {
        runBtn.classList.remove('active');
        setupBtn.classList.add('active');
    }
    
    // Refresh log content immediately
    pollDrawerLogs();
}

// Drawer tool lifecycle actions
async function executeToolAction(action) {
    if (!selectedToolId) return;
    
    let url = `/api/tools/${selectedToolId}/${action}`;
    let method = 'POST';
    let body = null;
    
    if (action === 'remove') {
        if (!confirm("Are you sure you want to remove this tool? This will erase all source code and the isolated environment folder.")) {
            return;
        }
        url = `/api/tools/${selectedToolId}`;
        method = 'DELETE';
    } else if (action === 'run') {
        const args = document.getElementById('tool-args').value;
        body = JSON.stringify({ args });
    }
    
    try {
        const response = await fetch(url, {
            method,
            headers: body ? { 'Content-Type': 'application/json' } : {},
            body
        });
        
        const resData = await response.json();
        
        if (response.ok) {
            if (action === 'remove') {
                closeDrawer();
                loadToolsGrid();
            } else {
                // Refresh drawer to capture status changes
                await refreshDrawerDetails();
            }
        } else {
            alert(`Action failed: ${resData.error}`);
        }
    } catch (err) {
        alert(`Network request failed: ${err}`);
    }
}

// Settings tab reset database
async function resetDatabase() {
    if (!confirm("WARNING: This will permanently remove all installed cybersecurity tools, active containers/environments, and execution logs. Proceed?")) {
        return;
    }
    
    try {
        // We delete all tools in our DB using standard iteration
        const tools = await fetchTools();
        for (const tool of tools) {
            await fetch(`/api/tools/${tool.id}`, { method: 'DELETE' });
        }
        alert("System environment reset completed successfully.");
        switchTab('installed-tools');
    } catch (e) {
        alert("Failed to reset system databases: " + e.message);
    }
}

// Settings tab load paths
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        if (!response.ok) throw new Error("Failed to fetch settings.");
        const data = await response.json();
        
        document.getElementById('settings-tools-path').value = data.tools_path || '';
        document.getElementById('settings-containers-path').value = data.containers_path || '';
        document.getElementById('settings-logs-path').value = data.logs_path || '';
    } catch (e) {
        console.error("Error loading settings:", e);
    }
}

// Settings tab save paths
async function saveSettings(event) {
    event.preventDefault();
    const tools_path = document.getElementById('settings-tools-path').value;
    const containers_path = document.getElementById('settings-containers-path').value;
    const logs_path = document.getElementById('settings-logs-path').value;
    
    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tools_path, containers_path, logs_path })
        });
        const resData = await response.json();
        if (response.ok) {
            alert(resData.message || "Settings saved successfully.");
        } else {
            alert("Error: " + resData.error);
        }
    } catch (err) {
        alert("Failed to save settings: " + err);
    }
}

// CLI Interactive Functions
async function postCliCommand(toolId, command, inputElement, logTypeSelect, refreshCallback) {
    if (!command.trim()) return;
    
    inputElement.disabled = true;
    
    try {
        const response = await fetch(`/api/tools/${toolId}/cli`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        
        const resData = await response.json();
        
        if (response.ok) {
            inputElement.value = '';
            // Change log type select to 'setup' so setup logs stream can be viewed
            if (logTypeSelect) {
                logTypeSelect.value = 'setup';
                if (logTypeSelect.onchange) logTypeSelect.onchange();
            }
            // Trigger refresh Callback immediately
            if (refreshCallback) refreshCallback();
        } else {
            alert(`CLI execution error: ${resData.error}`);
        }
    } catch (err) {
        alert(`Failed to send command: ${err}`);
    } finally {
        inputElement.disabled = false;
        inputElement.focus();
    }
}

function executeGlobalCli() {
    const toolId = document.getElementById('logs-tool-select').value;
    const inputElement = document.getElementById('global-cli-input');
    const logTypeSelect = document.getElementById('logs-type-select');
    if (!toolId) return;
    postCliCommand(toolId, inputElement.value, inputElement, logTypeSelect, loadGlobalLogs);
}

function handleGlobalCliKeydown(e) {
    if (e.key === 'Enter') {
        executeGlobalCli();
    }
}

function executeDrawerCli() {
    if (!selectedToolId) return;
    const inputElement = document.getElementById('drawer-cli-input');
    postCliCommand(selectedToolId, inputElement.value, inputElement, null, () => {
        setDrawerLogType('setup');
    });
}

function handleDrawerCliKeydown(e) {
    if (e.key === 'Enter') {
        executeDrawerCli();
    }
}
