
/**
 * AudioFormation Dashboard Logic.
 */

const API_BASE = '/api';

const app = {
    currentProject: null,
    currentData: null, // Full JSON object
    currentStatus: null, // Pipeline status object
    selectedChapterIndex: -1,
    wavesurfer: null,
    pollInterval: null,

    init() {
        // Check hash to determine view (rudimentary routing)
        this.fetchProjects();
    },

    // ──────────────────────────────────────────────
    // Projects List
    // ──────────────────────────────────────────────

    async fetchProjects() {
        const grid = document.getElementById('project-grid');
        
        try {
            const response = await fetch(`${API_BASE}/projects`);
            if (!response.ok) throw new Error('API Error');
            const projects = await response.json();
            this.renderProjects(projects);
        } catch (e) {
            console.error(e);
            grid.innerHTML = '<div class="card" style="border-color: red; color: red;">Failed to load projects. Is server running?</div>';
        }
    },

    renderProjects(projects) {
        const grid = document.getElementById('project-grid');
        grid.innerHTML = '';

        // "New Project" Card
        const newCard = document.createElement('div');
        newCard.className = 'card new-project';
        newCard.innerHTML = '<span>+ New Project</span>';
        newCard.onclick = () => this.createProject();
        grid.appendChild(newCard);

        // Project Cards
        projects.forEach(p => {
            const card = document.createElement('div');
            card.className = 'card project';
            
            // Format date
            const date = new Date(p.created).toLocaleDateString();
            
            // Status class
            let statusClass = 'pending';
            if (['complete', 'export', 'qc_final'].includes(p.pipeline_node)) statusClass = 'complete';
            if (p.pipeline_node === 'failed') statusClass = 'failed';
            if (p.pipeline_node === 'partial') statusClass = 'partial';

            // Create card content securely using DOM manipulation
            const titleEl = document.createElement('h3');
            titleEl.textContent = p.id;
            
            const metaEl = document.createElement('div');
            metaEl.style.cssText = 'font-size: 0.85rem; color: #888; margin-bottom: 0.5rem;';
            metaEl.textContent = `Created: ${date}`;
            
            const metaInfoEl = document.createElement('div');
            metaInfoEl.className = 'meta';
            
            const chaptersEl = document.createElement('span');
            chaptersEl.textContent = `${p.chapters} Chs • ${p.languages.join(', ')}`;
            
            const statusEl = document.createElement('span');
            statusEl.className = `status-badge ${statusClass}`;
            statusEl.textContent = p.pipeline_node;
            
            metaInfoEl.appendChild(chaptersEl);
            metaInfoEl.appendChild(statusEl);
            
            card.appendChild(titleEl);
            card.appendChild(metaEl);
            card.appendChild(metaInfoEl);
            
            card.onclick = () => this.loadProject(this.escapeHtml(p.id));
            grid.appendChild(card);
        });
    },

    async createProject() {
        const name = prompt("Enter new project ID (alphanumeric, no spaces):");
        if (!name) return;

        if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
            alert("Invalid ID. Use only letters, numbers, underscores, and hyphens.");
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/projects`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: name })
            });

            if (res.ok) {
                this.fetchProjects(); 
            } else {
                const err = await res.json();
                alert(`Error: ${err.detail}`);
            }
        } catch (e) {
            alert("Failed to create project. Check server connection.");
        }
    },
    
    refreshProjects() {
        const grid = document.getElementById('project-grid');
        grid.innerHTML = '<div class="card loading">Refreshing...</div>';
        this.fetchProjects();
    },

    // ──────────────────────────────────────────────
    // Editor Logic
    // ──────────────────────────────────────────────

    async loadProject(id) {
        try {
            // Load config AND status
            const [projRes, statRes] = await Promise.all([
                fetch(`${API_BASE}/projects/${id}`),
                fetch(`${API_BASE}/projects/${id}/status`)
            ]);

            if (!projRes.ok) throw new Error('Failed to load project config');
            
            this.currentProject = id;
            this.currentData = await projRes.json();
            this.currentStatus = statRes.ok ? await statRes.json() : null;
            
            // Populate both views initially
            this.renderForm();
            this.renderJson();
            
            // Reset tab state
            this.switchTab('config', true); // true = skip sync logic
            this.showEditor();
            
            // Update Mix link state
            const mixLink = document.getElementById('nav-mix');
            mixLink.classList.remove('disabled');
            mixLink.onclick = () => this.showMix();

        } catch (e) {
            alert(e.message);
        }
    },

    renderForm() {
        const d = this.currentData;
        document.getElementById('editor-project-id').innerText = d.id;

        // Config
        const gen = d.generation || {};
        document.getElementById('conf-chunk-chars').value = gen.chunk_max_chars || 200;
        document.getElementById('conf-crossfade').value = gen.crossfade_ms || 120;
        document.getElementById('conf-strategy').value = gen.chunk_strategy || 'breath_group';
        document.getElementById('conf-fail-thresh').value = gen.fail_threshold_percent || 5;

        const mix = d.mix || {};
        document.getElementById('conf-lufs').value = mix.target_lufs || -16.0;
        document.getElementById('conf-vol').value = mix.master_volume || 0.9;

        // Chapters List
        const chList = document.getElementById('chapter-list');
        chList.innerHTML = '';
        (d.chapters || []).forEach((ch, idx) => {
            const row = document.createElement('div');
            row.className = 'list-item';
            if (this.selectedChapterIndex === idx) row.classList.add('active');
            
            row.innerHTML = `
                <span>${this.escapeHtml(ch.id)}</span>
                <span>${this.escapeHtml(ch.title || '')}</span>
                <span>${this.escapeHtml(ch.language || '')}</span>
                <span>${this.escapeHtml(ch.mode || 'single')}</span>
            `;
            row.onclick = () => this.selectChapter(idx);
            chList.appendChild(row);
        });
        
        // Hide detail if no selection
        if (this.selectedChapterIndex === -1) {
            document.getElementById('chapter-detail').classList.add('hidden');
        } else {
            this.populateChapterDetail();
        }
    },

    selectChapter(idx) {
        this.selectedChapterIndex = idx;
        
        // Update list styles
        const rows = document.getElementById('chapter-list').children;
        for (let i = 0; i < rows.length; i++) {
            if (i === idx) rows[i].classList.add('active');
            else rows[i].classList.remove('active');
        }
        
        document.getElementById('chapter-detail').classList.remove('hidden');
        this.populateChapterDetail();
    },

    populateChapterDetail() {
        if (this.selectedChapterIndex === -1) return;
        const ch = this.currentData.chapters[this.selectedChapterIndex];
        const chars = this.currentData.characters || {};
        
        document.getElementById('chap-detail-title').innerText = `Edit: ${ch.id}`;
        
        // Status Badge Logic
        const badge = document.getElementById('chap-status-badge');
        let status = 'pending';
        if (this.currentStatus && this.currentStatus.nodes.generate.chapters) {
            const chStat = this.currentStatus.nodes.generate.chapters[ch.id];
            if (chStat) status = chStat.status;
        }
        
        badge.innerText = status.toUpperCase();
        badge.className = 'status-badge';
        if (status === 'complete') badge.classList.add('complete');
        else if (status === 'failed') badge.classList.add('failed');
        else if (status === 'running') badge.classList.add('partial'); // Re-use partial style for running
        badge.style.display = 'inline-block';

        // Populate fields
        document.getElementById('chap-title').value = ch.title || "";
        
        const charSelect = document.getElementById('chap-character');
        charSelect.innerHTML = '';
        Object.keys(chars).forEach(cid => {
            const opt = document.createElement('option');
            opt.value = cid;
            opt.text = chars[cid].name || cid;
            charSelect.add(opt);
        });
        const currentChar = ch.character || ch.default_character || 'narrator';
        if (chars[currentChar]) {
            charSelect.value = currentChar;
        }

        document.getElementById('chap-mode').value = ch.mode || "single";
        
        const dir = ch.direction || {};
        document.getElementById('chap-energy').value = dir.energy || "";
        document.getElementById('chap-pace').value = dir.pace || "";
        document.getElementById('chap-emotion').value = dir.emotion || "";
        
        // Attach listeners
        const inputs = ['chap-title', 'chap-character', 'chap-mode', 'chap-energy', 'chap-pace', 'chap-emotion'];
        inputs.forEach(id => {
            const el = document.getElementById(id);
            el.onchange = () => this.updateChapterData();
        });
    },

    updateChapterData() {
        if (this.selectedChapterIndex === -1) return;
        const ch = this.currentData.chapters[this.selectedChapterIndex];
        
        ch.title = document.getElementById('chap-title').value;
        const mode = document.getElementById('chap-mode').value;
        ch.mode = mode;
        
        const charVal = document.getElementById('chap-character').value;
        if (mode === 'single') {
            ch.character = charVal;
            delete ch.default_character;
        } else {
            ch.default_character = charVal;
            delete ch.character;
        }
        
        if (!ch.direction) ch.direction = {};
        ch.direction.energy = document.getElementById('chap-energy').value;
        ch.direction.pace = document.getElementById('chap-pace').value;
        ch.direction.emotion = document.getElementById('chap-emotion').value;
        
        this.renderForm();
    },

    async generateCurrentChapter() {
        if (this.selectedChapterIndex === -1) return;
        const ch = this.currentData.chapters[this.selectedChapterIndex];
        
        // 1. Save config first
        await this.saveProject();
        
        // 2. Trigger generation
        const btn = document.getElementById('btn-generate-chap');
        btn.disabled = true;
        btn.innerText = "Starting...";
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chapters: [ch.id] })
            });
            
            if (res.ok) {
                btn.innerText = "Generating...";
                // Start polling status
                this.pollStatus(ch.id);
            } else {
                const err = await res.json();
                alert(`Generation failed to start: ${err.detail}`);
                btn.disabled = false;
                btn.innerText = "⚡ Generate Audio";
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
            btn.disabled = false;
            btn.innerText = "⚡ Generate Audio";
        }
    },

    pollStatus(chapterId) {
        if (this.pollInterval) clearInterval(this.pollInterval);
        
        const MAX_POLL_SECONDS = 600; // 10 minutes max
        const POLL_INTERVAL_MS = 2000;
        let elapsed = 0;
        
        this.pollInterval = setInterval(async () => {
            elapsed += POLL_INTERVAL_MS / 1000;
            
            if (elapsed > MAX_POLL_SECONDS) {
                clearInterval(this.pollInterval);
                this.pollInterval = null;
                
                // Reset UI
                const btn = document.getElementById('btn-generate-chap');
                if (btn) {
                    btn.disabled = false;
                    btn.innerText = "⚡ Generate Audio";
                }
                alert("Operation timed out. Check server logs.");
                return;
            }
            
            try {
                const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
                if (!res.ok) return;
                
                const status = await res.json();
                this.currentStatus = status;
                
                // Update Gen Badge
                if (this.selectedChapterIndex !== -1 && chapterId) {
                    const currentCh = this.currentData.chapters[this.selectedChapterIndex];
                    if (currentCh.id === chapterId) {
                        this.populateChapterDetail(); // Refreshes badge
                    }
                }
                
                // Update Mix Badge (global)
                if (status.nodes && status.nodes.mix) {
                    this.updateMixBadge(status.nodes.mix.status);
                }
                
                // Check Chapter Gen completion
                if (chapterId) {
                    const genNode = status.nodes && status.nodes.generate;
                    if (genNode) {
                        const nodeStatus = genNode.status;
                        
                        // Check node-level completion (covers the wrapper)
                        if (nodeStatus === 'complete' || nodeStatus === 'failed') {
                            const btn = document.getElementById('btn-generate-chap');
                            if (btn) {
                                btn.disabled = false;
                                btn.innerText = "⚡ Generate Audio";
                            }
                            if (nodeStatus === 'failed') {
                                const errMsg = genNode.error || "Unknown error";
                                alert(`Generation failed: ${errMsg}`);
                            }
                            if (!this.isMixinRunning()) {
                                clearInterval(this.pollInterval);
                                this.pollInterval = null;
                            }
                            return;
                        }
                        
                        // Check chapter-level completion (finer granularity)
                        if (genNode.chapters && genNode.chapters[chapterId]) {
                            const chStatus = genNode.chapters[chapterId].status;
                            if (chStatus === 'complete' || chStatus === 'failed') {
                                const btn = document.getElementById('btn-generate-chap');
                                if (btn) {
                                    btn.disabled = false;
                                    btn.innerText = "⚡ Generate Audio";
                                }
                                if (chStatus === 'failed') alert("Generation failed for chapter.");
                                if (!this.isMixinRunning()) {
                                    clearInterval(this.pollInterval);
                                    this.pollInterval = null;
                                }
                            }
                        }
                    }
                }
                
            } catch (e) {
                console.error("Poll error", e);
            }
        }, POLL_INTERVAL_MS);
    },
    
    isMixinRunning() {
        const btn = document.getElementById('btn-mix');
        return btn && btn.disabled;
    },

    triggerIngest() {
        document.getElementById('ingest-file-input').click();
    },

    async handleIngestFiles(input) {
        if (!input.files || input.files.length === 0) return;
        
        const formData = new FormData();
        for (let i = 0; i < input.files.length; i++) {
            formData.append('files', input.files[i]);
        }
        
        const btn = document.querySelector('button[onclick="app.triggerIngest()"]');
        const originalText = btn.innerText;
        btn.innerText = "Uploading...";
        btn.disabled = true;

        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/ingest`, {
                method: 'POST',
                body: formData
            });
            
            if (res.ok) {
                const data = await res.json();
                alert(data.message);
                await this.loadProject(this.currentProject);
                this.switchTab('chapters');
            } else {
                const err = await res.json();
                alert(`Ingest failed: ${err.detail}`);
            }
        } catch (e) {
            alert(`Network error during ingest: ${e.message}`);
        } finally {
            btn.innerText = originalText;
            btn.disabled = false;
            input.value = "";
        }
    },

    renderJson() {
        document.getElementById('json-editor').value = JSON.stringify(this.currentData, null, 2);
    },

    updateDataFromForm() {
        if (!this.currentData.generation) this.currentData.generation = {};
        this.currentData.generation.chunk_max_chars = parseInt(document.getElementById('conf-chunk-chars').value);
        this.currentData.generation.crossfade_ms = parseInt(document.getElementById('conf-crossfade').value);
        this.currentData.generation.chunk_strategy = document.getElementById('conf-strategy').value;
        this.currentData.generation.fail_threshold_percent = parseFloat(document.getElementById('conf-fail-thresh').value);

        if (!this.currentData.mix) this.currentData.mix = {};
        this.currentData.mix.target_lufs = parseFloat(document.getElementById('conf-lufs').value);
        this.currentData.mix.master_volume = parseFloat(document.getElementById('conf-vol').value);
    },

    switchTab(targetTab, skipSync = false) {
        let currentTab = 'config'; // default
        if (document.getElementById('tab-btn-chapters').classList.contains('active')) currentTab = 'chapters';
        if (document.getElementById('tab-btn-json').classList.contains('active')) currentTab = 'json';

        if (!skipSync) {
            if (currentTab === 'json' && targetTab !== 'json') {
                try {
                    const raw = document.getElementById('json-editor').value;
                    this.currentData = JSON.parse(raw);
                    this.renderForm(); 
                } catch (e) {
                    alert("Invalid JSON. Please fix errors before switching tabs.");
                    return;
                }
            }
            else if (currentTab !== 'json' && targetTab === 'json') {
                this.updateDataFromForm();
                this.renderJson();
            }
        }

        ['config', 'chapters', 'json'].forEach(t => {
            const el = document.getElementById(`tab-${t}`);
            const btn = document.getElementById(`tab-btn-${t}`);
            
            if (t === targetTab) {
                el.classList.remove('hidden');
                btn.classList.add('active');
            } else {
                el.classList.add('hidden');
                btn.classList.remove('active');
            }
        });
    },

    async saveProject() {
        const isJsonTab = document.getElementById('tab-btn-json').classList.contains('active');
        try {
            if (isJsonTab) {
                const raw = document.getElementById('json-editor').value;
                this.currentData = JSON.parse(raw);
            } else {
                this.updateDataFromForm();
                this.renderJson();
            }

            const res = await fetch(`${API_BASE}/projects/${this.currentProject}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.currentData)
            });

            if (res.ok) {
                // optional notify
            } else {
                const err = await res.json();
                alert(`Error saving: ${err.detail}`);
            }
        } catch (e) {
            alert(`Invalid JSON or save error: ${e.message}`);
        }
    },

    // ──────────────────────────────────────────────
    // Timeline / Mix View
    // ──────────────────────────────────────────────

    async showMix() {
        if (!this.currentProject) return;

        document.getElementById('projects-view').classList.add('hidden');
        document.getElementById('editor-view').classList.add('hidden');
        document.getElementById('mix-view').classList.remove('hidden');

        document.getElementById('nav-projects').classList.remove('active');
        document.getElementById('nav-editor').classList.remove('active');
        document.getElementById('nav-mix').classList.add('active');

        document.getElementById('mix-project-id').innerText = this.currentProject;

        this.initWaveSurfer();
        this.loadMixFiles();
        
        // Load mix status
        if (this.currentStatus && this.currentStatus.nodes.mix) {
            this.updateMixBadge(this.currentStatus.nodes.mix.status);
        }
    },
    
    updateMixBadge(status) {
        const badge = document.getElementById('mix-status-badge');
        const btn = document.getElementById('btn-mix');
        
        badge.innerText = status.toUpperCase();
        badge.className = 'status-badge';
        badge.style.display = 'inline-block';
        
        if (status === 'complete') {
            badge.classList.add('complete');
            btn.disabled = false;
            btn.innerText = "☊ Run Mix";
        } else if (status === 'running') {
            badge.classList.add('partial');
            btn.disabled = true;
            btn.innerText = "Mixing...";
        } else if (status === 'failed') {
            badge.classList.add('failed');
            btn.disabled = false;
            btn.innerText = "☊ Run Mix";
        } else {
            // Pending
            btn.disabled = false;
            btn.innerText = "☊ Run Mix";
        }
    },
    
    async runMix() {
        // Save config first
        await this.saveProject();
        
        const btn = document.getElementById('btn-mix');
        btn.disabled = true;
        btn.innerText = "Starting...";
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/mix`, {
                method: 'POST'
            });
            
            if (res.ok) {
                this.updateMixBadge('running');
                
                // Start polling
                if (this.pollInterval) clearInterval(this.pollInterval);
                
                const MAX_POLL_SECONDS = 600; // 10 minutes max
                const POLL_INTERVAL_MS = 2000;
                let elapsed = 0;
                
                this.pollInterval = setInterval(async () => {
                    elapsed += POLL_INTERVAL_MS / 1000;
                    
                    if (elapsed > MAX_POLL_SECONDS) {
                        clearInterval(this.pollInterval);
                        this.pollInterval = null;
                        
                        // Reset UI
                        const mixBtn = document.getElementById('btn-mix');
                        if (mixBtn) {
                            mixBtn.disabled = false;
                            mixBtn.innerText = "☊ Run Mix";
                        }
                        alert("Mix operation timed out. Check server logs.");
                        return;
                    }
                    
                    const statRes = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
                    if (statRes.ok) {
                        const status = await statRes.json();
                        this.currentStatus = status;
                        const mixStatus = status.nodes && status.nodes.mix && status.nodes.mix.status;
                        
                        if (mixStatus) {
                            this.updateMixBadge(mixStatus);
                            
                            if (mixStatus === 'complete' || mixStatus === 'failed') {
                                clearInterval(this.pollInterval);
                                this.pollInterval = null;
                                
                                // Reset button
                                const mixBtn = document.getElementById('btn-mix');
                                if (mixBtn) {
                                    mixBtn.disabled = false;
                                    mixBtn.innerText = "☊ Run Mix";
                                }
                                
                                if (mixStatus === 'complete') {
                                    this.loadMixFiles(); // Refresh file list
                                } else {
                                    const errMsg = status.nodes.mix.error || "Unknown error";
                                    alert(`Mix failed: ${errMsg}`);
                                }
                            }
                        }
                    }
                }, POLL_INTERVAL_MS);
                
            } else {
                alert("Failed to start mix.");
                btn.disabled = false;
                btn.innerText = "☊ Run Mix";
            }
        } catch (e) {
            alert(`Error: ${e.message}`);
            btn.disabled = false;
            btn.innerText = "☊ Run Mix";
        }
    },

    async runAllPipeline() {
        if (!this.currentProject) return;
        
        const btn = document.getElementById('btn-run-all');
        const originalText = btn.innerText;
        btn.disabled = true;
        
        const steps = [
            { name: 'Validate', endpoint: 'validate', method: 'POST' },
            { name: 'Generate', endpoint: 'generate', method: 'POST', body: { chapters: null, engine: null } },
            { name: 'QC Scan', endpoint: 'qc-scan', method: 'POST' },
            { name: 'Process', endpoint: 'process', method: 'POST' },
            { name: 'Compose', endpoint: 'compose', method: 'POST', body: { preset: 'contemplative', duration: 60 } },
            { name: 'Mix', endpoint: 'mix', method: 'POST' },
            { name: 'Export', endpoint: 'export', method: 'POST', body: { format: 'mp3', bitrate: 192 } },
        ];
        
        try {
            // Save config first
            await this.saveProject();
            
            for (const step of steps) {
                btn.innerText = `${step.name}...`;
                
                const options = {
                    method: step.method,
                    headers: { 'Content-Type': 'application/json' },
                };
                if (step.body) {
                    options.body = JSON.stringify(step.body);
                }
                
                const res = await fetch(
                    `${API_BASE}/projects/${this.currentProject}/${step.endpoint}`,
                    options
                );
                
                // Handle non-JSON responses defensively
                const contentType = res.headers.get('content-type') || '';
                let data;
                if (contentType.includes('application/json')) {
                    data = await res.json();
                } else {
                    const text = await res.text();
                    data = { detail: text };
                }
                
                if (!res.ok) {
                    const errMsg = data.detail || `${step.name} failed (HTTP ${res.status})`;
                    alert(`Pipeline stopped at ${step.name}:\n${errMsg}`);
                    return;
                }
                
                // For validate: check if validation passed
                if (step.endpoint === 'validate') {
                    const passed = data.ok ?? data.passed ?? true;
                    if (!passed) {
                        const failures = data.details?.failures || data.failures || [];
                        const msg = failures.length > 0 
                            ? failures.map(f => `• ${f}`).join('\n')
                            : 'Check project config.';
                        alert(`Validation failed:\n${msg}`);
                        return;
                    }
                }
                
                // For background tasks: wait for completion
                if (data.status === 'running') {
                    const completed = await this.waitForNode(step.endpoint);
                    if (!completed) {
                        alert(`${step.name} failed or timed out. Check server logs.`);
                        return;
                    }
                }
            }
            
            alert("✅ Full pipeline completed successfully!");
            await this.loadProject(this.currentProject);
            
        } catch (e) {
            alert(`❌ Pipeline error: ${e.message}`);
        } finally {
            btn.disabled = false;
            btn.innerText = originalText;
        }
    },

    async waitForNode(endpoint) {
        // Map endpoint to pipeline node name
        const nodeMap = {
            'generate': 'generate',
            'qc-scan': 'qc_scan',
            'process': 'process',
            'compose': 'compose',
            'mix': 'mix',
            'export': 'export',
        };
        const nodeName = nodeMap[endpoint] || endpoint;
        
        const MAX_WAIT_MS = 600000; // 10 minutes
        const POLL_MS = 2000;
        let elapsed = 0;
        
        while (elapsed < MAX_WAIT_MS) {
            await new Promise(r => setTimeout(r, POLL_MS));
            elapsed += POLL_MS;
            
            try {
                const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
                if (!res.ok) continue;
                
                const status = await res.json();
                this.currentStatus = status;
                
                const nodeStatus = status.nodes?.[nodeName]?.status;
                if (nodeStatus === 'complete') return true;
                if (nodeStatus === 'failed') {
                    const error = status.nodes?.[nodeName]?.error || 'Unknown error';
                    console.error(`Node ${nodeName} failed:`, error);
                    return false;
                }
            } catch (e) {
                console.error('Poll error:', e);
            }
        }
        
        return false; // Timeout
    },

    initWaveSurfer() {
        if (this.wavesurfer) return;

        this.wavesurfer = WaveSurfer.create({
            container: '#waveform',
            waveColor: '#10b981',
            progressColor: '#059669',
            cursorColor: '#fff',
            barWidth: 2,
            barRadius: 3,
            cursorWidth: 1,
            height: 100,
            barGap: 2,
            normalize: true,
        });

        this.wavesurfer.on('audioprocess', () => this.updateTime());
        this.wavesurfer.on('seek', () => this.updateTime());
        this.wavesurfer.on('ready', () => this.updateTime());

        document.getElementById('play-btn').onclick = () => this.wavesurfer.playPause();
        
        document.getElementById('zoom-slider').oninput = (e) => {
            this.wavesurfer.zoom(Number(e.target.value));
        };
    },

    updateTime() {
        const cur = this.formatTime(this.wavesurfer.getCurrentTime());
        const dur = this.formatTime(this.wavesurfer.getDuration());
        document.getElementById('time-display').innerText = `${cur} / ${dur}`;
        
        const btn = document.getElementById('play-btn');
        btn.innerText = this.wavesurfer.isPlaying() ? '⏸ Pause' : '▶ Play';
    },

    formatTime(seconds) {
        if (!seconds) return "00:00";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    },

    loadMixFiles() {
        const list = document.getElementById('mix-file-list');
        list.innerHTML = '';

        if (!this.currentData || !this.currentData.chapters) return;

        this.currentData.chapters.forEach(ch => {
            const el = document.createElement('div');
            el.className = 'file-list-item';
            el.innerText = `${ch.id} - ${ch.title}`;
            
            el.onclick = () => {
                document.querySelectorAll('.file-list-item').forEach(i => i.classList.remove('active'));
                el.classList.add('active');
                
                this.loadAudio(ch);
            };
            
            list.appendChild(el);
        });
    },

    async loadAudio(chapterInfo) {
        const paths = [
            { url: `/projects/${this.currentProject}/06_MIX/renders/${chapterInfo.id}.wav`, type: "Mixed (Final)" },
            { url: `/projects/${this.currentProject}/03_GENERATED/processed/${chapterInfo.id}.wav`, type: "Processed (Normalized)" },
            { url: `/projects/${this.currentProject}/03_GENERATED/raw/${chapterInfo.id}.wav`, type: "Raw (Unprocessed)" },
        ];

        // Create track info securely
        const trackInfoEl = document.getElementById('track-info');
        trackInfoEl.innerHTML = ''; // Clear existing content
        
        const titleEl = document.createElement('h3');
        titleEl.textContent = `${chapterInfo.title} (${chapterInfo.id})`;
        
        const statusEl = document.createElement('p');
        statusEl.textContent = 'Checking audio availability...';
        
        trackInfoEl.appendChild(titleEl);
        trackInfoEl.appendChild(statusEl);

        let targetUrl = null;
        let type = "";

        for (const path of paths) {
            try {
                const res = await fetch(path.url, { method: 'HEAD' });
                if (res.ok) {
                    targetUrl = path.url;
                    type = path.type;
                    break;
                }
                // 404 is expected — just continue to next path
            } catch (e) {
                // Network error — continue to next path
            }
        }

        if (!targetUrl) {
            // Create error message securely
            const trackInfoEl = document.getElementById('track-info');
            trackInfoEl.innerHTML = ''; // Clear existing content
            
            const errorTitleEl = document.createElement('h3');
            errorTitleEl.style.cssText = 'color:var(--danger)';
            errorTitleEl.textContent = 'Audio Not Found';
            
            const errorMsgEl = document.createElement('p');
            errorMsgEl.innerHTML = `No audio found for <strong>${this.escapeHtml(chapterInfo.id)}</strong>.`;
            
            const checkedDiv = document.createElement('div');
            checkedDiv.style.cssText = 'background:var(--bg-card); padding:1rem; border-radius:4px; margin-top:1rem;';
            
            const checkedTitleEl = document.createElement('p');
            checkedTitleEl.style.cssText = 'margin-top:0';
            checkedTitleEl.textContent = 'Checked:';
            
            const checkedListEl = document.createElement('ul');
            checkedListEl.style.cssText = 'margin-bottom:0';
            
            paths.forEach(p => {
                const liEl = document.createElement('li');
                const codeEl = document.createElement('code');
                codeEl.textContent = p.url;
                liEl.appendChild(codeEl);
                checkedListEl.appendChild(liEl);
            });
            
            const instructionEl = document.createElement('p');
            instructionEl.style.cssText = 'margin-top:1rem; color:var(--text-secondary);';
            instructionEl.innerHTML = 'Generate audio in the <strong>Editor</strong>, then return here.';
            
            checkedDiv.appendChild(checkedTitleEl);
            checkedDiv.appendChild(checkedListEl);
            
            trackInfoEl.appendChild(errorTitleEl);
            trackInfoEl.appendChild(errorMsgEl);
            trackInfoEl.appendChild(checkedDiv);
            trackInfoEl.appendChild(instructionEl);
            
            return;
        }

        // Load into wavesurfer - create loading message securely
        trackInfoEl.innerHTML = ''; // Clear existing content (reusing variable)
        
        const loadingTitleEl = document.createElement('h3');
        loadingTitleEl.textContent = `${chapterInfo.title} (${chapterInfo.id})`;
        
        const loadingStatusEl = document.createElement('p');
        loadingStatusEl.textContent = `Loading ${type}...`;
        
        trackInfoEl.appendChild(loadingTitleEl);
        trackInfoEl.appendChild(loadingStatusEl);

        try {
            await this.wavesurfer.load(targetUrl);
            
            let badgeClass = type.startsWith('Mixed') ? 'complete' : 'partial';
            
            // Create success message securely
            trackInfoEl.innerHTML = ''; // Clear existing content
            
            const successTitleEl = document.createElement('h3');
            successTitleEl.textContent = `${chapterInfo.title} (${chapterInfo.id})`;
            
            const badgeDivEl = document.createElement('div');
            badgeDivEl.style.cssText = 'margin-top:0.5rem; margin-bottom:1rem;';
            
            const badgeSpanEl = document.createElement('span');
            badgeSpanEl.className = `status-badge ${badgeClass}`;
            badgeSpanEl.textContent = type;
            
            const durationEl = document.createElement('p');
            durationEl.textContent = `Duration: ${this.formatTime(this.wavesurfer.getDuration())}`;
            
            badgeDivEl.appendChild(badgeSpanEl);
            
            trackInfoEl.appendChild(successTitleEl);
            trackInfoEl.appendChild(badgeDivEl);
            trackInfoEl.appendChild(durationEl);
        } catch (e) {
            // Create error message securely
            trackInfoEl.innerHTML = ''; // Clear existing content
            
            const errorTitleEl = document.createElement('h3');
            errorTitleEl.style.cssText = 'color:var(--danger)';
            errorTitleEl.textContent = 'Load Error';
            
            const errorMsgEl = document.createElement('p');
            errorMsgEl.textContent = 'Found file but failed to decode: ';
            
            const codeEl = document.createElement('code');
            codeEl.textContent = e.message || 'Unknown error';
            errorMsgEl.appendChild(codeEl);
            
            trackInfoEl.appendChild(errorTitleEl);
            trackInfoEl.appendChild(errorMsgEl);
        }
    },

    // ──────────────────────────────────────────────
    // Nav / Helpers
    // ──────────────────────────────────────────────

    showProjects() {
        document.getElementById('projects-view').classList.remove('hidden');
        document.getElementById('editor-view').classList.add('hidden');
        document.getElementById('mix-view').classList.add('hidden');
        
        document.getElementById('nav-projects').classList.add('active');
        
        const edit = document.getElementById('nav-editor');
        edit.classList.remove('active');
        edit.classList.add('disabled');
        
        const mix = document.getElementById('nav-mix');
        mix.classList.remove('active');
        mix.classList.add('disabled');
        
        if (this.wavesurfer) {
            this.wavesurfer.pause();
        }
        if (this.pollInterval) clearInterval(this.pollInterval);

        this.currentProject = null;
        this.fetchProjects();
    },

    showEditor() {
        if (!this.currentProject) return;
        document.getElementById('projects-view').classList.add('hidden');
        document.getElementById('editor-view').classList.remove('hidden');
        document.getElementById('mix-view').classList.add('hidden');
        
        document.getElementById('nav-projects').classList.remove('active');
        document.getElementById('nav-editor').classList.add('active');
        document.getElementById('nav-mix').classList.remove('active');
        
        if (this.wavesurfer) {
            this.wavesurfer.pause();
        }
    },

    escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return unsafe;
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
};

document.addEventListener('DOMContentLoaded', () => app.init());
