import { escape } from './ui.mjs';

const ruleNames = { deduplicate: 'Consolidate exact duplicates', prefer_current_approved: 'Prefer approved current versions', match_topic: 'Match the requested topic' };
const cases = ['original', 'fresh', 'unaffected', 'historical'];
const json = value => `<pre class="trace-json">${escape(JSON.stringify(value, null, 2))}</pre>`;

export class NoisePanel {
  constructor(root, context, render, url) {
    Object.assign(this, { root, context, render, url });
    this.key = ''; this.data = null; this.error = ''; this.busy = false;
    this.values = new Map(); this.revisions = new Map();
    this.loadedDecisions = new Map();
    root.addEventListener('input', event => {
      const form = event.target.closest('form[data-noise]');
      if (!form) return;
      const fields = new FormData(form), saved = {};
      for (const name of new Set(fields.keys())) saved[name] = fields.getAll(name);
      this.values.set(`${this.key}:${form.id}`, saved);
      if (!this.revisions.has(`${this.key}:${form.id}`)) this.revisions.set(`${this.key}:${form.id}`, this.data?.revision);
    });
    root.addEventListener('submit', event => {
      if (!event.target.matches('form[data-noise]')) return;
      event.preventDefault(); void this.submit(event.target);
    });
    root.addEventListener('click', event => {
      const button = event.target.closest('[data-noise-action]');
      if (!button || button.disabled) return;
      void this.action(button);
    });
  }

  sync() {
    const { origin, chat } = this.context(), key = `${origin}:${chat}`;
    if (key === this.key) return;
    this.key = key; this.data = null; this.error = ''; this.busy = false; this.pending = null;
    this.loadedDecisions.clear();
    this.base = `/api/chats/${encodeURIComponent(chat)}/noise`;
    try {
      const p = JSON.parse(sessionStorage.getItem(`epoch.noise.pending:${key}`) || 'null');
      if (p && p.path.startsWith(this.base + '/') && typeof p.payload?.client_request_id === 'string') this.pending = p;
    } catch { this.error = 'Submission recovery storage is unavailable. Exact retries remain available in this tab.'; }
  }

  async refresh(force = false) {
    this.sync();
    const { chat, api } = this.context(), key = this.key;
    if (!chat || (this.busy && !force)) return;
    try {
      const { body } = await api.call(this.base);
      if (key !== this.key) return;
      if (body.chat_id !== chat || !Array.isArray(body.records) || !Array.isArray(body.sources)) throw new Error('Noise workspace response could not be confirmed.');
      this.data = body; this.error = '';
      if (this.pending && body.records.some(r => r.id === this.pending.payload.client_request_id)) this.clearPending();
    } catch (error) { if (key === this.key) this.error = error.status === 404 ? 'Noise controls require the updated normal backend. Restart with --env-file .env serve.' : error.message; }
  }

  clearPending() {
    this.pending = null;
    try { sessionStorage.removeItem(`epoch.noise.pending:${this.key}`); } catch { /* In-memory acknowledgement is sufficient for this tab. */ }
  }

  async write(path, payload, formId) {
    this.sync();
    if (this.busy) return;
    if (this.pending && (path !== this.pending.path || payload !== this.pending.payload)) return;
    const key = this.key, api = this.context().api;
    this.pending ||= { path, payload: { client_request_id: crypto.randomUUID(), ...payload } };
    const request = this.pending;
    try { sessionStorage.setItem(`epoch.noise.pending:${key}`, JSON.stringify(request)); } catch { /* Preserve exact request in memory. */ }
    this.busy = true; this.error = ''; this.render();
    try {
      const { body } = await api.call(request.path, request.payload);
      if (key !== this.key) return;
      if (body.id !== request.payload.client_request_id || body.chat_id !== this.context().chat) throw new Error('Action acknowledgement could not be confirmed. Retry the exact action.');
      this.clearPending();
      if (formId) { this.values.delete(`${key}:${formId}`); this.revisions.delete(`${key}:${formId}`); }
      await this.refresh(true);
    } catch (error) {
      if (key !== this.key) return;
      if (error.status >= 400 && error.status < 500) this.clearPending();
      this.error = error.message;
    } finally { if (key === this.key) { this.busy = false; this.render(); } }
  }

  async submit(form) {
    if (this.pending || this.busy) return;
    const f = new FormData(form), action = form.dataset.noise;
    const val = name => String(f.get(name) || '').trim();
    const revision = this.revisions.get(`${this.key}:${form.id}`) ?? this.data.revision;
    const policy = form.dataset.policy;
    if (action === 'analyze') return this.write(this.base + '/analyses', { trace_id: this.context().trace, issue: val('issue') }, form.id);
    if (action === 'metadata') {
      const source = this.data.sources.find(s => s.id === form.dataset.source);
      return this.write(this.base + '/sources/metadata', { expected_revision: revision, source_id: source.id, sha256: source.sha256,
        labels: { family: val('family'), version: val('version'), status: val('status'), approved: f.has('approved'), protected: f.has('protected'),
          topics: val('topics').split(',').map(v => v.trim()).filter(Boolean) } }, form.id);
    }
    if (action === 'draft') return this.write(this.base + '/policies', { analysis_id: form.dataset.analysis, title: val('title'), rules: f.getAll('rules') }, form.id);
    if (action === 'preview') return this.write(`${this.base}/policies/${policy}/previews`, {
      case: val('case'), purpose: val('purpose'), version: val('version') || null, topic: val('topic') || null,
      required_ids: f.getAll('required_ids') }, form.id);
    if (action === 'validate') return this.write(`${this.base}/policies/${policy}/validations`, {
      preview_id: val('preview_id'), trace_id: val('trace_id'), passed: val('passed') === 'true', notes: val('notes') }, form.id);
  }

  async action(button) {
    if (button.dataset.noiseAction === 'decision') {
      const key = this.key, id = button.dataset.decision;
      button.disabled = true;
      try {
        const { body } = await this.context().api.call(`${this.base}/decisions/${encodeURIComponent(id)}`);
        if (key === this.key && body.id === id && body.chat_id === this.context().chat) this.loadedDecisions.set(id, body);
      } catch (error) { if (key === this.key) this.error = error.message; }
      if (key === this.key) this.render();
      return;
    }
    if (button.dataset.noiseAction === 'retry' && this.pending) return this.write(this.pending.path, this.pending.payload);
    if (button.dataset.noiseAction === 'refresh') { await this.refresh(); this.render(); return; }
    if (this.pending || this.busy) return;
    if (button.dataset.noiseAction === 'retry-analysis') {
      const analysis = this.records('analysis').find(a => a.id === button.dataset.analysis);
      if (!analysis || analysis.state !== 'failed' || analysis.request.trace_id !== this.context().trace || this.data.model_busy) return;
      return this.write(this.base + '/analyses', { trace_id: analysis.request.trace_id, issue: analysis.request.issue });
    }
    if (button.dataset.noiseAction === 'activate') {
      const policy = button.dataset.policy;
      const validations = cases.map(c => this.records('validation').find(v => v.policy_id === policy && v.case === c && v.passed));
      if (validations.some(v => !v)) return;
      return this.write(`${this.base}/policies/${policy}/activate`, { expected_revision: this.data.revision, validation_ids: validations.map(v => v.id) });
    }
    if (button.dataset.noiseAction === 'rollback') return this.write(this.base + '/rollback', { expected_revision: this.data.revision, activation_id: button.dataset.activation });
  }

  records(kind) { return (this.data?.records || []).filter(r => r.kind === kind); }
  latest() { return this.records('analysis').find(r => r.request.trace_id === this.context().trace); }
  value(form, name, fallback = '') { return this.values.get(`${this.key}:${form}`)?.[name]?.[0] ?? fallback; }
  checked(form, name, value, fallback = false) {
    const saved = this.values.get(`${this.key}:${form}`);
    return saved ? (saved[name] || []).includes(value) : fallback;
  }
  input(form, name, label, fallback = '', type = 'text') {
    const value = this.value(form, name, fallback), id = `${form}-${name}`;
    return `<label class="trace-field" for="${escape(id)}"><span>${label}</span>${type === 'textarea' ? `<textarea id="${escape(id)}" name="${name}" rows="3" maxlength="2000" required>${escape(value)}</textarea>` : `<input id="${escape(id)}" name="${name}" value="${escape(value)}" maxlength="${name === 'trace_id' ? 32 : 120}" ${['title', 'trace_id'].includes(name) ? 'required' : ''}>`}</label>`;
  }
  select(form, name, label, options, fallback) {
    const value = this.value(form, name, fallback);
    return `<label class="trace-field"><span>${label}</span><select name="${name}">${options.map(([v, text]) => `<option value="${escape(v)}" ${v === value ? 'selected' : ''}>${escape(text)}</option>`).join('')}</select></label>`;
  }
  toggle(form, name, value, label, fallback = false) {
    return `<label class="noise-check"><input type="checkbox" name="${name}" value="${escape(value)}" ${this.checked(form, name, value, fallback) ? 'checked' : ''}>${escape(label)}</label>`;
  }
  evidence() {
    this.sync();
    const analysis = this.latest();
    if (!analysis?.answer) return '';
    const items = analysis.snapshot.evidence.filter(e => analysis.answer.relevant_evidence_ids.includes(e.id));
    return `<section class="noise-focus"><h3>Evidence relevant to the reported issue</h3><p class="trace-muted">Model-selected evidence; other steps remain available below.</p>${items.map(e => `<a data-route class="trace-citation" href="${escape(this.url({ span: e.span_id }) + '#trace-selected-span')}">${escape(e.id)} · ${escape(e.name)}</a>`).join('')}</section>`;
  }

  metadataView() {
    return `<details class="noise-sources" data-key="noise-sources"><summary>Source versions and approvals · ${this.data.sources.length} sources</summary>
      <p class="trace-muted">These are your annotations, not model guesses. Original files stay unchanged. Editing metadata deactivates the current policy until reviewed again. Matching source hashes can reuse annotations in the same project and environment.</p>
      ${this.data.sources.map(source => {
        const fid = `noise-source-${source.id}`, label = this.data.labels[source.id] || {};
        return `<details data-key="noise-source-${escape(source.id)}"><summary>${escape(source.name)} · ${escape(label.status || 'unknown')}</summary>
          <form id="${escape(fid)}" data-noise="metadata" data-source="${escape(source.id)}"><fieldset ${this.busy || this.pending || this.data.busy ? 'disabled' : ''}>
          <div class="noise-fields">${this.input(fid, 'family', 'Version family', label.family)}${this.input(fid, 'version', 'Version', label.version)}${this.select(fid, 'status', 'Status', ['unknown','current','superseded'].map(v => [v,v]), label.status || 'unknown')}${this.input(fid, 'topics', 'Topics (comma separated)', (label.topics || []).join(', '))}</div>
          ${this.toggle(fid, 'approved', 'on', 'Approved by me', !!label.approved)}${this.toggle(fid, 'protected', 'on', 'Always retain this source', !!label.protected)}<button>Save source metadata</button></fieldset></form>
          <small>Source ${escape(source.id)} · ${escape(source.sha256)}</small></details>`;
      }).join('')}</details>`;
  }

  policyView(policy) {
    const fid = `noise-preview-${policy.id}`, vid = `noise-validation-${policy.id}`;
    const previews = this.records('preview').filter(p => p.policy_id === policy.id);
    const validations = this.records('validation').filter(v => v.policy_id === policy.id);
    const ready = cases.every(c => validations.some(v => v.case === c && v.passed));
    const active = this.data.active_id === policy.id;
    const activation = this.records('activation').find(a => a.policy_id === policy.id && a.revision === this.data.revision);
    return `<details class="noise-policy" data-key="noise-policy-${policy.id}"><summary>${escape(policy.title)} · ${active ? 'Active · manual acceptance recorded' : 'Inactive policy'}</summary>
      <p>${policy.rules.map(r => escape(ruleNames[r])).join(' · ')}</p><small>Policy ${escape(policy.id)} · project ${escape(policy.project)}</small>
      <form id="${fid}" data-noise="preview" data-policy="${policy.id}"><fieldset ${this.busy || this.pending || this.data.busy ? 'disabled' : ''}><legend>Preview a case before trial</legend>
      <div class="noise-fields">${this.select(fid,'case','Case',cases.map(v => [v,v]),'original')}${this.select(fid,'purpose','Request purpose',['current','historical','all'].filter(v => this.data.environment === 'pdf_workshop' || v !== 'all').map(v => [v,v]),'current')}${this.input(fid,'version','Explicit version (optional)')}${this.data.environment === 'pdf_workshop' ? this.input(fid,'topic','Requested topic (optional)') : ''}</div>
      <p>Select the sources this case must retain:</p><div class="noise-required">${this.data.sources.map(s => this.toggle(fid,'required_ids',s.id,s.name)).join('')}</div><button>Create preview</button></fieldset></form>
      ${previews.slice(0,8).map(p => `<details data-key="noise-preview-result-${p.id}"><summary>${escape(p.request.case)} preview · ${p.selection.retained_ids.length}/${p.snapshot.sources.length} sources retained · ${p.required_retained ? 'required sources retained' : 'required sources would be omitted'}</summary>
        <table><thead><tr><th>Source</th><th>Selection</th><th>Reason</th></tr></thead><tbody>${p.selection.decisions.map(d => `<tr><td>${escape(p.snapshot.sources.find(s => s.id === d.source_id)?.name || d.source_id)}</td><td>${d.retained ? 'Retain' : 'Exclude from this retrieval'}</td><td>${escape(d.reason.replaceAll('_',' '))}</td></tr>`).join('')}</tbody></table>
        ${p.selection.warnings.map(w => `<p class="trace-notice">${escape(w)}</p>`).join('')}
        <p>Trial query: ${escape(JSON.stringify(p.query))}. Ask Hermes to retrieve documents using this purpose and topic. A preview alone does not run Hermes.</p>
        ${p.required_retained ? `<a class="trace-citation" href="/chat?chat=${encodeURIComponent(this.context().chat)}&context_preview=${p.id}">Use this preview in my next message</a>` : ''}<small>Preview ${p.id}</small></details>`).join('')}
      ${previews.length ? `<form id="${vid}" data-noise="validate" data-policy="${policy.id}"><fieldset ${this.busy || this.pending || this.data.busy ? 'disabled' : ''}><legend>Record your trial assessment</legend>
        ${this.select(vid,'preview_id','Preview used for the trial',previews.map(p => [p.id,`${p.request.case} · ${p.id}`]),previews[0].id)}${this.input(vid,'trace_id','Trace ID from the completed trial')}${this.select(vid,'passed','Your assessment',[['false','Failed / incomplete'],['true','Passed']], 'false')}${this.input(vid,'notes','Observed result and retained information','', 'textarea')}<button>Record assessment</button></fieldset></form>` : ''}
      <ul>${cases.map(c => `<li>${c}: ${validations.some(v => v.case === c && v.passed) ? 'passing trial recorded' : 'pending'}</li>`).join('')}</ul>
      <button type="button" data-noise-action="activate" data-policy="${policy.id}" ${active || !ready || this.busy || this.pending || this.data.busy ? 'disabled' : ''}>Activate reviewed policy</button>
      ${active && activation ? `<button type="button" data-noise-action="rollback" data-activation="${activation.id}" ${this.busy || this.pending || this.data.busy ? 'disabled' : ''}>Roll back this activation</button>` : ''}
      <details data-key="noise-validation-history-${policy.id}"><summary>Recorded assessments and provenance</summary>${json(validations)}</details></details>`;
  }

  nextStepView(answer) {
    if (answer.outcome === 'tool_defect') {
      const pdf = this.data.environment === 'pdf_workshop';
      const href = `/debugger?chat=${encodeURIComponent(this.context().chat)}`;
      return `<p class="trace-notice">The model identified a possible tool defect. Review the cited evidence; context filtering does not repair a faulty tool.</p><a class="trace-citation" href="${escape(href)}">${pdf ? 'Open PDF debugger' : 'Open conversation debugger'}</a><p class="trace-muted">Opens this conversation’s saved evidence. Review the available tool repair options there. Repair requires a separate explicit action.</p>`;
    }
    if (answer.outcome === 'insufficient_evidence') return '<p class="trace-notice">The captured evidence is insufficient to propose a fix. Review the missing evidence above and capture the missing steps before investigating again.</p>';
    if (answer.outcome === 'no_issue') return '<p class="trace-notice">No issue was established from this evidence. This does not prove the task succeeded.</p>';
    return '<p class="trace-notice">No supported context filter was proposed. Review the findings and source metadata before deciding on a change.</p>';
  }

  view() {
    this.sync();
    const { chat, trace } = this.context();
    if (!chat) return '<p class="trace-notice">Open traces from a conversation to investigate noise and manage its context policy.</p>';
    const analysis = this.latest(), fid = `noise-analysis-${trace}`;
    return `<section class="trace-questions noise-panel" id="noise-workspace"><header class="trace-question-heading"><div><p class="trace-eyebrow">CONTEXT QUALITY</p><h2>Investigate noise and prevent recurrence</h2></div><button type="button" data-noise-action="refresh">Refresh</button></header>
      <p class="trace-muted">Find relevant evidence, preview a scoped filter, then record trial results before activation. Original traces and sources remain available.</p>
      ${this.error ? `<p class="trace-question-error" role="alert">${escape(this.error)}</p>` : ''}${this.data?.warning ? `<p class="trace-question-error" role="alert">${escape(this.data.warning)}</p>` : ''}${this.pending ? `<p class="trace-notice">Submission acknowledgement pending. <button type="button" data-noise-action="retry" ${this.busy ? 'disabled' : ''}>Confirm or retry exact action</button></p>` : ''}
      ${!this.data ? '<p>Loading noise workspace…</p>' : `<p>Project ${escape(this.data.project)} · revision ${this.data.revision} · ${this.data.active_id ? 'A context policy is active' : 'No active context policy'}</p>
      ${trace ? `<form id="${fid}" data-noise="analyze"><fieldset ${this.busy || this.pending || this.data.model_busy ? 'disabled' : ''}>${this.input(fid,'issue','What went wrong?','', 'textarea')}<button>Investigate with local model</button><small>Uses ${escape(this.data.model)} through local Ollama.</small></fieldset></form>` : '<p>Select a trace to report an issue.</p>'}
      ${analysis ? `<article class="trace-answer"><h3>${escape(analysis.request.issue)}</h3>${analysis.state === 'running' ? '<p role="status">Local model is investigating…</p>' : analysis.error ? `<p class="trace-question-error" role="alert">${escape(analysis.error)}</p>${analysis.error_code ? `<p class="trace-muted">Error code: ${escape(analysis.error_code)}</p>` : ''}${analysis.error_details ? `<details data-key="noise-failure-${escape(analysis.id)}"><summary>Failure details</summary>${json(analysis.error_details)}</details>` : ''}<button type="button" data-noise-action="retry-analysis" data-analysis="${escape(analysis.id)}" ${this.busy || this.pending || this.data.model_busy ? 'disabled' : ''}>Try investigation again</button><p class="trace-muted">Runs a new local analysis of this trace with the same issue. The failed attempt stays in history.</p>` : `<p>${escape(analysis.answer.summary)}</p><p>Finding: ${escape(analysis.answer.outcome.replaceAll('_',' '))}. Model conclusions require review.</p>
      ${analysis.answer.findings.map(f => `<p><strong>${escape(f.kind)} · ${escape(f.confidence)} confidence</strong> ${escape(f.explanation)}</p><div>${f.evidence_ids.map(id => { const e = analysis.snapshot.evidence.find(v => v.id === id); return e ? `<a data-route class="trace-citation" href="${escape(this.url({span:e.span_id}) + '#trace-selected-span')}">${escape(id)} · ${escape(e.name)}</a>` : ''; }).join('')}</div>`).join('')}
      ${[...analysis.answer.missing_evidence, ...analysis.snapshot.warnings].map(w => `<p class="trace-notice">${escape(w)}</p>`).join('')}
      ${analysis.answer.outcome === 'context_noise' && analysis.answer.rules.length ? `<form id="noise-draft-${analysis.id}" data-noise="draft" data-analysis="${analysis.id}"><fieldset ${this.busy || this.pending ? 'disabled' : ''}>${this.input(`noise-draft-${analysis.id}`,'title','Policy name')}${analysis.answer.rules.map(r => this.toggle(`noise-draft-${analysis.id}`,'rules',r,ruleNames[r],true)).join('')}<button>Save selected rules as draft</button></fieldset></form>` : this.nextStepView(analysis.answer)}`}</article>` : ''}
      ${this.metadataView()}${this.records('policy').slice(0,10).map(p => this.policyView(p)).join('')}
      <details data-key="noise-decisions"><summary>Actual context delivered · recent decisions</summary>${this.data.decisions.length ? this.data.decisions.map(d => `<details data-key="noise-decision-${d.id}"><summary>${escape(d.tool)} · ${escape(d.created_at)} · ${escape(d.policy_id || 'no policy')}</summary>${this.loadedDecisions.has(d.id) ? json(this.loadedDecisions.get(d.id)) : `<button type="button" data-noise-action="decision" data-decision="${d.id}">Load supplied context and selection</button>${json(d)}`}</details>`).join('') : '<p>No recorded context selection yet. New document reads create evidence here.</p>'}</details>
      <details data-key="noise-history"><summary>Recent investigation and policy history (up to ${this.data.history_limit})</summary>${this.data.records.map(r => `<details data-key="noise-record-${r.id}"><summary>${escape(r.kind)} · ${escape(r.title || r.request.issue || r.created_at)}</summary>${json(r)}</details>`).join('')}</details>`}
    </section>`;
  }
}
