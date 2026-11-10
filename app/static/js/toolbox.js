const state = { designs: [], presentations: [], currentDesign: null, currentPresentation: null };

async function api(url, opts = {}) {
  const res = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...opts });
  if (!res.ok) {
    let msg = 'Request failed';
    try { const d = await res.json(); msg = d.error || JSON.stringify(d); } catch {}
    throw new Error(msg);
  }
  const ct = res.headers.get('content-type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 2500);
}

function qs(id) { return document.getElementById(id); }

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.toggle('active', p.id === 'tab-' + name));
}

document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));

// ----- Designs -----
async function loadDesigns() {
  state.designs = await api('/api/designs');
  renderDesignList();
  fillDesignSelect();
}

function renderDesignList() {
  const ul = qs('design-list'); ul.innerHTML = '';
  state.designs.forEach(d => {
    const li = document.createElement('li');
    li.innerHTML = `<div><strong>${esc(d.name)}</strong></div><div class="meta">${esc(d.description || '')}</div>`;
    if (state.currentDesign && state.currentDesign.id === d.id) li.classList.add('active');
    li.onclick = () => openDesign(d.id);
    ul.appendChild(li);
  });
}

function esc(s) { return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

function fillDesignSelect() {
  const opts = '<option value="">(No design)</option>' + state.designs.map(d => `<option value="${d.id}">${esc(d.name)}</option>`).join('');
  ['pres-design','ai-pres-design','import-pres-design'].forEach(id => {
    const sel = qs(id); if (!sel) return;
    const cur = sel.value;
    sel.innerHTML = opts;
    if (cur) sel.value = cur;
  });
  if (state.currentPresentation && qs('pres-design')) qs('pres-design').value = state.currentPresentation.design_id || '';
}

function openDesign(id) {
  const d = state.designs.find(x => x.id === id);
  if (!d) return;
  state.currentDesign = d;
  qs('design-empty').classList.add('hidden');
  qs('design-form').classList.remove('hidden');
  qs('design-id').value = d.id;
  qs('design-name').value = d.name || '';
  qs('design-description').value = d.description || '';
  const s = d.settings || {};
  qs('design-bg').value = s.background_color || '#0f172a';
  qs('design-text').value = s.text_color || '#e2e8f0';
  qs('design-heading').value = s.heading_color || '#f8fafc';
  qs('design-accent').value = s.accent_color || '#38bdf8';
  qs('design-font').value = s.font_family || 'Segoe UI, Arial, sans-serif';
  qs('design-heading-font').value = s.heading_font_family || 'Segoe UI, Arial, sans-serif';
  qs('design-align').value = s.slide_align || 'left';
  qs('design-title-align').value = s.title_align || 'center';
  qs('design-numbers').checked = s.show_slide_numbers !== false;
  qs('design-custom-css').value = s.custom_css || '';
  renderDesignList();
}

function newDesign() {
  state.currentDesign = null;
  qs('design-empty').classList.add('hidden');
  qs('design-form').classList.remove('hidden');
  qs('design-id').value = '';
  qs('design-name').value = 'New Design';
  qs('design-description').value = '';
  qs('design-bg').value = '#0f172a';
  qs('design-text').value = '#e2e8f0';
  qs('design-heading').value = '#f8fafc';
  qs('design-accent').value = '#38bdf8';
  qs('design-font').value = 'Segoe UI, Arial, sans-serif';
  qs('design-heading-font').value = 'Segoe UI, Arial, sans-serif';
  qs('design-align').value = 'left';
  qs('design-title-align').value = 'center';
  qs('design-numbers').checked = true;
  qs('design-custom-css').value = '';
}

qs('new-design').onclick = newDesign;

qs('import-design').onclick = () => qs('import-design-file').click();
qs('import-design-file').addEventListener('change', async (e) => {
  const file = e.target.files && e.target.files[0];
  if (!file) return;
  try {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch('/api/designs/import', { method: 'POST', body: fd });
    if (!res.ok) {
      let msg = 'Import failed';
      try { const d = await res.json(); msg = d.description || d.error || msg; } catch {}
      throw new Error(msg);
    }
    const saved = await res.json();
    toast('Design imported');
    await loadDesigns();
    openDesign(saved.id);
  } catch (err) {
    toast(err.message || 'Import failed');
  } finally {
    e.target.value = '';
  }
});

qs('design-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = qs('design-id').value;
  const payload = {
    name: qs('design-name').value,
    description: qs('design-description').value,
    settings: {
      background_color: qs('design-bg').value,
      text_color: qs('design-text').value,
      heading_color: qs('design-heading').value,
      accent_color: qs('design-accent').value,
      font_family: qs('design-font').value,
      heading_font_family: qs('design-heading-font').value,
      slide_align: qs('design-align').value,
      title_align: qs('design-title-align').value,
      show_slide_numbers: qs('design-numbers').checked,
      custom_css: qs('design-custom-css').value,
    }
  };
  const saved = id ? await api('/api/designs/' + id, { method: 'PUT', body: JSON.stringify(payload) })
                   : await api('/api/designs', { method: 'POST', body: JSON.stringify(payload) });
  toast('Design saved');
  await loadDesigns();
  openDesign(saved.id);
});

qs('delete-design').onclick = async () => {
  const id = qs('design-id').value; if (!id) return;
  if (!confirm('Delete this design? Presentations using it will have no design selected.')) return;
  await api('/api/designs/' + id, { method: 'DELETE' });
  state.currentDesign = null;
  qs('design-form').classList.add('hidden');
  qs('design-empty').classList.remove('hidden');
  await loadDesigns();
  await loadPresentations();
  toast('Design deleted');
};

// ----- Presentations -----
async function loadPresentations() {
  state.presentations = await api('/api/presentations');
  renderPresentationList();
}

function renderPresentationList() {
  const ul = qs('presentation-list'); ul.innerHTML = '';
  state.presentations.forEach(p => {
    const li = document.createElement('li');
    const d = state.designs.find(x => x.id === p.design_id);
    li.innerHTML = `<div><strong>${esc(p.name)}</strong></div><div class="meta">${(p.slides||[]).length} slide(s) · ${esc(d ? d.name : 'No design')}</div>`;
    if (state.currentPresentation && state.currentPresentation.id === p.id) li.classList.add('active');
    li.onclick = () => openPresentation(p.id);
    ul.appendChild(li);
  });
}

function slideCard(slide, idx, total) {
  const wrap = document.createElement('div');
  wrap.className = 'slide-card';
  wrap.dataset.idx = idx;
  const bullets = (slide.bullets || []).join('\n');
  wrap.innerHTML = `
    <div class="slide-card-header">
      <span>Slide ${idx + 1}</span>
      <div class="btns">
        <button type="button" class="secondary move-up" ${idx===0?'disabled':''}>↑</button>
        <button type="button" class="secondary move-down" ${idx===total-1?'disabled':''}>↓</button>
        <button type="button" class="danger remove-slide">Remove</button>
      </div>
    </div>
    <div class="row two">
      <label>Title <input class="s-title" value="${escAttr(slide.title||'')}" /></label>
      <label>Layout
        <select class="s-layout">
          <option value="title" ${slide.layout==='title'?'selected':''}>Title</option>
          <option value="default" ${(!slide.layout||slide.layout==='default')?'selected':''}>Default</option>
          <option value="section" ${slide.layout==='section'?'selected':''}>Section</option>
        </select>
      </label>
    </div>
    <label>Content (Markdown supported) <textarea class="s-content" rows="4">${esc(slide.content||'')}</textarea></label>
    <label>Bullets (one per line) <textarea class="s-bullets" rows="3">${esc(bullets)}</textarea></label>
    <label>Notes <textarea class="s-notes" rows="2">${esc(slide.notes||'')}</textarea></label>`;
  return wrap;
}
function escAttr(s){ return String(s??'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function renderSlidesEditor() {
  const c = qs('slides-editor'); c.innerHTML = '';
  const slides = (state.currentPresentation && state.currentPresentation.slides) || [];
  slides.forEach((s, i) => c.appendChild(slideCard(s, i, slides.length)));
  c.querySelectorAll('.remove-slide').forEach(btn => btn.onclick = () => {
    const i = +btn.closest('.slide-card').dataset.idx;
    state.currentPresentation.slides.splice(i,1);
    if (!state.currentPresentation.slides.length) state.currentPresentation.slides.push({title:'New Slide',content:'',bullets:[],layout:'title'});
    renderSlidesEditor();
  });
  c.querySelectorAll('.move-up').forEach(btn => btn.onclick = () => {
    const i = +btn.closest('.slide-card').dataset.idx;
    if (i>0){ const a=state.currentPresentation.slides; [a[i-1],a[i]]=[a[i],a[i-1]]; renderSlidesEditor(); }
  });
  c.querySelectorAll('.move-down').forEach(btn => btn.onclick = () => {
    const i = +btn.closest('.slide-card').dataset.idx; const a=state.currentPresentation.slides;
    if (i<a.length-1){ [a[i+1],a[i]]=[a[i],a[i+1]]; renderSlidesEditor(); }
  });
}

function collectSlidesFromEditor() {
  const cards = Array.from(document.querySelectorAll('#slides-editor .slide-card'));
  return cards.map(card => ({
    title: card.querySelector('.s-title').value,
    layout: card.querySelector('.s-layout').value,
    content: card.querySelector('.s-content').value,
    bullets: card.querySelector('.s-bullets').value.split('\n').map(s=>s.trim()).filter(Boolean),
    notes: card.querySelector('.s-notes').value,
  }));
}

function openPresentation(id) {
  const p = state.presentations.find(x => x.id === id);
  if (!p) return;
  state.currentPresentation = JSON.parse(JSON.stringify(p));
  qs('presentation-empty').classList.add('hidden');
  qs('presentation-form').classList.remove('hidden');
  qs('pres-id').value = p.id;
  qs('pres-name').value = p.name || '';
  fillDesignSelect();
  qs('pres-design').value = p.design_id || '';
  renderSlidesEditor();
  renderPresentationList();
}

function newPresentation() {
  state.currentPresentation = { name: 'New Presentation', design_id: (state.designs[0]||{}).id || '', slides: [{title:'Title Slide',content:'',bullets:[],layout:'title'}] };
  qs('presentation-empty').classList.add('hidden');
  qs('presentation-form').classList.remove('hidden');
  qs('pres-id').value = '';
  qs('pres-name').value = 'New Presentation';
  fillDesignSelect();
  qs('pres-design').value = state.currentPresentation.design_id;
  renderSlidesEditor();
}

qs('new-presentation').onclick = newPresentation;
qs('add-slide').onclick = () => {
  if (!state.currentPresentation) return;
  state.currentPresentation.slides = collectSlidesFromEditor();
  state.currentPresentation.slides.push({title:'New Slide', content:'', bullets:[], layout:'default'});
  renderSlidesEditor();
};

qs('presentation-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const id = qs('pres-id').value;
  const payload = {
    name: qs('pres-name').value,
    design_id: qs('pres-design').value,
    slides: collectSlidesFromEditor(),
  };
  const saved = id ? await api('/api/presentations/' + id, { method: 'PUT', body: JSON.stringify(payload) })
                   : await api('/api/presentations', { method: 'POST', body: JSON.stringify(payload) });
  toast('Presentation saved');
  await loadPresentations();
  openPresentation(saved.id);
});

qs('delete-pres').onclick = async () => {
  const id = qs('pres-id').value; if (!id) return;
  if (!confirm('Delete this presentation?')) return;
  await api('/api/presentations/' + id, { method: 'DELETE' });
  state.currentPresentation = null;
  qs('presentation-form').classList.add('hidden');
  qs('presentation-empty').classList.remove('hidden');
  await loadPresentations();
  toast('Presentation deleted');
};

qs('preview-pres').onclick = async () => {
  const id = qs('pres-id').value;
  if (!id) { toast('Save the presentation first to preview.'); return; }
  // auto-save current edits before preview
  await qs('presentation-form').requestSubmit();
  window.open('/preview/' + qs('pres-id').value, '_blank');
};

qs('download-pres').onclick = async () => {
  const id = qs('pres-id').value;
  if (!id) { toast('Save the presentation first to download.'); return; }
  await qs('presentation-form').requestSubmit();
  window.location = '/api/presentations/' + qs('pres-id').value + '/download';
};

// ----- AI Settings & Generation -----
function currentAIConfig() {
  return {
    provider: qs('ai-provider') ? qs('ai-provider').value : 'openai_compatible',
    base_url: qs('ai-base-url') ? qs('ai-base-url').value.trim() : '',
    api_key: qs('ai-api-key') ? qs('ai-api-key').value : '',
    model: qs('ai-model') ? qs('ai-model').value.trim() : '',
    temperature: parseFloat(qs('ai-temperature') ? (qs('ai-temperature').value || '0.7') : '0.7')
  };
}

function renderModelList(models) {
  const c = qs('ai-models-list'); if (!c) return;
  c.innerHTML = '';
  const current = (qs('ai-model') ? qs('ai-model').value.trim() : '');
  if (!models || !models.length) {
    c.innerHTML = '<span class="hint">Keine Modelle gefunden.</span>';
    return;
  }
  models.forEach(m => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'model-item' + (m === current ? ' active' : '');
    b.textContent = m;
    b.title = m;
    b.onclick = () => {
      qs('ai-model').value = m;
      c.querySelectorAll('.model-item').forEach(x => x.classList.toggle('active', x === b));
    };
    c.appendChild(b);
  });
}

async function loadSettings() {
  try {
    const s = await api('/api/settings');
    const ai = (s && s.ai) || {};
    if (qs('ai-provider')) qs('ai-provider').value = ai.provider || 'openai_compatible';
    if (qs('ai-base-url')) qs('ai-base-url').value = ai.base_url || '';
    if (qs('ai-api-key')) qs('ai-api-key').value = ai.api_key || '';
    if (qs('ai-model')) qs('ai-model').value = ai.model || '';
    if (qs('ai-temperature')) qs('ai-temperature').value = (ai.temperature ?? 0.7);
  } catch (e) { /* ignore */ }
}

if (qs('ai-settings-form')) {
  qs('ai-settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = { ai: currentAIConfig() };
    await api('/api/settings', { method: 'PUT', body: JSON.stringify(payload) });
    toast('AI settings saved');
  });
}

if (qs('ai-load-models')) {
  qs('ai-load-models').onclick = async () => {
    const btn = qs('ai-load-models');
    const status = qs('ai-models-status');
    btn.disabled = true; btn.textContent = 'Lade...';
    if (status) status.textContent = '';
    try {
      const res = await api('/api/ai/models', { method: 'POST', body: JSON.stringify({ ai: currentAIConfig() }) });
      const models = res.models || [];
      renderModelList(models);
      if (status) status.textContent = models.length ? `${models.length} Modell(e) gefunden` : 'Keine Modelle gefunden';
      toast(models.length ? 'Modelle geladen' : 'Keine Modelle gefunden');
    } catch (e) {
      renderModelList([]);
      if (status) status.textContent = 'Fehler beim Laden';
      toast(e.message || 'Modelle konnten nicht geladen werden');
    } finally {
      btn.disabled = false; btn.textContent = 'Modelle laden';
    }
  };
}

if (qs('ai-new-design')) {
  qs('ai-new-design').onclick = () => qs('ai-design-panel').classList.toggle('hidden');
  qs('ai-design-cancel').onclick = () => qs('ai-design-panel').classList.add('hidden');
  qs('ai-design-generate').onclick = async () => {
    const prompt = qs('ai-design-prompt').value.trim();
    if (!prompt) { toast('Please enter a prompt'); return; }
    const btn = qs('ai-design-generate');
    btn.disabled = true; btn.textContent = 'Generating...';
    try {
      const res = await api('/api/ai/generate-design', { method: 'POST', body: JSON.stringify({ prompt, save: true }) });
      toast('Design generated');
      qs('ai-design-panel').classList.add('hidden');
      qs('ai-design-prompt').value = '';
      await loadDesigns();
      if (res.saved) openDesign(res.saved.id);
    } catch (e) {
      toast(e.message || 'Generation failed');
    } finally {
      btn.disabled = false; btn.textContent = 'Generate & Save';
    }
  };
  if (qs('ai-design-from-file')) {
    qs('ai-design-from-file').onclick = async () => {
      const fileInput = qs('ai-design-file');
      const file = fileInput && fileInput.files && fileInput.files[0];
      if (!file) { toast('Bitte eine Datei auswählen (.pptx, .pdf, .html)'); return; }
      const btn = qs('ai-design-from-file');
      btn.disabled = true; btn.textContent = 'Analysiere...';
      try {
        const fd = new FormData();
        fd.append('file', file);
        fd.append('prompt', qs('ai-design-prompt').value || '');
        fd.append('save', 'true');
        const res = await fetch('/api/ai/generate-design-from-file', { method: 'POST', body: fd });
        let data = {};
        try { data = await res.json(); } catch {}
        if (!res.ok) throw new Error(data.error || data.description || 'Generierung fehlgeschlagen');
        if (data.source === 'heuristic') {
          toast('Design aus Datei extrahiert (ohne AI)');
          if (data.ai_warning) console.warn('AI fallback:', data.ai_warning);
        } else {
          toast('Design aus Datei generiert');
        }
        qs('ai-design-panel').classList.add('hidden');
        fileInput.value = '';
        await loadDesigns();
        if (data.saved) openDesign(data.saved.id);
      } catch (e) {
        toast(e.message || 'Generierung fehlgeschlagen');
      } finally {
        btn.disabled = false; btn.textContent = 'Design aus Datei generieren & speichern';
      }
    };
  }
}

if (qs('ai-new-presentation')) {
  qs('ai-new-presentation').onclick = () => qs('ai-pres-panel').classList.toggle('hidden');
  qs('ai-pres-cancel').onclick = () => qs('ai-pres-panel').classList.add('hidden');
  qs('ai-pres-generate').onclick = async () => {
    const prompt = qs('ai-pres-prompt').value.trim();
    if (!prompt) { toast('Please enter a prompt'); return; }
    const count = parseInt(qs('ai-pres-count').value, 10);
    const payload = { prompt, save: true, design_id: qs('ai-pres-design').value || '' };
    if (!isNaN(count) && count > 0) payload.slide_count = count;
    const btn = qs('ai-pres-generate');
    btn.disabled = true; btn.textContent = 'Generating...';
    try {
      const res = await api('/api/ai/generate-presentation', { method: 'POST', body: JSON.stringify(payload) });
      toast('Presentation generated');
      qs('ai-pres-panel').classList.add('hidden');
      qs('ai-pres-prompt').value = '';
      await loadPresentations();
      if (res.saved) openPresentation(res.saved.id);
    } catch (e) {
      toast(e.message || 'Generation failed');
    } finally {
      btn.disabled = false; btn.textContent = 'Generate & Save';
    }
  };
}

if (qs('import-pres-file-btn')) {
  qs('import-pres-file-btn').onclick = () => qs('import-pres-panel').classList.toggle('hidden');
  qs('import-pres-cancel').onclick = () => qs('import-pres-panel').classList.add('hidden');
  qs('import-pres-run').onclick = async () => {
    const fileInput = qs('import-pres-file');
    const file = fileInput && fileInput.files && fileInput.files[0];
    if (!file) { toast('Bitte eine Datei auswählen (.pptx, .pdf, .html)'); return; }
    const btn = qs('import-pres-run');
    btn.disabled = true; btn.textContent = 'Importiere...';
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('name', qs('import-pres-name').value || '');
      fd.append('design_id', qs('import-pres-design').value || '');
      const res = await fetch('/api/presentations/import-file', { method: 'POST', body: fd });
      let data = {};
      try { data = await res.json(); } catch {}
      if (!res.ok) throw new Error(data.error || data.description || 'Import fehlgeschlagen');
      toast(`Präsentation importiert (${data.slides_count || 0} Folien)`);
      if (data.ai_warning) console.warn('AI warning:', data.ai_warning);
      qs('import-pres-panel').classList.add('hidden');
      fileInput.value = '';
      qs('import-pres-name').value = '';
      await loadPresentations();
      if (data.saved) openPresentation(data.saved.id);
    } catch (e) {
      toast(e.message || 'Import fehlgeschlagen');
    } finally {
      btn.disabled = false; btn.textContent = 'Importieren & Speichern';
    }
  };
}

const quitBtn = qs('quit-app');
if (quitBtn) {
  quitBtn.onclick = async () => {
    if (!confirm('Tool wirklich beenden?')) return;
    try { await api('/api/shutdown', { method: 'POST' }); } catch (e) { /* server may exit before response */ }
    toast('Tool wird beendet...');
    setTimeout(() => {
      try { window.open('', '_self'); window.close(); } catch (e) {}
      try { window.close(); } catch (e) {}
      // fallback message if browser blocks closing
      document.body.innerHTML = '<div style="font-family:Segoe UI,Arial,sans-serif;padding:40px;color:#e5edf8;background:#0b1020;min-height:100vh"><h2>Tool beendet</h2><p>Der Server wurde gestoppt. Sie können dieses Browserfenster jetzt schließen.</p></div>';
    }, 400);
  };
}

(async function init(){
  await loadDesigns();
  await loadPresentations();
  await loadSettings();
})();
