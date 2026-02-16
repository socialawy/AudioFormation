
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
    availableEngines: [],

    init() {
        this.fetchProjects();
        this.fetchEngines();
    },

    // ──────────────────────────────────────────────
    // Global Data Fetching
    // ──────────────────────────────────────────────

    async fetchEngines() {
        try {
            const res = await fetch(`${API_BASE}/engines`);
            if (res.ok) {
                this.availableEngines = await res.json();
            }
        } catch (e) {
            console.error("Failed to fetch engines", e);
        }
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

            // Create card content
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
            
            // Populate views
            this.renderOverview();
            this.renderCast();
            this.renderEngineSettings();
            this.renderForm(); // Chapters
            this.renderJson();
            
            // Initial view
            this.showEditor();
            this.switchTab('overview', true);
            
            // Enable nav
            ['nav-editor', 'nav-mix', 'nav-export', 'nav-qc'].forEach(id => {
                document.getElementById(id).classList.remove('disabled');
            });
            
            // Navbar click handlers
            document.getElementById('nav-mix').onclick = () => this.showMix();
            document.getElementById('nav-export').onclick = () => this.showExport();
            document.getElementById('nav-qc').onclick = () => this.showQC();

            // Load Hardware Info
            this.fetchHardwareInfo(id);

        } catch (e) {
            alert(e.message);
        }
    },

    async fetchHardwareInfo(id) {
        try {
            const res = await fetch(`${API_BASE}/projects/${id}/hardware`);
            if (res.ok) {
                const hw = await res.json();
                const container = document.getElementById('hardware-info');
                container.innerHTML = `
                    <p>GPU: ${hw.gpu_name || 'None'} (${hw.vram_total_gb || 0} GB)</p>
                    <p>Strategy: ${hw.recommended_vram_strategy}</p>
                    <p>ffmpeg: ${hw.ffmpeg_available ? '✅' : '❌'}</p>
                `;
            }
        } catch(e) { console.error(e); }
    },

    renderOverview() {
        const d = this.currentData;
        const s = this.currentStatus;
        document.getElementById('editor-project-id').innerText = d.id;
        document.getElementById('overview-languages').innerText = d.languages.join(', ');
        document.getElementById('overview-created').innerText = new Date(d.created).toLocaleDateString();

        // Render Pipeline Stepper
        const container = document.getElementById('pipeline-stepper');
        container.innerHTML = '';
        
        const nodes = ['bootstrap', 'ingest', 'validate', 'generate', 'qc_scan', 'process', 'compose', 'mix', 'qc_final', 'export'];
        nodes.forEach(n => {
            const status = s?.nodes?.[n]?.status || 'pending';
            const nodeEl = document.createElement('div');
            nodeEl.className = `pipeline-node ${status}`;
            
            let icon = '○';
            if (status === 'complete') icon = '✅';
            if (status === 'running') icon = '⏳';
            if (status === 'failed') icon = '❌';
            
            nodeEl.innerHTML = `<span style="font-size:1.2rem">${icon}</span> <span>${n}</span>`;
            container.appendChild(nodeEl);
        });
    },

    renderCast() {
        const list = document.getElementById('cast-list');
        list.innerHTML = '';
        const chars = this.currentData.characters || {};

        Object.keys(chars).forEach(cid => {
            const char = chars[cid];
            const el = document.createElement('div');
            el.className = 'cast-item';
            
            el.innerHTML = `
                <h4>${char.name} (${cid})</h4>
                <div class="cast-prop"><label>Engine:</label> <span>${char.engine}</span></div>
                <div class="cast-prop"><label>Voice:</label> <span>${char.voice || char.reference_audio || 'None'}</span></div>
                <div class="cast-prop"><label>Dialect:</label> <span>${char.dialect || 'msa'}</span></div>
            `;
            list.appendChild(el);
        });
    },
    
    async addCharacter() {
        const id = prompt("Character ID (e.g. hero):");
        if (!id) return;
        const name = prompt("Display Name:");
        
        if (!this.currentData.characters) this.currentData.characters = {};
        this.currentData.characters[id] = {
            name: name,
            engine: "edge", // default
            voice: "ar-SA-HamedNeural",
            dialect: "msa"
        };
        await this.saveProject();
        this.renderCast();
    },

    renderEngineSettings() {
        const gen = this.currentData.generation || {};
        document.getElementById('conf-chunk-chars').value = gen.chunk_max_chars || 200;
        document.getElementById('conf-crossfade').value = gen.crossfade_ms || 120;
        document.getElementById('conf-strategy').value = gen.chunk_strategy || 'breath_group';
        document.getElementById('conf-fail-thresh').value = gen.fail_threshold_percent || 5;
        document.getElementById('conf-silence').value = gen.leading_silence_ms || 100;
        document.getElementById('conf-fallback-scope').value = gen.fallback_scope || 'chapter';

        const mix = this.currentData.mix || {};
        document.getElementById('conf-lufs').value = mix.target_lufs || -16.0;
        document.getElementById('conf-vol').value = mix.master_volume || 0.9;
    },

    renderForm() {
        // Chapters List
        const d = this.currentData;
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
        
        if (this.selectedChapterIndex === -1) {
            document.getElementById('chapter-detail').classList.add('hidden');
        } else {
            this.populateChapterDetail();
        }
    },

    selectChapter(idx) {
        this.selectedChapterIndex = idx;
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
        
        const badge = document.getElementById('chap-status-badge');
        let status = 'pending';
        if (this.currentStatus && this.currentStatus.nodes.generate.chapters) {
            const chStat = this.currentStatus.nodes.generate.chapters[ch.id];
            if (chStat) status = chStat.status;
        }
        badge.innerText = status.toUpperCase();
        badge.className = `status-badge ${status === 'complete' ? 'complete' : status === 'running' ? 'partial' : status === 'failed' ? 'failed' : ''}`;
        badge.style.display = 'inline-block';

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
        if (chars[currentChar]) charSelect.value = currentChar;

        document.getElementById('chap-mode').value = ch.mode || "single";
        
        const dir = ch.direction || {};
        // Using new dropdowns
        document.getElementById('chap-energy').value = dir.energy || "";
        document.getElementById('chap-pace').value = dir.pace || "";
        document.getElementById('chap-emotion').value = dir.emotion || "";
        
        // Listeners
        const inputs = ['chap-title', 'chap-character', 'chap-mode', 'chap-energy', 'chap-pace', 'chap-emotion'];
        inputs.forEach(id => {
            document.getElementById(id).onchange = () => this.updateChapterData();
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
    },

    updateDataFromForm() {
        if (!this.currentData.generation) this.currentData.generation = {};
        const gen = this.currentData.generation;
        gen.chunk_max_chars = parseInt(document.getElementById('conf-chunk-chars').value);
        gen.crossfade_ms = parseInt(document.getElementById('conf-crossfade').value);
        gen.chunk_strategy = document.getElementById('conf-strategy').value;
        gen.fail_threshold_percent = parseFloat(document.getElementById('conf-fail-thresh').value);
        gen.leading_silence_ms = parseInt(document.getElementById('conf-silence').value);
        gen.fallback_scope = document.getElementById('conf-fallback-scope').value;

        if (!this.currentData.mix) this.currentData.mix = {};
        this.currentData.mix.target_lufs = parseFloat(document.getElementById('conf-lufs').value);
        this.currentData.mix.master_volume = parseFloat(document.getElementById('conf-vol').value);
    },

    renderJson() {
        document.getElementById('json-editor').value = JSON.stringify(this.currentData, null, 2);
    },

    switchTab(targetTab, skipSync = false) {
        if (!skipSync) this.updateDataFromForm(); // Always sync from form before switching

        ['overview', 'cast', 'chapters', 'engine', 'json'].forEach(t => {
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
        
        // If switching to JSON tab, refresh it
        if (targetTab === 'json') this.renderJson();
    },

    async saveProject() {
        try {
            this.updateDataFromForm();
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.currentData)
            });
            if (!res.ok) {
                const err = await res.json();
                alert(`Error saving: ${err.detail}`);
            }
        } catch (e) {
            alert(`Save error: ${e.message}`);
        }
    },

    // ──────────────────────────────────────────────
    // Export View
    // ──────────────────────────────────────────────

    async showExport() {
        if (!this.currentProject) return;
        this.hideAllViews();
        document.getElementById('export-view').classList.remove('hidden');
        document.getElementById('nav-export').classList.add('active');
        
        this.fetchFiles();
    },

    async fetchFiles() {
        const list = document.getElementById('export-file-list');
        list.innerHTML = '<div class="card loading">Loading files...</div>';
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/files`);
            if (res.ok) {
                const files = await res.json();
                this.renderFileList(files);
            } else {
                list.innerHTML = '<div class="card" style="color:red">Failed to load files</div>';
            }
        } catch(e) {
            console.error(e);
        }
    },

    renderFileList(files) {
        const list = document.getElementById('export-file-list');
        list.innerHTML = '';
        
        if (files.length === 0) {
            list.innerHTML = '<div class="card">No files found. Run export.</div>';
            return;
        }
        
        files.forEach(f => {
            const el = document.createElement('div');
            el.className = 'file-download';
            
            const sizeMB = (f.size / (1024*1024)).toFixed(2);
            const date = new Date(f.modified * 1000).toLocaleString();
            
            el.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:0.2rem;">
                    <a href="/projects/${this.currentProject}/${f.path}" target="_blank" download>${f.name}</a>
                    <span class="file-size">${f.category} • ${date}</span>
                </div>
                <span class="file-size">${sizeMB} MB</span>
            `;
            list.appendChild(el);
        });
    },

    async triggerExport() {
        const fmt = document.getElementById('export-format').value;
        const bitrate = parseInt(document.getElementById('export-bitrate').value);
        
        const statusPanel = document.getElementById('export-status-panel');
        const statusText = document.getElementById('export-status-text');
        const statusMsg = document.getElementById('export-status-msg');
        
        statusPanel.classList.remove('hidden');
        statusText.innerText = 'Running...';
        statusMsg.innerText = `Exporting as ${fmt} at ${bitrate}kbps...`;
        
        try {
            await this.saveProject(); // Ensure config is saved
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/export`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({format: fmt, bitrate: bitrate})
            });
            
            if (res.ok) {
                this.pollExportStatus();
            } else {
                statusText.innerText = 'Failed';
                statusMsg.innerText = 'Server returned error.';
            }
        } catch(e) {
            statusText.innerText = 'Error';
            statusMsg.innerText = e.message;
        }
    },

    pollExportStatus() {
        if (this.pollInterval) clearInterval(this.pollInterval);
        
        this.pollInterval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
                if (res.ok) {
                    const status = await res.json();
                    const exportNode = status.nodes.export;
                    
                    if (exportNode.status === 'complete') {
                        clearInterval(this.pollInterval);
                        document.getElementById('export-status-text').innerText = 'Complete ✅';
                        document.getElementById('export-status-msg').innerText = 'Export finished successfully.';
                        this.fetchFiles(); // Refresh list
                    } else if (exportNode.status === 'failed') {
                        clearInterval(this.pollInterval);
                        document.getElementById('export-status-text').innerText = 'Failed ❌';
                        document.getElementById('export-status-msg').innerText = exportNode.error || 'Unknown error';
                    }
                }
            } catch(e) {
                console.error(e);
            }
        }, 2000);
    },

    // ──────────────────────────────────────────────
    // QC View
    // ──────────────────────────────────────────────

    async showQC() {
        if (!this.currentProject) return;
        this.hideAllViews();
        document.getElementById('qc-view').classList.remove('hidden');
        document.getElementById('nav-qc').classList.add('active');
        
        const container = document.getElementById('qc-reports-container');
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/qc`);
            if (res.ok) {
                const reports = await res.json();
                this.renderQCReports(reports);
            } else {
                container.innerHTML = '<div class="card">No QC reports found. Run QC Scan or QC Final.</div>';
            }
        } catch(e) {
            container.innerHTML = `<div class="card" style="color:red">Error: ${e.message}</div>`;
        }
    },

    renderQCReports(reports) {
        const container = document.getElementById('qc-reports-container');
        container.innerHTML = '';
        
        if (reports.final_qc) {
            const final = reports.final_qc;
            const el = document.createElement('div');
            el.className = 'card';
            el.innerHTML = `
                <h3>QC Final Report</h3>
                <div style="display:flex; gap:2rem; margin-bottom:1rem;">
                    <div>Passed: ${final.passed ? '✅ YES' : '❌ NO'}</div>
                    <div>Files: ${final.total_files}</div>
                    <div>Failures: ${final.failed_files}</div>
                </div>
                ${final.results.map(r => `
                    <div style="margin-top:0.5rem; padding:0.5rem; background:#333; border-radius:4px; border-left:4px solid ${r.status==='pass'?'#10b981':'#ef4444'}">
                        <strong>${r.filename}</strong>: LUFS ${r.lufs.toFixed(1)} | TP ${r.true_peak.toFixed(1)}
                        ${r.messages.length > 0 ? `<div style="color:#ef4444; font-size:0.9rem;">${r.messages.join('<br>')}</div>` : ''}
                    </div>
                `).join('')}
            `;
            container.appendChild(el);
        }
        
        if (reports.chunk_qc && reports.chunk_qc.length > 0) {
            const latest = reports.chunk_qc[reports.chunk_qc.length-1];
            const el = document.createElement('div');
            el.className = 'card';
            el.innerHTML = `
                <h3>Latest Chunk Scan</h3>
                <div style="display:flex; gap:2rem;">
                    <div>Fail Rate: ${latest.fail_rate_percent}%</div>
                    <div>Chunks: ${latest.total_chunks}</div>
                    <div>Failures: ${latest.failures}</div>
                </div>
            `;
            container.appendChild(el);
        }
    },

    // ──────────────────────────────────────────────
    // Core Navigation & Helpers
    // ──────────────────────────────────────────────

    hideAllViews() {
        ['projects-view', 'editor-view', 'mix-view', 'export-view', 'qc-view'].forEach(id => {
            document.getElementById(id).classList.add('hidden');
        });
        document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
    },

    showProjects() {
        this.hideAllViews();
        document.getElementById('projects-view').classList.remove('hidden');
        document.getElementById('nav-projects').classList.add('active');
        this.currentProject = null;
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.fetchProjects();
    },

    showEditor() {
        if (!this.currentProject) return;
        this.hideAllViews();
        document.getElementById('editor-view').classList.remove('hidden');
        document.getElementById('nav-editor').classList.add('active');
    },

    // Mix View Logic (retained from prev version)
    async showMix() {
        if (!this.currentProject) return;
        this.hideAllViews();
        document.getElementById('mix-view').classList.remove('hidden');
        document.getElementById('nav-mix').classList.add('active');
        document.getElementById('mix-project-id').innerText = this.currentProject;
        
        this.initWaveSurfer();
        this.loadMixFiles();
        if (this.currentStatus?.nodes?.mix) this.updateMixBadge(this.currentStatus.nodes.mix.status);
    },

    updateMixBadge(status) {
        const badge = document.getElementById('mix-status-badge');
        const btn = document.getElementById('btn-mix');
        badge.innerText = status.toUpperCase();
        badge.className = `status-badge ${status === 'complete' ? 'complete' : status === 'running' ? 'partial' : status === 'failed' ? 'failed' : ''}`;
        badge.style.display = 'inline-block';
        
        if (status === 'running') {
            btn.disabled = true;
            btn.innerText = "Mixing...";
        } else {
            btn.disabled = false;
            btn.innerText = "☊ Run Mix";
        }
    },

    async runMix() {
        await this.saveProject();
        const btn = document.getElementById('btn-mix');
        btn.disabled = true;
        btn.innerText = "Starting...";
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/mix`, { method: 'POST' });
            if (res.ok) {
                this.updateMixBadge('running');
                this.pollMixStatus();
            } else {
                alert("Failed to start mix.");
                btn.disabled = false;
                btn.innerText = "☊ Run Mix";
            }
        } catch (e) { alert(`Error: ${e.message}`); btn.disabled = false; }
    },

    pollMixStatus() {
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.pollInterval = setInterval(async () => {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
            if (res.ok) {
                const status = await res.json();
                this.currentStatus = status;
                const mixStatus = status.nodes?.mix?.status;
                if (mixStatus) {
                    this.updateMixBadge(mixStatus);
                    if (mixStatus === 'complete' || mixStatus === 'failed') {
                        clearInterval(this.pollInterval);
                        if (mixStatus === 'complete') this.loadMixFiles();
                    }
                }
            }
        }, 2000);
    },

    loadMixFiles() {
        const list = document.getElementById('mix-file-list');
        list.innerHTML = '';
        if (this.currentData?.chapters) {
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
        }
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
        document.getElementById('zoom-slider').oninput = (e) => this.wavesurfer.zoom(Number(e.target.value));
    },

    updateTime() {
        const cur = this.formatTime(this.wavesurfer.getCurrentTime());
        const dur = this.formatTime(this.wavesurfer.getDuration());
        document.getElementById('time-display').innerText = `${cur} / ${dur}`;
        document.getElementById('play-btn').innerText = this.wavesurfer.isPlaying() ? '⏸ Pause' : '▶ Play';
    },

    async loadAudio(chapterInfo) {
        const paths = [
            { url: `/projects/${this.currentProject}/06_MIX/renders/${chapterInfo.id}.wav`, type: "Mixed" },
            { url: `/projects/${this.currentProject}/03_GENERATED/processed/${chapterInfo.id}.wav`, type: "Processed" },
            { url: `/projects/${this.currentProject}/03_GENERATED/raw/${chapterInfo.id}.wav`, type: "Raw" },
        ];
        
        const trackInfoEl = document.getElementById('track-info');
        trackInfoEl.innerHTML = `<h3>${chapterInfo.id}</h3><p>Loading...</p>`;

        let loaded = false;
        for (const p of paths) {
            try {
                const res = await fetch(p.url, { method: 'HEAD' });
                if (res.ok) {
                    await this.wavesurfer.load(p.url);
                    trackInfoEl.innerHTML = `
                        <h3>${chapterInfo.title} (${chapterInfo.id})</h3>
                        <div class="status-badge complete" style="display:inline-block; margin:0.5rem 0;">${p.type}</div>
                        <p>Duration: ${this.formatTime(this.wavesurfer.getDuration())}</p>
                    `;
                    loaded = true;
                    break;
                }
            } catch(e) {}
        }
        
        if (!loaded) trackInfoEl.innerHTML = `<h3 style="color:red">Audio Not Found</h3><p>Run generation first.</p>`;
    },

    // Helpers
    formatTime(seconds) {
        if (!seconds) return "00:00";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    },

    escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return unsafe;
        return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    },

    triggerIngest() {
        document.getElementById('ingest-file-input').click();
    },

    async handleIngestFiles(input) {
        if (!input.files.length) return;
        const formData = new FormData();
        for (let i = 0; i < input.files.length; i++) formData.append('files', input.files[i]);
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/ingest`, { method: 'POST', body: formData });
            if (res.ok) {
                alert("Files ingested.");
                await this.loadProject(this.currentProject);
            } else alert("Ingest failed.");
        } catch(e) { alert(e.message); }
    },

    async runAllPipeline() {
        if (!confirm("Run full pipeline? This may take time.")) return;
        
        const steps = ['validate', 'generate', 'qc-scan', 'process', 'compose', 'mix', 'export'];
        const btn = document.getElementById('btn-run-all');
        btn.disabled = true;
        
        for (const step of steps) {
            btn.innerText = `Running ${step}...`;
            try {
                let body = {};
                if (step === 'generate') body = { chapters: null };
                if (step === 'compose') body = { preset: 'contemplative', duration: 60 };
                if (step === 'export') body = { format: 'mp3', bitrate: 192 };
                
                const res = await fetch(`${API_BASE}/projects/${this.currentProject}/${step}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body)
                });
                
                if (!res.ok) throw new Error(`${step} failed`);
                
                // Wait for completion
                if (step !== 'validate') await this.waitForNode(step);
                
            } catch(e) {
                alert(`Pipeline stopped at ${step}: ${e.message}`);
                btn.disabled = false;
                btn.innerText = "🚀 Run All Pipeline";
                return;
            }
        }
        
        btn.disabled = false;
        btn.innerText = "🚀 Run All Pipeline";
        alert("Pipeline complete!");
        this.loadProject(this.currentProject);
    },

    async waitForNode(endpoint) {
        const nodeMap = { 'generate': 'generate', 'qc-scan': 'qc_scan', 'process': 'process', 'compose': 'compose', 'mix': 'mix', 'export': 'export' };
        const nodeName = nodeMap[endpoint] || endpoint;
        
        while (true) {
            await new Promise(r => setTimeout(r, 2000));
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
            if (res.ok) {
                const s = await res.json();
                const status = s.nodes?.[nodeName]?.status;
                if (status === 'complete') return true;
                if (status === 'failed') throw new Error(`Node ${nodeName} failed`);
            }
        }
    },
    
    async generateCurrentChapter() {
        if (this.selectedChapterIndex === -1) return;
        const ch = this.currentData.chapters[this.selectedChapterIndex];
        await this.saveProject();
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
                this.pollStatus(ch.id);
            } else {
                alert("Failed to start generation");
                btn.disabled = false;
                btn.innerText = "⚡ Generate Audio";
            }
        } catch(e) { alert(e.message); btn.disabled = false; btn.innerText = "⚡ Generate Audio"; }
    },

    pollStatus(chapterId) {
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.pollInterval = setInterval(async () => {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
            if (res.ok) {
                this.currentStatus = await res.json();
                // Update specific chapter status
                if (this.currentData.chapters[this.selectedChapterIndex].id === chapterId) {
                    this.populateChapterDetail(); // Updates badge
                }
                const chStatus = this.currentStatus.nodes.generate.chapters?.[chapterId]?.status;
                if (chStatus === 'complete' || chStatus === 'failed') {
                    clearInterval(this.pollInterval);
                    const btn = document.getElementById('btn-generate-chap');
                    if (btn) { btn.disabled = false; btn.innerText = "⚡ Generate Audio"; }
                }
            }
        }, 2000);
    }
};

document.addEventListener('DOMContentLoaded', () => app.init());
