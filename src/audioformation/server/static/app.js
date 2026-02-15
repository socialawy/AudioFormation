
/**
 * AudioFormation Dashboard Logic.
 */

const API_BASE = '/api';

const app = {
    currentProject: null,
    currentData: null, // Full JSON for the editor

    init() {
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
                    Created: ${date}
                </div>
                <div class="meta">
                    <span>${p.chapters} Chs • ${p.languages.join(', ')}</span>
                    <span class="status-badge ${statusClass}">${p.pipeline_node}</span>
                </div>
            `;
            
            card.onclick = () => this.loadProject(p.id);
            grid.appendChild(card);
        });
    },

    async createProject() {
        const name = prompt("Enter new project ID (alphanumeric, no spaces):");
        if (!name) return;

        // Basic client-side validation
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
                this.fetchProjects(); // Refresh list
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
            const res = await fetch(`${API_BASE}/projects/${id}`);
            if (!res.ok) throw new Error('Failed to load project');
            const data = await res.json();
            
            this.currentProject = id;
            this.currentData = data;
            
            this.renderEditor();
            this.showEditor();
        } catch (e) {
            alert(e.message);
        }
    },

    renderEditor() {
        const d = this.currentData;
        document.getElementById('editor-project-id').innerText = d.id;

        // --- Configuration Tab ---
        // Generation
        const gen = d.generation || {};
        document.getElementById('conf-chunk-chars').value = gen.chunk_max_chars || 200;
        document.getElementById('conf-crossfade').value = gen.crossfade_ms || 120;
        document.getElementById('conf-strategy').value = gen.chunk_strategy || 'breath_group';
        document.getElementById('conf-fail-thresh').value = gen.fail_threshold_percent || 5;

        // Mix
        const mix = d.mix || {};
        document.getElementById('conf-lufs').value = mix.target_lufs || -16.0;
        document.getElementById('conf-vol').value = mix.master_volume || 0.9;

        // --- Chapters Tab ---
        const chList = document.getElementById('chapter-list');
        chList.innerHTML = '';
        (d.chapters || []).forEach(ch => {
            const row = document.createElement('div');
            row.className = 'list-item';
            row.innerHTML = `
                <span>${this.escapeHtml(ch.id)}</span>
                <span>${this.escapeHtml(ch.title || '')}</span>
                <span>${this.escapeHtml(ch.language || '')}</span>
                <span>${this.escapeHtml(ch.mode || 'single')}</span>
            `;
            chList.appendChild(row);
        });

        // --- JSON Tab ---
        document.getElementById('json-editor').value = JSON.stringify(d, null, 2);

        // Reset to config tab
        this.switchTab('config');
    },

    updateDataFromForm() {
        // Reads form values back into this.currentData
        if (!this.currentData.generation) this.currentData.generation = {};
        this.currentData.generation.chunk_max_chars = parseInt(document.getElementById('conf-chunk-chars').value);
        this.currentData.generation.crossfade_ms = parseInt(document.getElementById('conf-crossfade').value);
        this.currentData.generation.chunk_strategy = document.getElementById('conf-strategy').value;
        this.currentData.generation.fail_threshold_percent = parseFloat(document.getElementById('conf-fail-thresh').value);

        if (!this.currentData.mix) this.currentData.mix = {};
        this.currentData.mix.target_lufs = parseFloat(document.getElementById('conf-lufs').value);
        this.currentData.mix.master_volume = parseFloat(document.getElementById('conf-vol').value);
    },

    async saveProject() {
        // If on JSON tab, take value from textarea
        // Else, take values from form fields
        
        // Simple strategy: Update JSON from form fields if we are NOT on JSON tab.
        // If on JSON tab, parse textarea.
        const activeTab = document.querySelector('.nav-item.active').innerText;
        
        try {
            if (activeTab === 'Raw JSON') {
                const raw = document.getElementById('json-editor').value;
                this.currentData = JSON.parse(raw);
            } else {
                this.updateDataFromForm();
                // Update JSON text to match
                document.getElementById('json-editor').value = JSON.stringify(this.currentData, null, 2);
            }

            const res = await fetch(`${API_BASE}/projects/${this.currentProject}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.currentData)
            });

            if (res.ok) {
                const msg = await res.json();
                alert('Saved successfully!');
            } else {
                const err = await res.json();
                alert(`Error saving: ${err.detail}`);
            }
        } catch (e) {
            alert(`Invalid JSON or save error: ${e.message}`);
        }
    },

    // ──────────────────────────────────────────────
    // Navigation & UI
    // ──────────────────────────────────────────────

    showProjects() {
        document.getElementById('projects-view').classList.remove('hidden');
        document.getElementById('editor-view').classList.add('hidden');
        
        document.getElementById('nav-projects').classList.add('active');
        document.getElementById('nav-editor').classList.remove('active');
        document.getElementById('nav-editor').classList.add('disabled');
        
        this.fetchProjects(); // Refresh status
    },

    showEditor() {
        document.getElementById('projects-view').classList.add('hidden');
        document.getElementById('editor-view').classList.remove('hidden');
        
        document.getElementById('nav-projects').classList.remove('active');
        document.getElementById('nav-editor').classList.add('active');
        document.getElementById('nav-editor').classList.remove('disabled');
    },

    switchTab(tabName) {
        // Tabs: config, chapters, json
        ['config', 'chapters', 'json'].forEach(t => {
            const el = document.getElementById(`tab-${t}`);
            const btn = document.getElementById(`tab-btn-${t}`);
            
            if (t === tabName) {
                el.classList.remove('hidden');
                btn.classList.add('active');
            } else {
                el.classList.add('hidden');
                btn.classList.remove('active');
            }
        });

        // If switching TO json, update it from current form data first
        if (tabName === 'json') {
            this.updateDataFromForm();
            document.getElementById('json-editor').value = JSON.stringify(this.currentData, null, 2);
        }
        // If switching FROM json, parse it back to currentData
        // (This is tricky to detect easily without tracking previous tab. 
        // For simplicity, we assume user clicks save on JSON tab if they edit there, 
        // or we can re-parse if needed. Let's just re-parse to update forms if they changed JSON)
        if (tabName !== 'json') {
             try {
                 const raw = document.getElementById('json-editor').value;
                 this.currentData = JSON.parse(raw);
                 this.renderEditor(); // re-render inputs from JSON
             } catch(e) {
                 console.warn("Invalid JSON in editor, ignoring changes for form view.");
             }
        }
    },

    escapeHtml(unsafe) {
        return unsafe
             .replace(/&/g, "&amp;")
             .replace(/</g, "&lt;")
             .replace(/>/g, "&gt;")
             .replace(/"/g, "&quot;")
             .replace(/'/g, "&#039;");
    }
};

document.addEventListener('DOMContentLoaded', () => app.init());
