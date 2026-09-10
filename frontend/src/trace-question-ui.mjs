import { escape } from './ui.mjs';

const empty = () => ({ runtime: null, history: null, selected: null, error: '', sending: false });
const json = value => `<pre class="trace-json" tabindex="0">${escape(JSON.stringify(value, null, 2))}</pre>`;

export class TraceQuestionPanel {
  constructor(root, context, render, navigate, url) {
    Object.assign(this, { root, context, render, navigate, url, state: empty(), key: '', drafts: new Map(), pending: null });
    root.addEventListener('input', event => {
      if (event.target.id === 'trace-question-text') this.drafts.set(this.key, event.target.value);
    });
    root.addEventListener('submit', event => {
      if (event.target.id !== 'trace-question-form') return;
      event.preventDefault();
      void this.submit();
    });
    root.addEventListener('click', event => {
      if (event.target.closest('[data-action="retry-trace-question"]')) void this.submit();
    });
  }

  sync() {
    const { origin, trace } = this.context();
    const key = `epoch.trace-question.pending.v1:${origin}:${trace}`;
    if (key === this.key) return;
    this.key = key;
    this.state = empty();
    this.pending = null;
    try {
      const pending = JSON.parse(sessionStorage.getItem(key) || 'null');
      if (pending && typeof pending.client_request_id === 'string' && typeof pending.question === 'string') this.pending = pending;
    } catch { /* Retrying in this tab still retains the in-memory request identity. */ }
  }

  clearPending() {
    this.pending = null;
    try { sessionStorage.removeItem(this.key); } catch { /* Saved server history remains available. */ }
  }

  async refresh() {
    this.sync();
    const { api, trace, question, questionOffset } = this.context(), key = this.key;
    if (!trace) return;
    const result = await Promise.allSettled([
      api.questionRuntime(), api.questions(trace, questionOffset),
      question ? api.question(trace, question) : Promise.resolve(null),
    ]);
    if (key !== this.key || question !== this.context().question || questionOffset !== this.context().questionOffset) return;
    const errors = [];
    for (const [index, field] of ['runtime', 'history', 'selected'].entries()) {
      if (result[index].status === 'fulfilled') this.state[field] = result[index].value;
      else errors.push(result[index].reason.message);
    }
    // Never show another question's answer after URL selection changes.
    if (this.state.selected?.id !== question) this.state.selected = null;
    this.state.error = errors.join(' ');
    if (this.pending && [this.state.selected, ...(this.state.history?.items || [])].some(item => item?.id === this.pending.client_request_id)) this.clearPending();
  }

  async submit() {
    this.sync();
    if (this.state.sending) return;
    const { trace, span, api } = this.context(), key = this.key;
    const question = (this.drafts.get(key) || '').trim();
    if (!this.pending && !question) return;
    this.pending ||= { client_request_id: crypto.randomUUID(), question, span_id: span || null };
    const payload = this.pending;
    try { sessionStorage.setItem(key, JSON.stringify(payload)); } catch { /* Keep the same ID in memory on a network retry. */ }
    this.state.sending = true;
    this.state.error = '';
    this.render();
    try {
      const result = await api.ask(trace, payload);
      if (this.key !== key) return;
      this.clearPending();
      if (this.drafts.get(key)?.trim() === payload.question) this.drafts.delete(key);
      this.state.selected = result;
      this.state.sending = false;
      this.navigate(this.url({ question: result.id, question_offset: 0 }));
    } catch (error) {
      if (this.key !== key) return;
      if (error.status >= 400 && error.status < 500) this.clearPending();
      this.state.error = error.message;
    } finally {
      if (this.key === key) { this.state.sending = false; this.render(); }
    }
  }

  citations(ids, snapshot) {
    return ids.map(id => {
      const evidence = snapshot.evidence.find(item => item.id === id);
      if (!evidence) return '<span class="trace-warning-label">Unavailable reference</span>';
      return `<a data-route class="trace-citation" href="${escape(this.url({ span: evidence.span_id }) + '#trace-selected-span')}" title="${escape(evidence.name)}">${escape(id)} · ${escape(evidence.name)}</a>`;
    }).join('');
  }

  answerView(record) {
    const snapshot = record.snapshot;
    const findings = (items, title) => items.length ? `<section class="trace-answer-section"><h4>${title}</h4>${items.map(item => `<p>${escape(item.text)}</p><div class="trace-citations">${this.citations(item.evidence_ids, snapshot)}</div>`).join('')}</section>` : '';
    return `<article class="trace-answer" aria-label="Saved trace question"><header><h3>${escape(record.question)}</h3><span>${escape(record.model)} · ${escape(new Date(record.created_at).toLocaleString())}</span></header>
      ${record.state === 'running' ? '<p class="trace-question-status" role="status">Waiting for local Ollama to finish… You can browse other spans while it works.</p>' : ''}
      ${record.state === 'failed' ? `<p class="trace-question-error" role="alert">${escape(record.error?.message || 'The question could not be completed.')}</p>${record.error?.code ? `<p class="trace-muted">Error code: ${escape(record.error.code)}</p>` : ''}${record.error?.details ? `<details data-key="question-failure-${escape(record.id)}"><summary>Failure details</summary><pre class="trace-json">${escape(JSON.stringify(record.error.details, null, 2))}</pre></details>` : ''}` : ''}
      ${record.answer ? `${findings(record.answer.answer, 'Answer')}${findings(record.answer.hypotheses, 'Possible explanations')}${record.answer.missing_evidence.length ? `<section class="trace-answer-section"><h4>Missing evidence</h4><ul>${record.answer.missing_evidence.map(item => `<li>${escape(item)}</li>`).join('')}</ul></section>` : ''}<p class="trace-muted">Evidence references were checked. The explanation is model-generated and may need your review.</p>` : ''}
      <details class="trace-question-evidence" data-key="question-evidence-${record.id}"><summary>Evidence sent to the model · ${snapshot.included_span_count} of ${snapshot.indexed_span_count} indexed spans</summary>
        <p class="trace-muted">Snapshot saved ${escape(new Date(snapshot.captured_at).toLocaleString())}. Later arrivals do not change this answer.</p>
        ${snapshot.warnings.map(warning => `<p class="trace-notice">${escape(warning)}</p>`).join('')}
        ${snapshot.evidence.map(item => `<details data-key="question-source-${record.id}-${item.id}"><summary>${escape(item.id)} · ${escape(item.name)}</summary>${this.citations([item.id], snapshot)}${json(item)}</details>`).join('')}
      </details>
      ${snapshot.warnings.length ? `<p class="trace-warning-label">${snapshot.warnings.length} evidence limitation${snapshot.warnings.length === 1 ? '' : 's'} — see the saved snapshot above.</p>` : ''}
    </article>`;
  }

  view() {
    this.sync();
    const { trace, span, question, questionOffset } = this.context();
    if (!trace) return '';
    const { runtime, history, selected, sending, error } = this.state;
    const active = runtime?.active_question_id || history?.items.find(item => item.state === 'running')?.id || runtime?.model_busy;
    const record = question ? selected?.id === question ? selected : null : history?.items[0];
    const draft = this.pending?.question ?? this.drafts.get(this.key) ?? '';
    return `<section class="trace-questions" id="trace-questions" aria-labelledby="trace-questions-title">
      <header class="trace-question-heading"><div><p class="trace-eyebrow">LOCAL MODEL</p><h2 id="trace-questions-title">Ask about this trace</h2></div><span>${runtime ? escape(runtime.model) : 'Loading configuration…'}</span></header>
      <p class="trace-muted">Ask what happened or why a result looks wrong. Selected evidence goes to your local Ollama when you submit.</p>
      ${runtime ? `<p class="trace-question-scope">${span ? `Focus: span ${escape(span.slice(0, 12))} and related steps` : 'Scope: this trace'} · Ollama connection checked when you ask</p>` : ''}
      ${error ? `<p class="trace-question-error" role="alert">${escape(error)}${record ? ' The saved answer remains visible.' : ''}</p>` : ''}
      ${(runtime?.warnings || []).map(warning => `<p class="trace-notice">${escape(warning)}</p>`).join('')}
      <form id="trace-question-form"><label for="trace-question-text" class="sr-only">Question about this trace</label><textarea id="trace-question-text" name="trace-question" rows="3" maxlength="2000" required placeholder="Why did this run choose the wrong invoice?" ${this.pending || sending ? 'disabled' : ''}>${escape(draft)}</textarea>
        <div class="trace-question-actions"><span>${active ? 'A local question is running. It will continue if you leave this page.' : 'One question at a time · no changes to your agent or traces'}</span>
          ${this.pending ? `<button type="button" data-action="retry-trace-question" ${sending ? 'disabled' : ''}>${sending ? 'Submitting…' : 'Confirm or retry submission'}</button>` : `<button type="submit" ${sending || active || !runtime?.available ? 'disabled' : ''}>Ask local model</button>`}</div>
      </form>
      ${history?.items.length ? `<nav class="trace-question-history" aria-label="Saved trace questions">${history.items.map(item => `<a data-route class="${record?.id === item.id ? 'selected' : ''}" href="${escape(this.url({ question: item.id }))}" ${record?.id === item.id ? 'aria-current="true"' : ''}>${escape(item.question)}<span>${escape(item.state)}</span></a>`).join('')}</nav>` : '<p class="trace-muted">No saved questions for this trace yet.</p>'}
      ${history && (questionOffset || history.total > 5) ? `<nav class="trace-pagination" aria-label="Question pages">${questionOffset ? `<a data-route href="${escape(this.url({ question_offset: Math.max(0, questionOffset - 5), question: '' }))}">Newer questions</a>` : '<span></span>'}<span>${Math.min(questionOffset + 1, history.total)}–${Math.min(questionOffset + 5, history.total)} of ${history.total}</span>${questionOffset + 5 < history.total ? `<a data-route href="${escape(this.url({ question_offset: questionOffset + 5, question: '' }))}">Older questions</a>` : '<span></span>'}</nav>` : ''}
      ${record ? this.answerView(record) : question ? '<p class="trace-muted">Loading selected answer, or it is unavailable. Refresh to retry.</p>' : ''}
    </section>`;
  }
}
