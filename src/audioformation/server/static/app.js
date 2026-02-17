
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
    voiceCache: {}, // Cache voices by engine+lang
    activeUploadCid: null, // Track character ID for ref upload

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

    async fetchVoices(engine, lang) {
        const key = `${engine}:${lang}`;
        if (this.voiceCache[key]) return this.voiceCache[key];

        try {
            const res = await fetch(`${API_BASE}/engines/${engine}/voices?lang=${lang || ''}`);
            if (res.ok) {
                const voices = await res.json();
                this.voiceCache[key] = voices;
                return voices;
            }
        } catch (e) {
            console.error(`Failed to fetch voices for ${engine}`, e);
        }
        return [];
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
            this.fetchAssets(); // Populate assets tab
            
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

    async renderCast() {
        const list = document.getElementById('cast-list');
        list.innerHTML = '';
        const chars = this.currentData.characters || {};
        const projectLangs = this.currentData.languages || ['ar'];
        const primaryLang = projectLangs[0]; // Default for fetching voices

        for (const cid of Object.keys(chars)) {
            const char = chars[cid];
            const el = document.createElement('div');
            el.className = 'cast-item';
            
            // Build Engine Options
            let engineOpts = '';
            this.availableEngines.forEach(e => {
                const selected = e.id === char.engine ? 'selected' : '';
                engineOpts += `<option value="${e.id}" ${selected}>${e.name}</option>`;
            });

            // Fetch voices for current engine selection
            const voices = await this.fetchVoices(char.engine, primaryLang);
            let voiceOpts = '<option value="">(Select Voice)</option>';
            
            // If XTTS, voices list might be empty or locales. 
            // For Edge/ElevenLabs/gTTS we have lists.
            voices.forEach(v => {
                const selected = (v.id === char.voice) ? 'selected' : '';
                voiceOpts += `<option value="${v.id}" ${selected}>${v.name} (${v.gender})</option>`;
            });

            // If current voice isn't in list (e.g. from different language), add it
            if (char.voice && !voices.find(v => v.id === char.voice)) {
                voiceOpts += `<option value="${char.voice}" selected>${char.voice} (Current)</option>`;
            }

            // Reference Upload Section (XTTS/ElevenLabs cloning)
            let referenceHtml = '';
            if (char.engine === 'xtts' || char.engine === 'elevenlabs') {
                referenceHtml = `
                    <div class="form-group" style="flex:2;">
                        <label>Reference Audio (Cloning)</label>
                        <div style="display:flex; gap:0.5rem; align-items:center;">
                            <input type="text" value="${this.escapeHtml(char.reference_audio || '')}" readonly style="flex:1; opacity:0.7;">
                            <button class="btn small" onclick="app.triggerRefUpload('${cid}')">Upload</button>
                            <button class="btn small" onclick="app.previewVoice('${cid}')">Preview</button>
                        </div>
                    </div>
                `;
            } else {
                referenceHtml = `
                    <div class="form-group" style="flex:2;">
                        <label>Persona</label>
                        <input type="text" value="${this.escapeHtml(char.persona || '')}" 
                               onchange="app.updateCharacter('${cid}', 'persona', this.value)">
                    </div>
                `;
            }

            el.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <h4 style="margin:0; color:var(--accent);">${char.name} <span style="color:#666; font-weight:normal;">(${cid})</span></h4>
                    <button class="btn small" style="opacity:0.6" onclick="app.removeCharacter('${cid}')">Remove</button>
                </div>
                <div class="form-row" style="margin-bottom:0.5rem;">
                    <div class="form-group">
                        <label>Engine</label>
                        <select onchange="app.updateCharacter('${cid}', 'engine', this.value)">
                            ${engineOpts}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Voice</label>
                        <select onchange="app.updateCharacter('${cid}', 'voice', this.value)">
                            ${voiceOpts}
                        </select>
                    </div>
                </div>
                <div class="form-row" style="margin-bottom:0;">
                    <div class="form-group" style="flex:1;">
                        <label>Dialect</label>
                        <select onchange="app.updateCharacter('${cid}', 'dialect', this.value)">
                            <option value="msa" ${char.dialect === 'msa' ? 'selected' : ''}>MSA</option>
                            <option value="eg" ${char.dialect === 'eg' ? 'selected' : ''}>Egyptian</option>
                            <option value="sa" ${char.dialect === 'sa' ? 'selected' : ''}>Saudi</option>
                            <option value="ae" ${char.dialect === 'ae' ? 'selected' : ''}>Emirati</option>
                        </select>
                    </div>
                    ${referenceHtml}
                </div>
            `;
            list.appendChild(el);
        }
    },
    
    async updateCharacter(cid, field, value) {
        if (!this.currentData.characters[cid]) return;
        
        this.currentData.characters[cid][field] = value;
        
        // If engine changed, voice might be invalid, and we need to refresh list
        if (field === 'engine') {
            this.currentData.characters[cid].voice = ''; // Reset voice
            await this.saveProject();
            this.renderCast(); // Re-render to update voice list and toggle reference/persona
        } else {
            // For other fields, just save
            await this.saveProject();
        }
    },

    async removeCharacter(cid) {
        if (!confirm(`Remove character ${cid}?`)) return;
        delete this.currentData.characters[cid];
        await this.saveProject();
        this.renderCast();
    },
    
    async addCharacter() {
        const id = prompt("Character ID (e.g. hero):");
        if (!id) return;
        // Check for duplicate
        if (this.currentData.characters && this.currentData.characters[id]) {
            alert("ID already exists.");
            return;
        }

        const name = prompt("Display Name:");
        if (!this.currentData.characters) this.currentData.characters = {};
        
        this.currentData.characters[id] = {
            name: name || id,
            engine: "edge",
            voice: "",
            dialect: "msa"
        };
        await this.saveProject();
        this.renderCast();
    },

    triggerRefUpload(cid) {
        this.activeUploadCid = cid;
        document.getElementById('file-upload-ref').click();
    },

    async handleRefUpload(input) {
        if (!input.files.length || !this.activeUploadCid) return;
        const file = input.files[0];
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/upload?category=references`, {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                const data = await res.json();
                this.updateCharacter(this.activeUploadCid, 'reference_audio', data.path);
                alert("Reference uploaded!");
                this.renderCast();
            } else {
                const err = await res.json();
                alert(`Upload failed: ${err.detail}`);
            }
        } catch(e) { alert(e.message); }
        input.value = ''; // Reset
    },

    async handleMusicUpload(input) {
        if (!input.files.length) return;
        const file = input.files[0];
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/upload?category=music`, {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                alert("Background music uploaded!");
                this.fetchMusicFiles();
                this.fetchAssets();
            } else {
                const err = await res.json();
                alert(`Upload failed: ${err.detail}`);
            }
        } catch(e) { alert(e.message); }
        input.value = '';
    },

    async previewVoice(cid) {
        const char = this.currentData.characters[cid];
        const text = prompt("Enter text for preview:", "مرحبا بالعالم. هذا اختبار للصوت.");
        if (!text) return;
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/preview`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    text: text,
                    engine: char.engine,
                    voice: char.voice,
                    reference_audio: char.reference_audio,
                    language: 'ar' // Default to arabic for preview
                })
            });
            
            if (res.ok) {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const audio = new Audio(url);
                audio.play();
            } else {
                const err = await res.json();
                alert(`Preview failed: ${err.detail}`);
            }
        } catch(e) { alert(e.message); }
    },

    renderEngineSettings() {
        const gen = this.currentData.generation || {};
        document.getElementById('conf-chunk-chars').value = gen.chunk_max_chars || 200;
        document.getElementById('conf-crossfade').value = gen.crossfade_ms || 120;
        document.getElementById('conf-strategy').value = gen.chunk_strategy || 'breath_group';
        document.getElementById('conf-fail-thresh').value = gen.fail_threshold_percent || 5;
        document.getElementById('conf-silence').value = gen.leading_silence_ms || 100;
        document.getElementById('conf-fallback-scope').value = gen.fallback_scope || 'chapter';

        // XTTS Settings
        document.getElementById('conf-xtts-temp').value = gen.xtts_temperature || 0.7;
        document.getElementById('conf-xtts-rep').value = gen.xtts_repetition_penalty || 5.0;
        document.getElementById('conf-xtts-vram').value = gen.xtts_vram_management || 'empty_cache_per_chapter';

        const mix = this.currentData.mix || {};
        document.getElementById('conf-lufs').value = mix.target_lufs || -16.0;
        document.getElementById('conf-vol').value = mix.master_volume || 0.9;
    },

    renderForm() {
        // Chapters List
        const d = this.currentData;
        const s = this.currentStatus;
        const chList = document.getElementById('chapter-list');
        chList.innerHTML = '';
        (d.chapters || []).forEach((ch, idx) => {
            const row = document.createElement('div');
            row.className = 'list-item';
            if (this.selectedChapterIndex === idx) row.classList.add('active');
            
            // Determine status
            let status = 'pending';
            if (s && s.nodes && s.nodes.generate && s.nodes.generate.chapters) {
                const chStat = s.nodes.generate.chapters[ch.id];
                if (chStat) status = chStat.status;
            }
            
            let statusBadge = `<span class="status-badge ${status}">${status}</span>`;
            
            // Actions
            let actions = `
                <div class="action-buttons">
                    <button class="btn small" onclick="app.selectChapter(${idx})">Edit</button>
                    <button class="btn small success" onclick="event.stopPropagation(); app.generateSingleChapter('${ch.id}')">⚡Gen</button>
                    ${status === 'complete' ? `<button class="btn small" onclick="event.stopPropagation(); app.playChapter('${ch.id}')">▶ Play</button>` : ''}
                </div>
            `;

            row.innerHTML = `
                <span>${this.escapeHtml(ch.id)}</span>
                <span>${this.escapeHtml(ch.title || '')}</span>
                <span>${this.escapeHtml(ch.language || '')}</span>
                <span>${statusBadge}</span>
                <span>${actions}</span>
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
        
        // Remove badge from detail view as it's now in the list
        // document.getElementById('chap-status-badge').style.display = 'none';

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

        // XTTS Settings
        gen.xtts_temperature = parseFloat(document.getElementById('conf-xtts-temp').value);
        gen.xtts_repetition_penalty = parseFloat(document.getElementById('conf-xtts-rep').value);
        gen.xtts_vram_management = document.getElementById('conf-xtts-vram').value;

        if (!this.currentData.mix) this.currentData.mix = {};
        this.currentData.mix.target_lufs = parseFloat(document.getElementById('conf-lufs').value);
        this.currentData.mix.master_volume = parseFloat(document.getElementById('conf-vol').value);
    },

    renderJson() {
        document.getElementById('json-editor').value = JSON.stringify(this.currentData, null, 2);
    },

    switchTab(targetTab, skipSync = false) {
        if (!skipSync) this.updateDataFromForm(); // Always sync from form before switching

        ['overview', 'cast', 'chapters', 'engine', 'json', 'assets'].forEach(t => {
            const el = document.getElementById(`tab-${t}`);
            const btn = document.getElementById(`tab-btn-${t}`);
            if (!el) return;
            
            if (t === targetTab) {
                el.classList.remove('hidden');
                if (btn) btn.classList.add('active');
            } else {
                el.classList.add('hidden');
                if (btn) btn.classList.remove('active');
            }
        });
        
        // If switching to JSON tab, refresh it
        if (targetTab === 'json') this.renderJson();
        if (targetTab === 'assets') this.fetchAssets();
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
        
        // Populate Metadata inputs
        const meta = this.currentData.export?.metadata || {};
        document.getElementById('meta-title').value = meta.title || this.currentProject;
        document.getElementById('meta-author').value = meta.author || '';
        document.getElementById('meta-narrator').value = meta.narrator || '';
        document.getElementById('meta-year').value = meta.year || new Date().getFullYear();
        
        this.fetchFiles();
    },

    onExportFormatChange() {
        const fmt = document.getElementById('export-format').value;
        const mp3Group = document.getElementById('group-mp3-bitrate');
        const aacGroup = document.getElementById('group-aac-bitrate');
        
        if (fmt === 'm4b') {
            mp3Group.classList.add('hidden');
            aacGroup.classList.remove('hidden');
        } else if (fmt === 'mp3') {
            mp3Group.classList.remove('hidden');
            aacGroup.classList.add('hidden');
        } else {
            // WAV
            mp3Group.classList.add('hidden');
            aacGroup.classList.add('hidden');
        }
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
            list.innerHTML = '<div class="card">No exported files found. Click "Export Now".</div>';
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
                <div style="display:flex; align-items:center; gap:1rem;">
                    <span class="file-size">${sizeMB} MB</span>
                    <a href="/projects/${this.currentProject}/${f.path}" target="_blank" download class="btn small">⬇</a>
                </div>
            `;
            list.appendChild(el);
        });
    },

    async triggerExport() {
        // Save metadata first
        if (!this.currentData.export) this.currentData.export = {};
        this.currentData.export.metadata = {
            title: document.getElementById('meta-title').value,
            author: document.getElementById('meta-author').value,
            narrator: document.getElementById('meta-narrator').value,
            year: parseInt(document.getElementById('meta-year').value),
        };
        await this.saveProject();

        const fmt = document.getElementById('export-format').value;
        let bitrate = 192;
        
        if (fmt === 'mp3') {
            bitrate = parseInt(document.getElementById('export-bitrate').value);
        } else if (fmt === 'm4b') {
            bitrate = parseInt(document.getElementById('export-aac-bitrate').value);
        }
        
        const statusPanel = document.getElementById('export-status-panel');
        const statusText = document.getElementById('export-status-text');
        const statusMsg = document.getElementById('export-status-msg');
        
        statusPanel.classList.remove('hidden');
        statusText.innerText = 'Running...';
        statusMsg.innerText = `Exporting as ${fmt.toUpperCase()} (${bitrate}kbps)...`;
        
        try {
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
    // Assets (SFX/Music)
    // ──────────────────────────────────────────────

    async fetchAssets() {
        const list = document.getElementById('assets-list');
        list.innerHTML = '<div class="card loading">Loading assets...</div>';
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/files`);
            if (res.ok) {
                const files = await res.json();
                // Filter only sfx and music
                const assets = files.filter(f => f.category === 'sfx' || f.category === 'music');
                this.renderAssetsList(assets);
            } else {
                list.innerHTML = '<div class="card" style="color:red">Failed to load assets</div>';
            }
        } catch(e) {
            console.error(e);
        }
    },

    renderAssetsList(files) {
        const list = document.getElementById('assets-list');
        list.innerHTML = '';
        
        if (files.length === 0) {
            list.innerHTML = '<div class="card">No assets generated yet. Use the tools above.</div>';
            return;
        }
        
        files.forEach(f => {
            const el = document.createElement('div');
            el.className = 'file-download';
            
            const sizeMB = (f.size / (1024*1024)).toFixed(2);
            const date = new Date(f.modified * 1000).toLocaleString();
            const badgeClass = f.category === 'sfx' ? 'warning' : 'complete'; // reuse colors
            
            el.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:0.2rem;">
                    <a href="/projects/${this.currentProject}/${f.path}" target="_blank">${f.name}</a>
                    <div style="display:flex; align-items:center; gap:0.5rem;">
                        <span class="status-badge ${badgeClass}">${f.category.toUpperCase()}</span>
                        <span class="file-size">${date} • ${sizeMB} MB</span>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:1rem;">
                    <button class="btn small" onclick="app.playAsset('${f.path}')">▶</button>
                    <a href="/projects/${this.currentProject}/${f.path}" target="_blank" download class="btn small">⬇</a>
                </div>
            `;
            list.appendChild(el);
        });
    },

    playAsset(path) {
        const url = `/projects/${this.currentProject}/${path}`;
        const audio = new Audio(url);
        audio.play();
    },

    async generateSFX() {
        const type = document.getElementById('sfx-type').value;
        const duration = parseFloat(document.getElementById('sfx-duration').value);
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/sfx`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ type: type, duration: duration })
            });
            
            if (res.ok) {
                const data = await res.json();
                alert(`Generated: ${data.message}`);
                this.fetchAssets();
            } else {
                const err = await res.json();
                alert(`Failed: ${err.detail}`);
            }
        } catch(e) { alert(e.message); }
    },

    async composeMusic() {
        const preset = document.getElementById('music-preset').value;
        const duration = parseFloat(document.getElementById('music-duration').value);
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/compose`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ preset: preset, duration: duration })
            });
            
            if (res.ok) {
                // Compose is async, so we just alert started. 
                // In real app, we'd poll or wait. For now, simple UX.
                alert(`Composition started for ${preset}. Check back in a moment.`);
                
                // Poll a few times to auto-refresh list
                setTimeout(() => this.fetchAssets(), 2000);
                setTimeout(() => this.fetchAssets(), 5000);
            } else {
                const err = await res.json();
                alert(`Failed: ${err.detail}`);
            }
        } catch(e) { alert(e.message); }
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
        this.loadMixConfig();
        this.fetchMusicFiles();
        
        if (this.currentStatus?.nodes?.mix) this.updateMixBadge(this.currentStatus.nodes.mix.status);
    },

    loadMixConfig() {
        const mix = this.currentData.mix || {};
        const duck = mix.ducking || {};
        
        document.getElementById('mix-master-vol').value = mix.master_volume || 0.9;
        document.getElementById('mix-target-lufs').value = mix.target_lufs || -16.0;
        
        document.getElementById('mix-duck-thresh').value = duck.vad_threshold || 0.5;
        document.getElementById('mix-duck-atten').value = duck.attenuation_db || -12;
        document.getElementById('mix-duck-lookahead').value = duck.look_ahead_ms || 200;
        document.getElementById('mix-duck-attack').value = duck.attack_ms || 100;
        document.getElementById('mix-duck-release').value = duck.release_ms || 500;
    },
    
    updateMixConfigFromForm() {
        if (!this.currentData.mix) this.currentData.mix = {};
        if (!this.currentData.mix.ducking) this.currentData.mix.ducking = {};
        
        const mix = this.currentData.mix;
        const duck = mix.ducking;
        
        mix.master_volume = parseFloat(document.getElementById('mix-master-vol').value);
        mix.target_lufs = parseFloat(document.getElementById('mix-target-lufs').value);
        
        duck.vad_threshold = parseFloat(document.getElementById('mix-duck-thresh').value);
        duck.attenuation_db = parseFloat(document.getElementById('mix-duck-atten').value);
        duck.look_ahead_ms = parseInt(document.getElementById('mix-duck-lookahead').value);
        duck.attack_ms = parseInt(document.getElementById('mix-duck-attack').value);
        duck.release_ms = parseInt(document.getElementById('mix-duck-release').value);
    },

    async fetchMusicFiles() {
        const select = document.getElementById('mix-music-file');
        // Keep first two options (Auto, None)
        select.length = 2; 
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/files`);
            if (res.ok) {
                const files = await res.json();
                files.filter(f => f.category === 'music').forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.name; // Just the filename
                    opt.text = f.name;
                    select.add(opt);
                });
            }
        } catch(e) { console.error(e); }
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
        this.updateMixConfigFromForm();
        await this.saveProject();
        
        const btn = document.getElementById('btn-mix');
        btn.disabled = true;
        btn.innerText = "Starting...";
        
        const musicVal = document.getElementById('mix-music-file').value;
        // Construct API URL with music param if selected (or 'none' explicitly)
        // If empty string (Auto), send nothing (null)
        let url = `${API_BASE}/projects/${this.currentProject}/mix`;
        if (musicVal === 'none') {
            // Logic handled by backend? No, API takes music_file param.
            // If we want NO music, we might need a way to signal that.
            // Current backend: if music_file provided, uses it. If None, auto-detects.
            // To force NO music, we might need to pass a special value or update backend logic.
            // Hack for now: pass a non-existent file? No, that warns.
            // Proper fix: Backend should support explicit "none".
            // For now, let's assume 'none' string is not a file and handle gracefully or just omit.
            // Actually, if value is 'none', let's not pass parameter, but that triggers auto-detect.
            // Let's pass 'none' as query param and let backend fail gracefully to voice-only? 
            // In mix.py: if music_file provided and not found, it falls back to voice-only with warning.
            // So passing "FORCE_NO_MUSIC" works.
            url += `?music=FORCE_NO_MUSIC`; 
        } else if (musicVal) {
            url += `?music=${encodeURIComponent(musicVal)}`;
        }
        
        try {
            const res = await fetch(url, { method: 'POST' });
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
                this.currentStatus = await res.json();
                const mixStatus = this.currentStatus.nodes?.mix?.status;
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
    
    async generateSingleChapter(chapterId) {
        if (!confirm(`Regenerate chapter ${chapterId}? This will overwrite existing audio.`)) return;
        
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chapters: [chapterId] })
            });
            if (res.ok) {
                alert(`Started generation for ${chapterId}`);
                // Start polling to update UI
                this.pollStatus(chapterId);
            } else {
                alert("Generation failed to start");
            }
        } catch(e) {
            alert(e.message);
        }
    },
    
    toggleCollapse(el) {
        el.classList.toggle('collapsed');
    },
    
    playChapter(chapterId) {
        // Try playing from Mix renders first, then raw
        const audio = new Audio(`/projects/${this.currentProject}/06_MIX/renders/${chapterId}.wav`);
        audio.onerror = () => {
            // Fallback to processed
            audio.src = `/projects/${this.currentProject}/03_GENERATED/processed/${chapterId}.wav`;
            audio.onerror = () => {
                // Fallback to raw
                audio.src = `/projects/${this.currentProject}/03_GENERATED/raw/${chapterId}.wav`;
                audio.play().catch(e => alert("Audio not found"));
            };
            audio.play();
        };
        audio.play();
    },

    pollStatus(chapterId) {
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.pollInterval = setInterval(async () => {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
            if (res.ok) {
                this.currentStatus = await res.json();
                
                // If editing specific chapter, update detail
                if (this.selectedChapterIndex !== -1 && 
                    this.currentData.chapters[this.selectedChapterIndex].id === chapterId) {
                    this.populateChapterDetail(); 
                }
                
                // Always refresh list to update badges
                this.renderForm();
                
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
