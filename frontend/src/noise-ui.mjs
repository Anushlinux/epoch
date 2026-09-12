import { escape } from './ui.mjs';

const ruleNames = { deduplicate: 'Consolidate exact duplicates', prefer_current_approved: 'Prefer approved current versions', match_topic: 'Match the requested topic' };
const cases = ['original', 'fresh', 'unaffected', 'historical'];
const json = value => `<pre class="trace-json">${escape(JSON.stringify(value, null, 2))}</pre>`;
const outcomeNames = { context_noise: 'Possible context noise', tool_defect: 'Possible tool issue', insufficient_evidence: 'More evidence needed', no_issue: 'No issue established' };
const paragraphs = text => String(text || '').split(/\n\s*\n/).filter(Boolean).map(part => `<p>${escape(part)}</p>`).join('');

export class NoisePanel {
  constructor(root, context, render, url) {
    Object.assign(this, { root, context, render, url });
    this.key = ''; this.data = null; this.error = ''; this.notice = ''; this.busy = false;
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
    root.addEventListener('invalid', event => {
      if (!event.target.closest('form[data-noise]')) return;
      // A renamed filter can be invalid while its optional name control is closed.
      for (let detail = event.target.closest('details'); detail && root.contains(detail); detail = detail.parentElement?.closest('details')) detail.open = true;
    }, true);
    root.addEventListener('click', event => {
      const button = event.target.closest('[data-noise-action]');
      if (!button || button.disabled) return;
      void this.action(button);
    });
  }

  sync() {
    const { origin, chat } = this.context(), key = `${origin}:${chat}`;
    if (key === this.key) return;
    this.key = key; this.data = null; this.error = ''; this.notice = ''; this.busy = false; this.pending = null;
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
    this.busy = true; this.error = ''; this.notice = ''; this.render();
    try {
      const { body } = await api.call(request.path, request.payload);
      if (key !== this.key) return;
      if (body.id !== request.payload.client_request_id || body.chat_id !== this.context().chat) throw new Error('Action acknowledgement could not be confirmed. Retry the exact action.');
      this.clearPending();
      if (body.kind === 'activation' && body.review_id) this.notice = 'Filter applied. New current document retrievals will use it.';
      if (body.kind === 'rollback') this.notice = 'Filter undone. New retrievals will use the previous policy, or no filter if none was active.';
      if (body.kind === 'cleanup_review') this.notice = body.ready ? 'Review ready. Check the affected sources before applying.' : 'Review needs attention. No filter has been applied.';
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
    if ((action === 'draft' && !f.getAll('rules').length)
      || (action === 'cleanup-review' && !f.getAll('rules').length && !f.getAll('source_action_ids').length)) {
      this.error = 'Select at least one suggested change to continue.'; this.render(); return;
    }
    if (action === 'analyze') return this.write(this.base + '/analyses', { trace_id: this.context().trace, issue: val('issue') }, form.id);
    if (action === 'metadata') {
      const source = this.data.sources.find(s => s.id === form.dataset.source);
      return this.write(this.base + '/sources/metadata', { expected_revision: revision, source_id: source.id, sha256: source.sha256,
        labels: { family: val('family'), version: val('version'), status: val('status'), approved: f.has('approved'), protected: f.has('protected'),
          topics: val('topics').split(',').map(v => v.trim()).filter(Boolean) } }, form.id);
    }
    if (action === 'draft') return this.write(this.base + '/policies', { analysis_id: form.dataset.analysis, title: val('title'), rules: f.getAll('rules') }, form.id);
    if (action === 'cleanup-review') return this.write(this.base + '/cleanup-reviews', {
      analysis_id: form.dataset.analysis, expected_revision: this.data.revision, title: val('title'),
      rules: f.getAll('rules'), ...(this.data.source_action_support ? { source_action_ids: f.getAll('source_action_ids') } : {}), topic: val('topic') || null }, form.id);
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
      if (!analysis || !['failed', 'answered'].includes(analysis.state) || analysis.request.trace_id !== this.context().trace || this.data.model_busy) return;
      return this.write(this.base + '/analyses', { trace_id: analysis.request.trace_id, issue: analysis.request.issue });
    }
    if (button.dataset.noiseAction === 'activate') {
      const policy = button.dataset.policy;
      const validations = cases.map(c => this.records('validation').find(v => v.policy_id === policy && v.case === c && v.passed));
      if (validations.some(v => !v)) return;
      return this.write(`${this.base}/policies/${policy}/activate`, { expected_revision: this.data.revision, validation_ids: validations.map(v => v.id) });
    }
    if (button.dataset.noiseAction === 'apply-cleanup') {
      const review = this.records('cleanup_review').find(r => r.id === button.dataset.review);
      if (!review || !review.ready || this.reviewStale(review)) return;
      return this.write(`${this.base}/cleanup-reviews/${review.id}/apply`, { expected_revision: review.snapshot.revision });
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
    return `<details class="noise-sources" data-key="noise-sources"><summary>Sources <span class="noise-count">${this.data.sources.length}</span></summary>
      <p class="trace-muted">Optional source annotations. Saving a change deactivates the current filter until reviewed again.</p>
      ${this.data.sources.map(source => {
        const fid = `noise-source-${source.id}`, label = this.data.labels[source.id] || {};
        return `<details data-key="noise-source-${escape(source.id)}"><summary>${escape(source.name)} · ${escape(label.status || 'unknown')}</summary>
          <form id="${escape(fid)}" data-noise="metadata" data-source="${escape(source.id)}"><fieldset ${this.busy || this.pending || this.data.busy ? 'disabled' : ''}>
          <div class="noise-fields">${this.input(fid, 'family', 'Version family', label.family)}${this.input(fid, 'version', 'Version', label.version)}${this.select(fid, 'status', 'Status', ['unknown','current','superseded'].map(v => [v,v]), label.status || 'unknown')}${this.input(fid, 'topics', 'Topics (comma separated)', (label.topics || []).join(', '))}</div>
          ${this.toggle(fid, 'approved', 'on', 'Approved by me', !!label.approved)}${this.toggle(fid, 'protected', 'on', 'Always retain this source', !!label.protected)}<button>Save source metadata</button></fieldset></form>
          <details data-key="noise-source-identity-${escape(source.id)}"><summary>Source identity</summary><small>ID ${escape(source.id)}<br>SHA-256 ${escape(source.sha256)}</small></details></details>`;
      }).join('')}</details>`;
  }

  policyView(policy) {
    const fid = `noise-preview-${policy.id}`, vid = `noise-validation-${policy.id}`;
    const previews = this.records('preview').filter(p => p.policy_id === policy.id);
    const validations = this.records('validation').filter(v => v.policy_id === policy.id);
    const ready = cases.every(c => validations.some(v => v.case === c && v.passed));
    const active = this.data.active_id === policy.id;
    const activation = this.data.active_activation?.policy_id === policy.id ? this.data.active_activation : this.records('activation').find(a => a.policy_id === policy.id && a.revision === this.data.revision);
    return `<details class="noise-policy" data-key="noise-policy-${policy.id}"><summary>${escape(policy.title)} · ${active ? (activation?.acceptance === 'user_approved_filter' ? 'Active · applied after user review' : 'Active policy') : 'Inactive policy'}</summary>
      <p>${[...policy.rules.map(r => escape(ruleNames[r])), ...(policy.source_exclusions?.length ? [`${policy.source_exclusions.length} reviewed document exclusion${policy.source_exclusions.length === 1 ? '' : 's'}`] : [])].join(' · ')}</p><small>Policy ${escape(policy.id)} · project ${escape(policy.project)}</small>
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

  reviewStale(review) {
    const fields = ['id', 'sha256', 'kind', 'name', 'size', 'project_id'];
    const signature = sources => JSON.stringify(sources.map(s => fields.map(f => s[f])));
    return review.snapshot.revision !== this.data.revision || review.previous_active_id !== this.data.active_id
      || signature(review.snapshot.sources) !== signature(this.data.sources);
  }

  sourceProposals(analysis) {
    const proposals = analysis?.source_validation ? analysis.source_validation.proposals : analysis?.source_proposals;
    return Array.isArray(proposals) ? proposals : [];
  }

  sourceProposalWarnings(analysis) {
    const warnings = analysis?.source_validation ? analysis.source_validation.warnings : analysis?.proposal_warnings;
    return Array.isArray(warnings) ? warnings : [];
  }

  legacySourceAnalysis(analysis) {
    return this.data.source_action_support && analysis?.answer && !analysis.source_validation && !Array.isArray(analysis.answer.source_actions);
  }

  sourceQuoteView(proposal, key, analysis) {
    return `<details class="noise-source-evidence" data-key="${escape(key)}"><summary>Why this source?</summary>
      ${proposal.source_quote ? `<p class="noise-quote-label">${escape(proposal.source_name || 'Source to exclude')}</p><blockquote>${escape(proposal.source_quote)}</blockquote>` : ''}
      ${proposal.replacement_quote ? `<p class="noise-quote-label">${escape(proposal.replacement_name || 'Source to keep')}</p><blockquote>${escape(proposal.replacement_quote)}</blockquote>` : ''}
      ${[proposal.quote_matches?.source, proposal.quote_matches?.replacement].some(match => match?.method === 'pdf_layout') ? '<p class="trace-muted">Matched across PDF spacing differences. Quotes show the original source text.</p>' : ''}
      ${analysis && proposal.evidence_ids?.length ? `<div class="trace-citations">${this.evidenceLinks(analysis, proposal.evidence_ids)}</div>` : ''}
      <small>Source ID ${escape(proposal.source_id)}<br>Replacement ID ${escape(proposal.replacement_id)}</small>
      </details>`;
  }

  sourceProposalView(proposal, analysis, form) {
    return `<section class="noise-source-proposal">
      ${this.toggle(form, 'source_action_ids', proposal.id, `Exclude ${proposal.source_name || proposal.source_id}`, true)}
      <p class="noise-proposal-replacement"><span>Keep instead</span> ${escape(proposal.replacement_name || proposal.replacement_id)}</p>
      <div class="noise-proposal-reason">${paragraphs(proposal.explanation)}</div>
      ${this.sourceQuoteView(proposal, `noise-proposal-${analysis.id}-${proposal.id}`, analysis)}
      </section>`;
  }

  rerunSourceAnalysisView(analysis) {
    return `<div class="noise-analysis-update"><p>This saved analysis predates document suggestions. Investigate again to identify specific sources.</p>
      <button class="noise-primary" type="button" data-noise-action="retry-analysis" data-analysis="${escape(analysis.id)}" ${this.busy || this.pending || this.data.model_busy ? 'disabled' : ''}>Investigate again</button></div>`;
  }

  cleanupFormView(analysis) {
    const direct = this.data.supports_cleanup_review, fid = `noise-cleanup-${analysis.id}`;
    if (!direct) return '<p class="noise-next-note">This environment requires trial review before activation. Open Manage sources and history to create a draft.</p>';
    const review = this.records('cleanup_review').find(r => r.analysis_id === analysis.id);
    if (this.legacySourceAnalysis(analysis)) return `${review && this.data.active_activation?.review_id === review.id ? `<details class="noise-disclosure" data-key="noise-applied-review-${review.id}"><summary>View applied source review</summary>${this.cleanupReviewView(review)}</details>` : ''}${this.rerunSourceAnalysisView(analysis)}`;
    const proposals = this.sourceProposals(analysis), rules = analysis.answer.rules || [];
    const ruleControls = `${rules.map(r => this.toggle(fid,'rules',r,ruleNames[r],!proposals.length)).join('')}${rules.includes('match_topic') ? this.input(fid,'topic','Topic to match') : ''}`;
    const form = `<form class="noise-cleanup-form" id="${fid}" data-noise="cleanup-review" data-analysis="${analysis.id}"><fieldset ${this.busy || this.pending || this.data.busy ? 'disabled' : ''}><legend>${proposals.length ? 'Suggested source exclusions' : 'Suggested filter'}</legend>
      ${proposals.map(proposal => this.sourceProposalView(proposal, analysis, fid)).join('')}
      ${proposals.length && rules.length ? `<details class="noise-additional-rules" data-key="noise-additional-rules-${analysis.id}"><summary>Additional filter rules</summary>${ruleControls}</details>` : ruleControls}
      <details class="noise-filter-name" data-key="noise-filter-name-${analysis.id}"><summary>Filter name</summary>${this.input(fid,'title','Name','Reviewed document cleanup')}</details>
      <div class="noise-action-row"><button class="noise-primary">${review ? 'Update source review' : 'Review affected sources'}</button><span>No changes until you apply.</span></div>
      </fieldset></form>`;
    if (!review) return form;
    if (this.data.active_activation?.review_id === review.id) return `<details class="noise-disclosure" data-key="noise-applied-review-${review.id}"><summary>View applied source review</summary>${this.cleanupReviewView(review)}<details class="noise-edit-filter" data-key="noise-edit-filter-${review.id}"><summary>Change suggested filter</summary>${form}</details></details>`;
    return `${this.cleanupReviewView(review)}<details class="noise-edit-filter" data-key="noise-edit-filter-${review.id}" ${this.reviewStale(review) && this.data.active_activation?.review_id !== review.id ? 'open' : ''}><summary>Change suggested filter</summary>${form}</details>`;
  }

  draftFormView(analysis) {
    if (!analysis?.answer?.rules?.length || analysis.answer.outcome !== 'context_noise') return '';
    const fid = `noise-draft-${analysis.id}`;
    return `<details data-key="noise-trial-option-${analysis.id}"><summary>Create a trial draft</summary>
      <p class="trace-muted">This separate path requires four recorded trial assessments before activation.</p>
      <form id="${fid}" data-noise="draft" data-analysis="${analysis.id}"><fieldset ${this.busy || this.pending || this.data.busy ? 'disabled' : ''}>${this.input(fid,'title','Policy name')}${analysis.answer.rules.map(r => this.toggle(fid,'rules',r,ruleNames[r],true)).join('')}<button>Save trial draft</button></fieldset></form></details>`;
  }

  cleanupReviewView(review) {
    const applied = this.data.active_activation?.review_id === review.id;
    const stale = !applied && this.reviewStale(review);
    const sources = new Map(review.snapshot.sources.map(s => [s.id, s]));
    const newlyExcluded = new Set(review.newly_excluded_ids);
    const proposals = review.proposed_source_actions || [];
    const inheritedProposals = review.inherited_source_exclusions || [];
    const analysis = this.records('analysis').find(item => item.id === review.analysis_id);
    const decisions = [...review.selection.decisions].sort((a, b) => Number(newlyExcluded.has(b.source_id)) - Number(newlyExcluded.has(a.source_id)));
    return `<section class="noise-cleanup-review" aria-labelledby="cleanup-heading-${review.id}"><p class="noise-role-label">${applied ? 'Applied filter' : 'Review before applying'}</p><h3 id="cleanup-heading-${review.id}">${escape(review.title)}</h3>
      <p class="noise-review-count"><strong>${review.newly_excluded_ids.length} source${review.newly_excluded_ids.length === 1 ? '' : 's'} ${applied ? 'newly excluded' : 'to exclude'}</strong><span>${review.selection.retained_ids.length} of ${review.snapshot.sources.length} kept</span></p>
      <p class="noise-scope">Project <strong>${escape(review.project)}</strong> · Documents · Future current retrievals across this project.${review.query.topic ? ` Preview topic: ${escape(review.query.topic)}. Future matching uses the requested topic.` : ''}</p>
      ${review.rules.length ? `<p>${review.rules.map(r => escape(ruleNames[r])).join(' · ')}</p>` : ''}
      ${review.inherited_rules.length ? `<small>Carried forward from the active filter: ${review.inherited_rules.map(r => escape(ruleNames[r])).join(' · ')}.</small>` : ''}
      <div class="noise-source-table" tabindex="0" role="region" aria-label="Reviewed source selection"><table><thead><tr><th scope="col">Source</th><th scope="col">After applying</th><th scope="col">Reason and retained replacement</th></tr></thead><tbody>
      ${decisions.map(d => {
        const source = sources.get(d.source_id), replacement = sources.get(d.replacement_id);
        const proposed = proposals.find(item => item.source_id === d.source_id);
        const proposal = proposed || inheritedProposals.find(item => item.source_sha256 && item.source_sha256 === d.sha256);
        return `<tr><td>${escape(source?.name || d.source_id)}<details data-key="cleanup-source-${review.id}-${escape(d.source_id)}"><summary>Source identity</summary><small>ID ${escape(d.source_id)}<br>SHA-256 ${escape(d.sha256)}</small></details></td><td><span class="noise-selection ${d.retained ? 'noise-selection-keep' : 'noise-selection-exclude'}">${d.retained ? 'Keep' : newlyExcluded.has(d.source_id) ? 'Exclude' : 'Already excluded'}</span></td><td>${proposal && !d.retained ? `<div class="noise-review-explanation">${paragraphs(proposal.explanation)}</div>` : escape(d.reason.replaceAll('_',' '))}${replacement ? `<small>Keep instead: ${escape(replacement.name)}</small>` : ''}${proposal ? this.sourceQuoteView(proposal, `cleanup-evidence-${review.id}-${d.source_id}`, proposed ? analysis : null) : ''}</td></tr>`;
      }).join('')}
      </tbody></table></div>
      ${[...review.blocked, ...review.selection.warnings].map(w => `<p class="trace-notice">${escape(w)}</p>`).join('')}
      <p class="noise-review-note">Original files and history stay available. This filter changes future context; it does not repair tools or guarantee an outcome.</p>
      ${applied ? '<p class="trace-ready">Applied. Future current retrievals use this filter.</p>' : `${stale ? '<p class="trace-notice">Sources or settings changed. Update the source review before applying.</p>' : ''}
      <button class="noise-apply" type="button" data-noise-action="apply-cleanup" data-review="${review.id}" ${!review.ready || stale || this.busy || this.pending || this.data.busy ? 'disabled' : ''}>${this.busy && this.pending?.path.endsWith(`/${review.id}/apply`) ? 'Applying…' : 'Apply filter'}</button>
      `}
      </section>`;
  }

  activeFilterView() {
    if (!this.data.active_id) return '';
    const policy = this.records('policy').find(p => p.id === this.data.active_id), activation = this.data.active_activation;
    return `<section class="noise-active-filter" aria-label="Active context filter"><div><h3>Filter active${policy ? `: ${escape(policy.title)}` : ''}</h3>
      <p>Future current retrievals · ${escape(this.data.project)} · ${this.data.environment === 'pdf_workshop' ? 'Documents' : escape(this.data.environment)}</p></div>
      ${activation ? `<button type="button" data-noise-action="rollback" data-activation="${activation.id}" ${this.busy || this.pending || this.data.busy ? 'disabled' : ''}>Undo filter</button>` : ''}</section>`;
  }

  nextStepView(answer) {
    if (answer.outcome === 'tool_defect') {
      const pdf = this.data.environment === 'pdf_workshop';
      const href = `/debugger?chat=${encodeURIComponent(this.context().chat)}`;
      return `<div class="noise-next-action"><p>Review this possible tool issue in the debugger.</p><a class="noise-primary" href="${escape(href)}">${pdf ? 'Open PDF debugger' : 'Open conversation debugger'}</a></div>`;
    }
    if (answer.outcome === 'insufficient_evidence') return '<p class="noise-next-note">Review the missing evidence before investigating again.</p>';
    if (answer.outcome === 'no_issue') return '<p class="noise-next-note">No filter suggested. Review the result against your original task.</p>';
    return '<p class="noise-next-note">No source exclusion could be confirmed from this analysis.</p>';
  }

  analysisFormView(trace) {
    const fid = `noise-analysis-${trace}`;
    const pendingIssue = this.pending?.path === this.base + '/analyses' && this.pending.payload.trace_id === trace ? this.pending.payload.issue : '';
    return `<form class="noise-composer" id="${fid}" data-noise="analyze"><fieldset ${this.busy || this.pending || this.data.model_busy ? 'disabled' : ''}>
      ${this.input(fid,'issue','What would you like to investigate?',pendingIssue, 'textarea')}
      <div class="noise-action-row"><button class="noise-primary">${this.busy && this.pending?.path.endsWith('/analyses') ? 'Starting…' : 'Investigate'}</button><span>Local model · Ollama</span></div>
      </fieldset></form>`;
  }

  evidenceLinks(analysis, ids) {
    return ids.map(id => {
      const evidence = analysis.snapshot.evidence.find(item => item.id === id);
      return evidence?.span_id ? `<a data-route class="trace-citation" href="${escape(this.url({span:evidence.span_id}) + '#trace-selected-span')}">${escape(id)} · ${escape(evidence.name)}</a>` : '';
    }).join('');
  }

  analysisView(analysis) {
    const answer = analysis.answer, warnings = [...new Set([...(answer?.missing_evidence || []), ...(analysis.snapshot?.warnings || [])])];
    const proposalWarnings = this.sourceProposalWarnings(analysis);
    const hasSuggestions = answer?.outcome === 'context_noise' && (answer.rules.length || this.sourceProposals(analysis).length);
    const heading = `noise-answer-heading-${analysis.id}`;
    const question = `<section class="noise-question-card" aria-label="Your question"><p class="noise-role-label">Your question</p><div class="noise-question-text">${paragraphs(analysis.request.issue)}</div></section>`;
    let content;
    if (analysis.state === 'running') content = '<p class="noise-running" role="status">Investigating with your local model…</p>';
    else if (analysis.error) content = `<p class="trace-question-error" role="alert">${escape(analysis.error)}</p>
      ${analysis.error_code || analysis.error_details ? `<details class="noise-disclosure" data-key="noise-failure-${escape(analysis.id)}"><summary>Failure details</summary>${analysis.error_code ? `<p>Error code: ${escape(analysis.error_code)}</p>` : ''}${analysis.error_details ? json(analysis.error_details) : ''}</details>` : ''}
      <button class="noise-primary" type="button" data-noise-action="retry-analysis" data-analysis="${escape(analysis.id)}" ${this.busy || this.pending || this.data.model_busy ? 'disabled' : ''}>Retry investigation</button>`;
    else if (!answer) content = '<p class="trace-notice">Analysis is not available yet.</p>';
    else content = `<div class="noise-answer-summary">${paragraphs(answer.summary)}</div>
      <p class="noise-review-caution">Model assessment · Review the evidence before making changes.</p>
      ${proposalWarnings.length ? `<details class="noise-evidence-warning" data-key="noise-proposal-warning-${analysis.id}"><summary>Some suggestions could not be confirmed <span class="noise-count">${proposalWarnings.length}</span></summary><ul>${proposalWarnings.map(warning => `<li>${escape(warning)}</li>`).join('')}</ul></details>` : ''}
      ${warnings.length ? `<details class="noise-evidence-warning" data-key="noise-warning-${analysis.id}"><summary>Evidence is incomplete <span class="noise-count">${warnings.length}</span></summary><ul>${warnings.map(warning => `<li>${escape(warning)}</li>`).join('')}</ul></details>` : ''}
      ${hasSuggestions ? this.cleanupFormView(analysis) : this.legacySourceAnalysis(analysis) ? this.rerunSourceAnalysisView(analysis) : this.nextStepView(answer)}
      <details class="noise-disclosure noise-findings" data-key="noise-evidence-${analysis.id}"><summary>Evidence <span class="noise-count">${answer.findings.length} finding${answer.findings.length === 1 ? '' : 's'}</span></summary>
      ${answer.findings.map(finding => `<section class="noise-finding"><header><h4>${escape(finding.kind.replaceAll('_',' '))}</h4><span>${escape(finding.confidence)} confidence</span></header><div>${paragraphs(finding.explanation)}</div><div class="trace-citations">${this.evidenceLinks(analysis, finding.evidence_ids)}</div></section>`).join('')}
      ${answer.relevant_evidence_ids?.length ? `<div class="noise-relevant-evidence"><h4>Referenced steps</h4><div class="trace-citations">${this.evidenceLinks(analysis, answer.relevant_evidence_ids)}</div></div>` : ''}</details>`;
    return `${question}<article class="noise-answer-card" aria-labelledby="${escape(heading)}"><header class="noise-answer-heading"><h3 id="${escape(heading)}">Analysis</h3>${answer ? `<span class="noise-outcome">${escape(outcomeNames[answer.outcome] || answer.outcome.replaceAll('_',' '))}</span>` : ''}</header>${content}</article>`;
  }

  advancedView(analysis) {
    return `<details class="noise-advanced" data-key="noise-advanced"><summary>Manage sources and history</summary><div class="noise-advanced-body">
      ${this.metadataView()}
      <details data-key="noise-decisions"><summary>Delivered context</summary>${this.data.decisions.length ? this.data.decisions.map(d => `<details data-key="noise-decision-${d.id}"><summary>${escape(d.tool)} · ${escape(d.created_at)}</summary>${this.loadedDecisions.has(d.id) ? json(this.loadedDecisions.get(d.id)) : `<button type="button" data-noise-action="decision" data-decision="${d.id}">Load recorded context</button>${json(d)}`}</details>`).join('') : '<p class="trace-muted">No context selections recorded yet.</p>'}</details>
      <details data-key="noise-policies"><summary>Filters and trials</summary>${this.draftFormView(analysis)}${this.records('policy').slice(0,10).map(p => this.policyView(p)).join('') || '<p class="trace-muted">No filters saved.</p>'}</details>
      <details data-key="noise-history"><summary>History</summary>${this.data.records.map(r => `<details data-key="noise-record-${r.id}"><summary>${escape(r.kind.replaceAll('_',' '))} · ${escape(r.title || r.request?.issue || r.created_at)}</summary>${json(r)}</details>`).join('') || '<p class="trace-muted">No investigations yet.</p>'}</details>
      <details data-key="noise-workspace-info"><summary>Workspace details</summary><dl class="noise-workspace-facts"><dt>Project</dt><dd>${escape(this.data.project)}</dd><dt>Revision</dt><dd>${this.data.revision}</dd><dt>Environment</dt><dd>${escape(this.data.environment)}</dd><dt>Local model</dt><dd>${escape(this.data.model)}</dd><dt>History</dt><dd>Latest ${this.data.history_limit} records</dd></dl><p class="trace-muted">Protected sources remain available. Version and topic rules retain sources with unknown metadata; reviewed source exclusions use matching document content. Source annotations can be reused for matching files in this project and environment.</p></details>
      </div></details>`;
  }

  view() {
    this.sync();
    const { chat, trace } = this.context();
    if (!chat) return '<p class="trace-notice">Open a conversation’s traces to investigate an issue.</p>';
    const analysis = this.latest();
    const pendingAnalysis = this.pending?.path === this.base + '/analyses' && this.pending.payload.trace_id === trace;
    const hasDraft = Boolean(this.value(`noise-analysis-${trace}`, 'issue').trim() || pendingAnalysis);
    return `<section class="trace-questions noise-panel" id="noise-workspace"><header class="trace-question-heading"><div><h2>Investigate this trace</h2>${this.data ? `<p class="noise-workspace-label">${escape(this.data.project)}${this.data.active_id ? '' : ' · No active filter'}</p>` : ''}</div></header>
      ${this.notice ? `<p class="trace-ready noise-notification" role="status">${escape(this.notice)}</p>` : ''}
      ${this.error ? `<p class="trace-question-error" role="alert">${escape(this.error)}</p>` : ''}${this.data?.warning ? `<p class="trace-question-error" role="alert">${escape(this.data.warning)}</p>` : ''}
      ${this.pending ? `<div class="trace-notice noise-pending"><p>Waiting for confirmation.</p><button type="button" data-noise-action="retry" ${this.busy ? 'disabled' : ''}>Confirm or retry exact action</button></div>` : ''}
      ${!this.data ? '<p role="status">Loading investigation…</p>' : `${this.activeFilterView()}
      ${analysis ? this.analysisView(analysis) : trace ? this.analysisFormView(trace) : '<p class="trace-muted">Select a trace to investigate.</p>'}
      ${analysis && trace ? `<details class="noise-ask-another" data-key="noise-ask-${analysis.id}-${hasDraft ? 'draft' : 'empty'}" ${hasDraft ? 'open' : ''}><summary>${hasDraft ? 'Your next question · Draft' : 'Ask another question'}</summary>${this.analysisFormView(trace)}</details>` : ''}
      ${this.advancedView(analysis)}`}
    </section>`;
  }
}
