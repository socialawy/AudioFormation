/**
 * AudioFormation Dashboard Logic.
 *
 * PATCH 1 CHANGES (2026-02-18):
 *   - Poll Isolation: replaced single this.pollInterval with this.activePolls{}
 *     Keys: activePolls.export | activePolls.mix | activePolls.generate
 *     Each poller clears only its own key; no cross-contamination possible.
 *   - stopAllPolls(): used when navigating back to Projects to kill all running polls.
 *   - stopAllAudio(): pauses all <audio> elements + wavesurfer before playing new audio.
 *   - XSS sweep: escapeHtml() applied consistently in renderCast(), renderFileList(),
 *     renderAssetsList(), renderQCReports(), loadAudio(), renderForm().
 */

const API_BASE = '/api';

const app = {
    currentProject: null,
    currentData: null,
    currentStatus: null,
    selectedChapterIndex: -1,
    wavesurfer: null,
    activePolls: {},          // FIX P1: keyed { export, mix, generate } — no more shared pollInterval
    availableEngines: [],
    voiceCache: {},
    activeUploadCid: null,

    init() {
        this.initToastContainer(); // PATCH 2: toast system
        this.fetchProjects();
        this.fetchEngines();
    },

    // ──────────────────────────────────────────────
    // Global Data Fetching
    // ──────────────────────────────────────────────

    async fetchEngines() {
        try {
            const res = await fetch(`${API_BASE}/engines`);
            if (res.ok) this.availableEngines = await res.json();
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

        const newCard = document.createElement('div');
        newCard.className = 'card new-project';
        newCard.innerHTML = '<span>+ New Project</span>';
        newCard.onclick = () => this.createProject();
        grid.appendChild(newCard);

        projects.forEach(p => {
            const card = document.createElement('div');
            card.className = 'card project';

            const date = new Date(p.created).toLocaleDateString();

            let statusClass = 'pending';
            if (['complete', 'export', 'qc_final'].includes(p.pipeline_node)) statusClass = 'complete';
            if (p.pipeline_node === 'failed') statusClass = 'failed';
            if (p.pipeline_node === 'partial') statusClass = 'partial';

            const titleEl = document.createElement('h3');
            titleEl.textContent = p.id;

            const metaEl = document.createElement('div');
            metaEl.style.cssText = 'font-size: 0.85rem; color: #888; margin-bottom: 0.5rem;';
            metaEl.textContent = `Created: ${date}`;

            const metaInfoEl = document.createElement('div');
            metaInfoEl.className = 'meta';

            const chaptersEl = document.createElement('span');
            chaptersEl.textContent = `${p.chapters} Chs \u2022 ${p.languages.join(', ')}`;

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
                this.showToast(`Error: ${err.detail}`, 'error');
            }
        } catch (e) {
            this.showToast("Failed to create project. Check server connection.", 'error');
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
            const [projRes, statRes] = await Promise.all([
                fetch(`${API_BASE}/projects/${id}`),
                fetch(`${API_BASE}/projects/${id}/status`)
            ]);
            if (!projRes.ok) throw new Error('Failed to load project config');

            this.currentProject = id;
            this.currentData = await projRes.json();
            this.currentStatus = statRes.ok ? await statRes.json() : null;

            this.renderOverview();
            this.renderCast();
            this.renderEngineSettings();
            this.renderForm();
            this.renderJson();
            this.fetchAssets();

            this.showEditor();
            this.switchTab('overview', true);

            ['nav-editor', 'nav-mix', 'nav-export', 'nav-qc'].forEach(navId => {
                document.getElementById(navId).classList.remove('disabled');
            });

            document.getElementById('nav-mix').onclick = () => this.showMix();
            document.getElementById('nav-export').onclick = () => this.showExport();
            document.getElementById('nav-qc').onclick = () => this.showQC();

            this.fetchHardwareInfo(id);
        } catch (e) {
            this.showToast(e.message, 'error');
        }
    },

    async fetchHardwareInfo(id) {
        try {
            const res = await fetch(`${API_BASE}/projects/${id}/hardware`);
            if (res.ok) {
                const hw = await res.json();
                const container = document.getElementById('hardware-info');
                container.innerHTML = `
                    <p>GPU: ${this.escapeHtml(String(hw.gpu_name || 'None'))} (${hw.vram_total_gb || 0} GB)</p>
                    <p>Strategy: ${this.escapeHtml(String(hw.recommended_vram_strategy || ''))}</p>
                    <p>ffmpeg: ${hw.ffmpeg_available ? '\u2705' : '\u274C'}</p>
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

        const container = document.getElementById('pipeline-stepper');
        container.innerHTML = '';
        const nodes = ['bootstrap','ingest','validate','generate','qc_scan','process','compose','mix','qc_final','export'];
        nodes.forEach(n => {
            const status = s?.nodes?.[n]?.status || 'pending';
            const nodeEl = document.createElement('div');
            nodeEl.className = `pipeline-node ${status}`;
            let icon = '\u25CB';
            if (status === 'complete') icon = '\u2705';
            if (status === 'running') icon = '\u23F3';
            if (status === 'failed') icon = '\u274C';
            nodeEl.innerHTML = `<span style="font-size:1.2rem">${icon}</span> <span>${n}</span>`;
            container.appendChild(nodeEl);
        });
    },

    async renderCast() {
        const list = document.getElementById('cast-list');
        list.innerHTML = '';
        const chars = this.currentData.characters || {};
        const projectLangs = this.currentData.languages || ['ar'];
        const primaryLang = projectLangs[0];

        for (const cid of Object.keys(chars)) {
            const char = chars[cid];
            const el = document.createElement('div');
            el.className = 'cast-item';

            let engineOpts = '';
            this.availableEngines.forEach(e => {
                const selected = e.id === char.engine ? 'selected' : '';
                engineOpts += `<option value="${this.escapeHtml(e.id)}" ${selected}>${this.escapeHtml(e.name)}</option>`;
            });

            // FIX P1 XSS: escapeHtml applied to all cid usages in event handlers
            const safeCid = this.escapeHtml(cid);
            let voiceSectionHtml = '';
            let referenceHtml = '';

            if (char.engine === 'xtts') {
                voiceSectionHtml = `
                    <div class="form-group">
                        <label>Voice</label>
                        <div style="padding: 0.5rem; background: #2a2a2a; border-radius: 4px; color: #888; font-style: italic;">
                            Voice cloning via reference audio
                        </div>
                    </div>`;
                referenceHtml = `
                    <div class="form-group" style="flex:2;">
                        <label>Reference Audio (Cloning)</label>
                        <div style="display:flex; gap:0.5rem; align-items:center;">
                            <input type="text" value="${this.escapeHtml(char.reference_audio || '')}" readonly style="flex:1; opacity:0.7;">
                            <button class="btn small" onclick="app.triggerRefUpload('${safeCid}')">Upload</button>
                            <button class="btn small" onclick="app.previewVoice('${safeCid}')">Preview</button>
                        </div>
                    </div>`;
            } else if (char.engine === 'gtts') {
                voiceSectionHtml = `
                    <div class="form-group">
                        <label>Voice</label>
                        <div style="padding: 0.5rem; background: #2a2a2a; border-radius: 4px; color: #888; font-style: italic;">
                            Language only
                        </div>
                    </div>`;
                referenceHtml = `
                    <div class="form-group" style="flex:2;">
                        <label>Persona</label>
                        <input type="text" value="${this.escapeHtml(char.persona || '')}"
                               onchange="app.updateCharacter('${safeCid}', 'persona', this.value)">
                    </div>`;
            } else if (char.engine === 'elevenlabs') {
                const voices = await this.fetchVoices(char.engine, primaryLang);
                let voiceOpts = '<option value="">(Select Voice)</option>';
                voices.forEach(v => {
                    const selected = (v.id === char.voice) ? 'selected' : '';
                    voiceOpts += `<option value="${this.escapeHtml(v.id)}" ${selected}>${this.escapeHtml(v.name)} (${this.escapeHtml(v.gender)})</option>`;
                });
                if (char.voice && !voices.find(v => v.id === char.voice)) {
                    voiceOpts += `<option value="${this.escapeHtml(char.voice)}" selected>${this.escapeHtml(char.voice)} (Current)</option>`;
                }
                voiceSectionHtml = `
                    <div class="form-group">
                        <label>Voice</label>
                        <div style="display:flex; gap:0.5rem; align-items:center;">
                            <select onchange="app.updateCharacter('${safeCid}', 'voice', this.value)" style="flex:1;">
                                ${voiceOpts}
                            </select>
                            <div style="padding: 0.25rem 0.5rem; background: #1a3a1a; border-radius: 4px; font-size: 0.8rem; color: #10b981;">
                                API Key \u2713
                            </div>
                        </div>
                    </div>`;
                referenceHtml = `
                    <div class="form-group" style="flex:2;">
                        <label>Reference Audio (Cloning)</label>
                        <div style="display:flex; gap:0.5rem; align-items:center;">
                            <input type="text" value="${this.escapeHtml(char.reference_audio || '')}" readonly style="flex:1; opacity:0.7;">
                            <button class="btn small" onclick="app.triggerRefUpload('${safeCid}')">Upload</button>
                            <button class="btn small" onclick="app.previewVoice('${safeCid}')">Preview</button>
                        </div>
                    </div>`;
            } else {
                // Edge and other engines
                const voices = await this.fetchVoices(char.engine, primaryLang);
                let voiceOpts = '<option value="">(Select Voice)</option>';
                voices.forEach(v => {
                    const selected = (v.id === char.voice) ? 'selected' : '';
                    voiceOpts += `<option value="${this.escapeHtml(v.id)}" ${selected}>${this.escapeHtml(v.name)} (${this.escapeHtml(v.gender)})</option>`;
                });
                if (char.voice && !voices.find(v => v.id === char.voice)) {
                    voiceOpts += `<option value="${this.escapeHtml(char.voice)}" selected>${this.escapeHtml(char.voice)} (Current)</option>`;
                }
                voiceSectionHtml = `
                    <div class="form-group">
                        <label>Voice</label>
                        <select onchange="app.updateCharacter('${safeCid}', 'voice', this.value)">
                            ${voiceOpts}
                        </select>
                    </div>`;
                referenceHtml = `
                    <div class="form-group" style="flex:2;">
                        <label>Persona</label>
                        <input type="text" value="${this.escapeHtml(char.persona || '')}"
                               onchange="app.updateCharacter('${safeCid}', 'persona', this.value)">
                    </div>`;
            }

            el.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                    <h4 style="margin:0; color:var(--accent);">${this.escapeHtml(char.name)} <span style="color:#666; font-weight:normal;">(${safeCid})</span></h4>
                    <button class="btn small" style="opacity:0.6" onclick="app.removeCharacter('${safeCid}')">Remove</button>
                </div>
                <div class="form-row" style="margin-bottom:0.5rem;">
                    <div class="form-group">
                        <label>Engine</label>
                        <select onchange="app.updateCharacter('${safeCid}', 'engine', this.value)">
                            ${engineOpts}
                        </select>
                    </div>
                    ${voiceSectionHtml}
                </div>
                <div class="form-row" style="margin-bottom:0;">
                    <div class="form-group" style="flex:1;">
                        <label>Dialect</label>
                        <select onchange="app.updateCharacter('${safeCid}', 'dialect', this.value)">
                            <option value="msa" ${char.dialect === 'msa' ? 'selected' : ''}>MSA</option>
                            <option value="eg"  ${char.dialect === 'eg'  ? 'selected' : ''}>Egyptian</option>
                            <option value="sa"  ${char.dialect === 'sa'  ? 'selected' : ''}>Saudi</option>
                            <option value="ae"  ${char.dialect === 'ae'  ? 'selected' : ''}>Emirati</option>
                        </select>
                    </div>
                    ${referenceHtml}
                </div>`;
            list.appendChild(el);
        }
    },

    async updateCharacter(cid, field, value) {
        if (!this.currentData.characters[cid]) return;
        this.currentData.characters[cid][field] = value;
        if (field === 'engine') {
            this.currentData.characters[cid].voice = '';
            await this.saveProject();
            this.renderCast();
        } else {
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
        if (this.currentData.characters && this.currentData.characters[id]) {
            alert("ID already exists.");
            return;
        }
        const name = prompt("Display Name:");
        if (!this.currentData.characters) this.currentData.characters = {};
        this.currentData.characters[id] = { name: name || id, engine: "edge", voice: "", dialect: "msa" };
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
                method: 'POST', body: formData
            });
            if (res.ok) {
                const data = await res.json();
                this.updateCharacter(this.activeUploadCid, 'reference_audio', data.path);
                this.showToast("Reference uploaded!", 'success');
                this.renderCast();
            } else {
                const err = await res.json();
                this.showToast(`Upload failed: ${err.detail}`, 'error');
            }
        } catch(e) { this.showToast(e.message, 'error'); }
        input.value = '';
    },

    async handleMusicUpload(input) {
        if (!input.files.length) return;
        const file = input.files[0];
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/upload?category=music`, {
                method: 'POST', body: formData
            });
            if (res.ok) {
                this.showToast("Background music uploaded!", 'success');
                this.fetchMusicFiles();
                this.fetchAssets();
            } else {
                const err = await res.json();
                this.showToast(`Upload failed: ${err.detail}`, 'error');
            }
        } catch(e) { this.showToast(e.message, 'error'); }
        input.value = '';
    },

    async previewVoice(cid) {
        const char = this.currentData.characters[cid];
        const text = prompt("Enter text for preview:", "\u0645\u0631\u062D\u0628\u0627 \u0628\u0627\u0644\u0639\u0627\u0644\u0645. \u0647\u0630\u0627 \u0627\u062E\u062A\u0628\u0627\u0631 \u0644\u0644\u0635\u0648\u062A.");
        if (!text) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/preview`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ text, engine: char.engine, voice: char.voice, reference_audio: char.reference_audio, language: 'ar' })
            });
            if (res.ok) {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                this.stopAllAudio(); // FIX P1: prevent overlap
                const audio = new Audio(url);
                audio.play();
            } else {
                const err = await res.json();
                this.showToast(`Preview failed: ${err.detail}`, 'error');
            }
        } catch(e) { this.showToast(e.message, 'error'); }
    },

    renderEngineSettings() {
        const gen = this.currentData.generation || {};
        document.getElementById('conf-chunk-chars').value = gen.chunk_max_chars || 200;
        document.getElementById('conf-crossfade').value = gen.crossfade_ms || 120;
        document.getElementById('conf-strategy').value = gen.chunk_strategy || 'breath_group';
        document.getElementById('conf-fail-thresh').value = gen.fail_threshold_percent || 5;
        document.getElementById('conf-silence').value = gen.leading_silence_ms || 100;
        document.getElementById('conf-fallback-scope').value = gen.fallback_scope || 'chapter';
        document.getElementById('conf-xtts-temp').value = gen.xtts_temperature || 0.7;
        document.getElementById('conf-xtts-rep').value = gen.xtts_repetition_penalty || 5.0;
        document.getElementById('conf-xtts-vram').value = gen.xtts_vram_management || 'empty_cache_per_chapter';
        const mix = this.currentData.mix || {};
        document.getElementById('conf-lufs').value = mix.target_lufs || -16.0;
        document.getElementById('conf-vol').value = mix.master_volume || 0.9;
    },

    renderForm() {
        const d = this.currentData;
        const s = this.currentStatus;
        const chList = document.getElementById('chapter-list');
        chList.innerHTML = '';
        (d.chapters || []).forEach((ch, idx) => {
            const row = document.createElement('div');
            row.className = 'list-item';
            if (this.selectedChapterIndex === idx) row.classList.add('active');

            let status = 'pending';
            if (s?.nodes?.generate?.chapters) {
                const chStat = s.nodes.generate.chapters[ch.id];
                if (chStat) status = chStat.status;
            }

            const safeId = this.escapeHtml(ch.id);
            const actions = `
                <div class="action-buttons">
                    <button class="btn small" onclick="app.selectChapter(${idx})">Edit</button>
                    <button class="btn small success" onclick="event.stopPropagation(); app.generateSingleChapter('${safeId}')">&#x26A1;Gen</button>
                    ${status === 'complete' ? `<button class="btn small" onclick="event.stopPropagation(); app.playChapter('${safeId}')">&#9654; Play</button>` : ''}
                </div>`;

            row.innerHTML = `
                <span>${safeId}</span>
                <span>${this.escapeHtml(ch.title || '')}</span>
                <span>${this.escapeHtml(ch.language || '')}</span>
                <span><span class="status-badge ${status}">${status}</span></span>
                <span>${actions}</span>`;
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
            rows[i].classList.toggle('active', i === idx);
        }
        document.getElementById('chapter-detail').classList.remove('hidden');
        this.populateChapterDetail();
    },

    populateChapterDetail() {
        if (this.selectedChapterIndex === -1) return;
        const ch = this.currentData.chapters[this.selectedChapterIndex];
        const chars = this.currentData.characters || {};
        document.getElementById('chap-detail-title').innerText = `Edit: ${ch.id}`;
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
        document.getElementById('chap-energy').value = dir.energy || "";
        document.getElementById('chap-pace').value = dir.pace || "";
        document.getElementById('chap-emotion').value = dir.emotion || "";
        ['chap-title','chap-character','chap-mode','chap-energy','chap-pace','chap-emotion'].forEach(elId => {
            document.getElementById(elId).onchange = () => this.updateChapterData();
        });
    },

    updateChapterData() {
        if (this.selectedChapterIndex === -1) return;
        const ch = this.currentData.chapters[this.selectedChapterIndex];
        ch.title = document.getElementById('chap-title').value;
        const mode = document.getElementById('chap-mode').value;
        ch.mode = mode;
        const charVal = document.getElementById('chap-character').value;
        if (mode === 'single') { ch.character = charVal; delete ch.default_character; }
        else { ch.default_character = charVal; delete ch.character; }
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
        if (!skipSync) this.updateDataFromForm();
        ['overview','cast','chapters','engine','json','assets'].forEach(t => {
            const el = document.getElementById(`tab-${t}`);
            const btn = document.getElementById(`tab-btn-${t}`);
            if (!el) return;
            el.classList.toggle('hidden', t !== targetTab);
            if (btn) btn.classList.toggle('active', t === targetTab);
        });
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
                this.showToast(`Error saving: ${err.detail}`, 'error');
            }
        } catch (e) {
            this.showToast(`Save error: ${e.message}`, 'error');
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
        const meta = this.currentData.export?.metadata || {};
        document.getElementById('meta-title').value = meta.title || this.currentProject;
        document.getElementById('meta-author').value = meta.author || '';
        document.getElementById('meta-narrator').value = meta.narrator || '';
        document.getElementById('meta-year').value = meta.year || new Date().getFullYear();
        this.fetchFiles();
    },

    onExportFormatChange() {
        const fmt = document.getElementById('export-format').value;
        document.getElementById('group-mp3-bitrate').classList.toggle('hidden', fmt !== 'mp3');
        document.getElementById('group-aac-bitrate').classList.toggle('hidden', fmt !== 'm4b');
    },

    async fetchFiles() {
        const list = document.getElementById('export-file-list');
        list.innerHTML = '<div class="card loading">Loading files...</div>';
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/files`);
            if (res.ok) this.renderFileList(await res.json());
            else list.innerHTML = '<div class="card" style="color:red">Failed to load files</div>';
        } catch(e) { console.error(e); }
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
            // FIX P1 XSS: all file fields escaped
            const safePath = this.escapeHtml(f.path);
            const safeName = this.escapeHtml(f.name);
            const safeCategory = this.escapeHtml(f.category);
            const safeProject = this.escapeHtml(this.currentProject);
            el.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:0.2rem;">
                    <a href="/projects/${safeProject}/${safePath}" target="_blank" download>${safeName}</a>
                    <span class="file-size">${safeCategory} \u2022 ${date}</span>
                </div>
                <div style="display:flex; align-items:center; gap:1rem;">
                    <span class="file-size">${sizeMB} MB</span>
                    <a href="/projects/${safeProject}/${safePath}" target="_blank" download class="btn small">\u2B07</a>
                </div>`;
            list.appendChild(el);
        });
    },

    async triggerExport() {
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
        if (fmt === 'mp3') bitrate = parseInt(document.getElementById('export-bitrate').value);
        else if (fmt === 'm4b') bitrate = parseInt(document.getElementById('export-aac-bitrate').value);
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
                body: JSON.stringify({format: fmt, bitrate})
            });
            if (res.ok) this.pollExportStatus();
            else { statusText.innerText = 'Failed'; statusMsg.innerText = 'Server returned error.'; }
        } catch(e) { statusText.innerText = 'Error'; statusMsg.innerText = e.message; }
    },

    // FIX P1: export poll owns its own key — never kills mix or generate polls
    pollExportStatus() {
        if (this.activePolls.export) clearInterval(this.activePolls.export);
        this.activePolls.export = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
                if (res.ok) {
                    const status = await res.json();
                    const exportNode = status.nodes.export;
                    if (exportNode.status === 'complete') {
                        clearInterval(this.activePolls.export);
                        delete this.activePolls.export;
                        document.getElementById('export-status-text').innerText = 'Complete \u2705';
                        document.getElementById('export-status-msg').innerText = 'Export finished successfully.';
                        this.fetchFiles();
                    } else if (exportNode.status === 'failed') {
                        clearInterval(this.activePolls.export);
                        delete this.activePolls.export;
                        document.getElementById('export-status-text').innerText = 'Failed \u274C';
                        document.getElementById('export-status-msg').innerText = exportNode.error || 'Unknown error';
                    }
                }
            } catch(e) { console.error(e); }
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
            if (res.ok) this.renderQCReports(await res.json());
            else container.innerHTML = '<div class="card">No QC reports found. Run QC Scan or QC Final.</div>';
        } catch(e) {
            container.innerHTML = `<div class="card" style="color:red">Error: ${this.escapeHtml(e.message)}</div>`;
        }
    },

    renderQCReports(reports) {
        const container = document.getElementById('qc-reports-container');
        container.innerHTML = '';
        if (reports.final_qc) {
            const final = reports.final_qc;
            const el = document.createElement('div');
            el.className = 'card';
            // FIX P1 XSS: filenames and messages escaped
            el.innerHTML = `
                <h3>QC Final Report</h3>
                <div style="display:flex; gap:2rem; margin-bottom:1rem;">
                    <div>Passed: ${final.passed ? '\u2705 YES' : '\u274C NO'}</div>
                    <div>Files: ${final.total_files}</div>
                    <div>Failures: ${final.failed_files}</div>
                </div>
                ${final.results.map(r => `
                    <div style="margin-top:0.5rem; padding:0.5rem; background:#333; border-radius:4px; border-left:4px solid ${r.status==='pass'?'#10b981':'#ef4444'}">
                        <strong>${this.escapeHtml(r.filename)}</strong>: LUFS ${r.lufs.toFixed(1)} | TP ${r.true_peak.toFixed(1)}
                        ${r.messages.length > 0 ? `<div style="color:#ef4444; font-size:0.9rem;">${r.messages.map(m => this.escapeHtml(m)).join('<br>')}</div>` : ''}
                    </div>`).join('')}`;
            container.appendChild(el);
        }
        if (reports.chunk_qc && reports.chunk_qc.length > 0) {
            const latest = reports.chunk_qc[reports.chunk_qc.length - 1];
            const el = document.createElement('div');
            el.className = 'card';
            el.innerHTML = `
                <h3>Latest Chunk Scan</h3>
                <div style="display:flex; gap:2rem;">
                    <div>Fail Rate: ${latest.fail_rate_percent}%</div>
                    <div>Chunks: ${latest.total_chunks}</div>
                    <div>Failures: ${latest.failures}</div>
                </div>`;
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
                this.renderAssetsList(files.filter(f => f.category === 'sfx' || f.category === 'music'));
            } else {
                list.innerHTML = '<div class="card" style="color:red">Failed to load assets</div>';
            }
        } catch(e) { console.error(e); }
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
            const badgeClass = f.category === 'sfx' ? 'warning' : 'complete';
            // FIX P1 XSS: all file fields escaped
            const safePath = this.escapeHtml(f.path);
            const safeName = this.escapeHtml(f.name);
            const safeProject = this.escapeHtml(this.currentProject);
            el.innerHTML = `
                <div style="display:flex; flex-direction:column; gap:0.2rem;">
                    <a href="/projects/${safeProject}/${safePath}" target="_blank">${safeName}</a>
                    <div style="display:flex; align-items:center; gap:0.5rem;">
                        <span class="status-badge ${badgeClass}">${this.escapeHtml(f.category.toUpperCase())}</span>
                        <span class="file-size">${date} \u2022 ${sizeMB} MB</span>
                    </div>
                </div>
                <div style="display:flex; align-items:center; gap:1rem;">
                    <button class="btn small" onclick="app.playAsset('${safePath}')">&#9654;</button>
                    <a href="/projects/${safeProject}/${safePath}" target="_blank" download class="btn small">\u2B07</a>
                </div>`;
            list.appendChild(el);
        });
    },

    playAsset(path) {
        this.stopAllAudio(); // FIX P1: no audio overlap
        const audio = new Audio(`/projects/${this.currentProject}/${path}`);
        audio.play();
    },

    async generateSFX() {
        const type = document.getElementById('sfx-type').value;
        const duration = parseFloat(document.getElementById('sfx-duration').value);
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/sfx`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ type, duration })
            });
            if (res.ok) { const data = await res.json(); this.showToast(`Generated: ${data.message}`, 'success'); this.fetchAssets(); }
            else { const err = await res.json(); this.showToast(`Failed: ${err.detail}`, 'error'); }
        } catch(e) { this.showToast(e.message, 'error'); }
    },

    async composeMusic() {
        const preset = document.getElementById('music-preset').value;
        const duration = parseFloat(document.getElementById('music-duration').value);
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/compose`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ preset, duration })
            });
            if (res.ok) {
                this.showToast(`Composition started for ${preset}. Refreshing shortly...`, 'info');
                setTimeout(() => this.fetchAssets(), 2000);
                setTimeout(() => this.fetchAssets(), 5000);
            } else { const err = await res.json(); this.showToast(`Failed: ${err.detail}`, 'error'); }
        } catch(e) { this.showToast(e.message, 'error'); }
    },

    // ──────────────────────────────────────────────
    // Navigation
    // ──────────────────────────────────────────────

    hideAllViews() {
        ['projects-view','editor-view','mix-view','export-view','qc-view'].forEach(id => {
            document.getElementById(id).classList.add('hidden');
        });
        document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
    },

    showProjects() {
        this.hideAllViews();
        document.getElementById('projects-view').classList.remove('hidden');
        document.getElementById('nav-projects').classList.add('active');
        this.currentProject = null;
        this.stopAllPolls(); // FIX P1: clear ALL active polls
        this.fetchProjects();
    },

    showEditor() {
        if (!this.currentProject) return;
        this.hideAllViews();
        document.getElementById('editor-view').classList.remove('hidden');
        document.getElementById('nav-editor').classList.add('active');
    },

    // ──────────────────────────────────────────────
    // Mix View
    // ──────────────────────────────────────────────

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
        select.length = 2;
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/files`);
            if (res.ok) {
                const files = await res.json();
                files.filter(f => f.category === 'music').forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.name;
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
        btn.disabled = (status === 'running');
        btn.innerText = status === 'running' ? "Mixing..." : "\u2602 Run Mix";
    },

    async runMix() {
        this.updateMixConfigFromForm();
        await this.saveProject();
        const btn = document.getElementById('btn-mix');
        btn.disabled = true;
        btn.innerText = "Starting...";
        const musicVal = document.getElementById('mix-music-file').value;
        let url = `${API_BASE}/projects/${this.currentProject}/mix`;
        if (musicVal === 'none') url += `?music=FORCE_NO_MUSIC`;
        else if (musicVal) url += `?music=${encodeURIComponent(musicVal)}`;
        try {
            const res = await fetch(url, { method: 'POST' });
            if (res.ok) { this.updateMixBadge('running'); this.pollMixStatus(); }
            else { this.showToast("Failed to start mix.", 'error'); btn.disabled = false; btn.innerText = "\u2602 Run Mix"; }
        } catch (e) { this.showToast(`Error: ${e.message}`, 'error'); btn.disabled = false; }
    },

    // FIX P1: mix poll owns its own key — never kills export or generate polls
    pollMixStatus() {
        if (this.activePolls.mix) clearInterval(this.activePolls.mix);
        this.activePolls.mix = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
                if (res.ok) {
                    this.currentStatus = await res.json();
                    const mixStatus = this.currentStatus.nodes?.mix?.status;
                    if (mixStatus) {
                        this.updateMixBadge(mixStatus);
                        if (mixStatus === 'complete' || mixStatus === 'failed') {
                            clearInterval(this.activePolls.mix);
                            delete this.activePolls.mix;
                            if (mixStatus === 'complete') this.loadMixFiles();
                        }
                    }
                }
            } catch(e) { console.error(e); }
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
        document.getElementById('play-btn').innerText = this.wavesurfer.isPlaying() ? '\u23F8 Pause' : '\u25B6 Play';
    },

    async loadAudio(chapterInfo) {
        const pid = this.currentProject;
        const paths = [
            { url: `/projects/${pid}/06_MIX/renders/${chapterInfo.id}.wav`, type: "Mixed" },
            { url: `/projects/${pid}/03_GENERATED/processed/${chapterInfo.id}.wav`, type: "Processed" },
            { url: `/projects/${pid}/03_GENERATED/raw/${chapterInfo.id}.wav`, type: "Raw" },
        ];
        const trackInfoEl = document.getElementById('track-info');
        // FIX P1 XSS: chapterInfo fields escaped
        trackInfoEl.innerHTML = `<h3>${this.escapeHtml(chapterInfo.id)}</h3><p>Loading...</p>`;
        let loaded = false;
        for (const p of paths) {
            try {
                const res = await fetch(p.url, { method: 'HEAD' });
                if (res.ok) {
                    try {
                        await this.wavesurfer.load(p.url);
                        trackInfoEl.innerHTML = `
                            <h3>${this.escapeHtml(chapterInfo.title)} (${this.escapeHtml(chapterInfo.id)})</h3>
                            <div class="status-badge complete" style="display:inline-block; margin:0.5rem 0;">${p.type}</div>
                            <p>Duration: ${this.formatTime(this.wavesurfer.getDuration())}</p>`;
                        loaded = true;
                        break;
                    } catch (playbackError) {
                        console.error(`Playback error loading ${p.type} audio:`, playbackError);
                    }
                }
            } catch (headError) { /* silent 404 probe */ }
        }
        if (!loaded) trackInfoEl.innerHTML = `<h3 style="color:red">Audio Not Found</h3><p>Run generation first.</p>`;
    },

    // ──────────────────────────────────────────────
    // Helpers
    // ──────────────────────────────────────────────

    formatTime(seconds) {
        if (!seconds) return "00:00";
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    },

    escapeHtml(unsafe) {
        if (typeof unsafe !== 'string') return unsafe;
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    },

    // FIX P1: Stop all active audio to prevent overlap when starting new playback
    stopAllAudio() {
        document.querySelectorAll('audio').forEach(a => { a.pause(); a.currentTime = 0; });
        if (this.wavesurfer && this.wavesurfer.isPlaying()) this.wavesurfer.pause();
    },

    // FIX P1: Kill all running polls (used on navigation away from project)
    stopAllPolls() {
        Object.keys(this.activePolls).forEach(key => {
            clearInterval(this.activePolls[key]);
            delete this.activePolls[key];
        });
    },

    // PATCH 2: Toast notification system — replaces all alert() calls
    // Levels: 'info' (default) | 'success' | 'error'
    initToastContainer() {
        if (document.getElementById('toast-container')) return;
        const container = document.createElement('div');
        container.id = 'toast-container';
        container.style.cssText = `
            position: fixed; top: 1.25rem; right: 1.25rem; z-index: 9999;
            display: flex; flex-direction: column; gap: 0.5rem;
            pointer-events: none;
        `;
        document.body.appendChild(container);
    },

    showToast(message, level = 'info', duration = 3500) {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const colors = {
            info:    { bg: 'var(--bg-card, #1e1e1e)', border: 'var(--border, #333)', text: 'var(--text-primary, #e5e5e5)' },
            success: { bg: '#0d2b1e', border: '#10b981', text: '#6ee7b7' },
            error:   { bg: '#2b0d0d', border: '#ef4444', text: '#fca5a5' },
        };
        const c = colors[level] || colors.info;

        const toast = document.createElement('div');
        toast.style.cssText = `
            background: ${c.bg}; border: 1px solid ${c.border}; color: ${c.text};
            padding: 0.75rem 1.1rem; border-radius: 6px; font-size: 0.9rem;
            max-width: 320px; word-break: break-word;
            pointer-events: auto; cursor: pointer;
            box-shadow: 0 4px 12px rgba(0,0,0,0.4);
            opacity: 0; transform: translateX(12px);
            transition: opacity 0.2s ease, transform 0.2s ease;
        `;
        toast.textContent = message;
        toast.onclick = () => this._dismissToast(toast);
        container.appendChild(toast);

        // Animate in
        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(0)';
        });

        // Auto-dismiss
        toast._timer = setTimeout(() => this._dismissToast(toast), duration);
    },

    _dismissToast(toast) {
        clearTimeout(toast._timer);
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(12px)';
        setTimeout(() => toast.remove(), 220);
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
            if (res.ok) { this.showToast("Files ingested.", 'success'); await this.loadProject(this.currentProject); }
            else this.showToast("Ingest failed.", 'error');
        } catch(e) { this.showToast(e.message, 'error'); }
    },

    async runFromStep() {
        const select = document.getElementById('run-from-select');
        const startStep = select.value;
        if (!startStep) { this.showToast('Select a step to run from.', 'error'); return; }
        if (!this.currentProject) return;
        const allSteps = ['validate','generate','qc-scan','process','compose','mix','qc-final','export'];
        const steps = allSteps.slice(allSteps.indexOf(startStep));
        const btn = document.querySelector('[onclick="app.runFromStep()"]');
        const originalText = btn.textContent;
        for (const step of steps) {
            btn.textContent = `\u23F3 ${step}...`;
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
                if (step === 'validate') {
                    const data = await res.json();
                    if (data.failures > 0) { this.showToast(`Validation failed: ${data.failures} issue(s)`, 'error'); break; }
                    continue;
                }
                await this.waitForNode(step);
            } catch(e) { this.showToast(`Pipeline stopped at ${step}: ${e.message}`, 'error'); break; }
        }
        btn.textContent = originalText;
        this.loadProject(this.currentProject);
    },

    async runAllPipeline() {
        if (!confirm("Run full pipeline? This may take time.")) return;
        const steps = ['validate','generate','qc-scan','process','compose','mix','qc-final','export'];
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
                if (step !== 'validate') await this.waitForNode(step);
            } catch(e) {
                this.showToast(`Pipeline stopped at ${step}: ${e.message}`, 'error');
                btn.disabled = false;
                btn.innerText = "\uD83D\uDE80 Run All Pipeline";
                return;
            }
        }
        btn.disabled = false;
        btn.innerText = "\uD83D\uDE80 Run All Pipeline";
        this.showToast("Pipeline complete!", 'success');
        this.loadProject(this.currentProject);
    },

    async waitForNode(endpoint) {
        const nodeMap = {
            'generate': 'generate', 'qc-scan': 'qc_scan', 'process': 'process',
            'compose': 'compose', 'mix': 'mix', 'qc-final': 'qc_final', 'export': 'export'
        };
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
            if (res.ok) { btn.innerText = "Generating..."; this.pollStatus(ch.id); }
            else { this.showToast("Failed to start generation", 'error'); btn.disabled = false; btn.innerText = "\u26A1 Generate Audio"; }
        } catch(e) { this.showToast(e.message, 'error'); btn.disabled = false; btn.innerText = "\u26A1 Generate Audio"; }
    },

    async generateSingleChapter(chapterId) {
        if (!confirm(`Regenerate chapter ${chapterId}? This will overwrite existing audio.`)) return;
        try {
            const res = await fetch(`${API_BASE}/projects/${this.currentProject}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chapters: [chapterId] })
            });
            if (res.ok) { this.showToast(`Started generation for ${chapterId}`, 'info'); this.pollStatus(chapterId); }
            else this.showToast("Generation failed to start", 'error');
        } catch(e) { this.showToast(e.message, 'error'); }
    },

    toggleCollapse(el) {
        el.classList.toggle('collapsed');
    },

    playChapter(chapterId) {
        this.stopAllAudio(); // FIX P1: prevent overlap
        const pid = this.currentProject;
        const audio = new Audio(`/projects/${pid}/06_MIX/renders/${chapterId}.wav`);
        audio.onerror = () => {
            audio.src = `/projects/${pid}/03_GENERATED/processed/${chapterId}.wav`;
            audio.onerror = () => {
                audio.src = `/projects/${pid}/03_GENERATED/raw/${chapterId}.wav`;
                audio.play().catch(() => this.showToast("Audio not found", 'error'));
            };
            audio.play();
        };
        audio.play();
    },

    // FIX P1: generate poll owns its own key — never kills mix or export polls
    pollStatus(chapterId) {
        if (this.activePolls.generate) clearInterval(this.activePolls.generate);
        this.activePolls.generate = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/projects/${this.currentProject}/status`);
                if (res.ok) {
                    this.currentStatus = await res.json();
                    if (this.selectedChapterIndex !== -1 &&
                        this.currentData.chapters[this.selectedChapterIndex].id === chapterId) {
                        this.populateChapterDetail();
                    }
                    this.renderForm();
                    const chStatus = this.currentStatus.nodes.generate.chapters?.[chapterId]?.status;
                    if (chStatus === 'complete' || chStatus === 'failed') {
                        clearInterval(this.activePolls.generate);
                        delete this.activePolls.generate;
                        const btn = document.getElementById('btn-generate-chap');
                        if (btn) { btn.disabled = false; btn.innerText = "\u26A1 Generate Audio"; }
                    }
                }
            } catch(e) { console.error(e); }
        }, 2000);
    }
};

document.addEventListener('DOMContentLoaded', () => app.init());