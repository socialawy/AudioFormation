
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

            card.innerHTML = `
                <h3>${this.escapeHtml(p.id)}</h3>
                <div style="font-size: 0.85rem; color: #888; margin-bottom: 0.5rem;">
                    Created: ${this.escapeHtml(date)}
                </div>
                <div class="meta">
                    <span>${this.escapeHtml(p.chapters)} Chs • ${this.escapeHtml(p.languages.join(', '))}</span>
                    <span class="status-badge ${statusClass}">${this.escapeHtml(p.pipeline_node)}</span>
                </div>
            `;
            
            card.onclick = () => this.loadProject(p.id);
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
        
        this.pollInterval = setInterval(async () => {
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
                if (status.nodes.mix) {
                    this.updateMixBadge(status.nodes.mix.status);
                }
                
                // Check Chapter Gen completion
                if (chapterId) {
                    const genNode = status.nodes.generate;
                    if (genNode && genNode.chapters && genNode.chapters[chapterId]) {
                        const chStatus = genNode.chapters[chapterId].status;
                        if (chStatus === 'complete' || chStatus === 'failed') {
                            // If user is polling specifically for chapter generation
                            document.getElementById('btn-generate-chap').disabled = false;
                            document.getElementById('btn-generate-chap').innerText = "⚡ Generate Audio";
                            if (chStatus === 'failed') alert("Generation failed. Check logs.");
                            
                            // Only clear if not mixing
                            if (!this.isMixinRunning()) clearInterval(this.pollInterval);
                        }
                    }
                }
                
            } catch (e) {
                console.error("Poll error", e);
            }
        }, 2000);
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
                this.pollInterval = setInterval(async () => {
                    const statRes = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
                    if (statRes.ok) {
                        const status = await statRes.json();
                        this.currentStatus = status;
                        const mixStatus = status.nodes.mix.status;
                        
                        this.updateMixBadge(mixStatus);
                        
                        if (mixStatus === 'complete' || mixStatus === 'failed') {
                            clearInterval(this.pollInterval);
                            this.pollInterval = null;
                            if (mixStatus === 'complete') {
                                this.loadMixFiles(); // Refresh file list
                            } else {
                                alert("Mix failed.");
                            }
                        }
                    }
                }, 2000);
                
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
        // Paths: mix checks render first, then processed (fallback), then raw
        // But mix view should prioritize MIXED content if available (in 06_MIX/renders)
        // Actually, the original logic prioritized processed.
        // Let's improve priority: Mix Render -> Processed -> Raw
        
        const mixRenderUrl = `/projects/${this.currentProject}/06_MIX/renders/${chapterInfo.id}.wav`;
        const processedUrl = `/projects/${this.currentProject}/03_GENERATED/processed/${chapterInfo.id}.wav`;
        const rawUrl = `/projects/${this.currentProject}/03_GENERATED/raw/${chapterInfo.id}.wav`;

        let targetUrl = null;
        let type = "";

        document.getElementById('track-info').innerHTML = `
            <h3>${chapterInfo.title} (${chapterInfo.id})</h3>
            <p>Checking audio availability...</p>
        `;

        try {
            // Check Mix Render
            const mRes = await fetch(mixRenderUrl, { method: 'HEAD' });
            if (mRes.ok) {
                targetUrl = mixRenderUrl;
                type = "Mixed (Final)";
            } else {
                // Check processed
                const pRes = await fetch(processedUrl, { method: 'HEAD' });
                if (pRes.ok) {
                    targetUrl = processedUrl;
                    type = "Processed (Normalized)";
                } else {
                    // Check raw fallback
                    const rRes = await fetch(rawUrl, { method: 'HEAD' });
                    if (rRes.ok) {
                        targetUrl = rawUrl;
                        type = "Raw (Unprocessed)";
                    }
                }
            }
        } catch (e) {
            console.error("Error checking files:", e);
        }

        if (!targetUrl) {
             document.getElementById('track-info').innerHTML = `
                <h3 style="color:var(--danger)">Audio Not Found</h3>
                <p>Could not find audio for <strong>${chapterInfo.id}</strong>.</p>
                <div style="background:var(--bg-card); padding:1rem; border-radius:4px; margin-top:1rem;">
                    <p style="margin-top:0">Checked locations:</p>
                    <ul style="margin-bottom:0">
                        <li><code>renders/${chapterInfo.id}.wav</code></li>
                        <li><code>processed/${chapterInfo.id}.wav</code></li>
                        <li><code>raw/${chapterInfo.id}.wav</code></li>
                    </ul>
                </div>
                <p style="margin-top:1rem; color:var(--text-secondary);">
                    Use the <strong>Editor</strong> to generate audio, then <strong>Mix</strong>.
                </p>
            `;
            return;
        }

        document.getElementById('track-info').innerHTML = `
            <h3>${this.escapeHtml(chapterInfo.title)} (${this.escapeHtml(chapterInfo.id)})</h3>
            <p>Loading ${this.escapeHtml(type)}...</p>
        `;

        try {
            await this.wavesurfer.load(targetUrl);
            
            let badgeClass = 'partial';
            if (type.startsWith('Mixed')) badgeClass = 'complete';
            
            document.getElementById('track-info').innerHTML = `
                <h3>${this.escapeHtml(chapterInfo.title)} (${this.escapeHtml(chapterInfo.id)})</h3>
                <div style="margin-top:0.5rem; margin-bottom:1rem;">
                    <span class="status-badge ${badgeClass}">${this.escapeHtml(type)}</span>
                </div>
                <p>Duration: ${this.escapeHtml(this.formatTime(this.wavesurfer.getDuration()))}</p>
                <p><small style="opacity:0.6">${this.escapeHtml(targetUrl)}</small></p>
            `;
        } catch (e) {
             document.getElementById('track-info').innerHTML = `
                <h3 style="color:var(--danger)">Load Error</h3>
                <p>Found file but failed to decode.</p>
                <p><code>${this.escapeHtml(e.message)}</code></p>
            `;
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
