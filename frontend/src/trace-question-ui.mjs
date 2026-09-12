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
    const missing = record.answer?.missing_evidence || [];
    const limitations = [...missing, ...snapshot.warnings];
    const findings = items => items.map(item => `<div class="tq-finding"><p>${escape(item.text)}</p><div class="trace-citations">${this.citations(item.evidence_ids, snapshot)}</div></div>`).join('');
    return `<article class="trace-answer tq-conversation" aria-label="Saved question and answer">
      <section class="tq-question" aria-label="Your question"><h3>Your question</h3><p>${escape(record.question)}</p></section>
      <section class="tq-response" aria-label="Local model answer"><header class="tq-response-heading"><h3>Answer</h3><span>Local model · review required</span></header>
        ${record.state === 'running' ? '<p class="trace-question-status" role="status">Analyzing this trace…</p>' : ''}
        ${record.state === 'failed' ? `<p class="trace-question-error" role="alert">${escape(record.error?.message || 'The question could not be completed.')}</p>${record.error?.code || record.error?.details ? `<details class="tq-disclosure" data-key="question-failure-${escape(record.id)}"><summary>Error details</summary>${record.error.code ? `<p>${escape(record.error.code)}</p>` : ''}${record.error.details ? json(record.error.details) : ''}</details>` : ''}` : ''}
        ${record.answer ? `${findings(record.answer.answer)}${record.answer.hypotheses.length ? `<details class="tq-disclosure" data-key="question-hypotheses-${escape(record.id)}"><summary>Possible explanations · ${record.answer.hypotheses.length}</summary>${findings(record.answer.hypotheses)}</details>` : ''}` : ''}
        ${limitations.length ? `<details class="tq-disclosure tq-limitations" data-key="question-limitations-${escape(record.id)}"><summary>Evidence is incomplete · ${limitations.length} limitation${limitations.length === 1 ? '' : 's'}</summary>${missing.length ? `<h4>Missing evidence</h4><ul>${missing.map(item => `<li>${escape(item)}</li>`).join('')}</ul>` : ''}${snapshot.warnings.length ? `<h4>Capture and selection limits</h4><ul>${snapshot.warnings.map(warning => `<li>${escape(warning)}</li>`).join('')}</ul>` : ''}</details>` : ''}
        <details class="tq-disclosure tq-evidence" data-key="question-evidence-${escape(record.id)}"><summary>View evidence · ${snapshot.included_span_count} of ${snapshot.indexed_span_count} steps</summary>
          <p class="tq-evidence-meta">${escape(record.model)} · ${escape(new Date(record.created_at).toLocaleString())}</p><p class="tq-evidence-meta">Snapshot: ${escape(new Date(snapshot.captured_at).toLocaleString())}. Later trace arrivals are not included.</p>
          ${snapshot.evidence.map(item => `<details class="tq-source" data-key="question-source-${escape(record.id)}-${escape(item.id)}"><summary>${escape(item.id)} · ${escape(item.name)}</summary>${this.citations([item.id], snapshot)}${json(item)}</details>`).join('')}
        </details>
      </section>
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
    const composer = `<form id="trace-question-form" class="tq-composer"><label for="trace-question-text">${record ? 'Your next question' : 'Your question'}</label><textarea id="trace-question-text" name="trace-question" rows="3" maxlength="2000" required placeholder="What would you like to understand about this run?" ${this.pending || sending ? 'disabled' : ''}>${escape(draft)}</textarea>
      <div class="trace-question-actions"><span>${active ? 'A local analysis is running…' : span ? `Focused on step ${escape(span.slice(0, 12))}` : 'Uses the recorded trace'}${!active && runtime && !runtime.available ? ' · Local model unavailable' : ''}</span>
        ${this.pending ? `<button type="button" data-action="retry-trace-question" ${sending ? 'disabled' : ''}>${sending ? 'Submitting…' : 'Check submission'}</button>` : `<button type="submit" ${sending || active || !runtime?.available ? 'disabled' : ''}>${sending ? 'Submitting…' : 'Ask local model'}</button>`}</div>
      ${this.pending && !sending ? '<p class="tq-evidence-meta">The submission was not confirmed. Check it before sending another question.</p>' : ''}
    </form>`;
    return `<section class="trace-questions trace-question-panel" id="trace-questions" aria-labelledby="trace-questions-title">
      <header class="trace-question-heading"><h2 id="trace-questions-title">${record ? 'Trace explanation' : 'Ask about this trace'}</h2><span>Local Ollama</span></header>
      ${error ? `<p class="trace-question-error" role="alert">${escape(error)}${record ? ' The saved answer remains visible.' : ''}</p>` : ''}
      ${runtime?.warnings?.length ? `<details class="tq-disclosure tq-limitations" data-key="question-runtime-${escape(trace)}"><summary>Local model notice${runtime.warnings.length === 1 ? '' : 's'} · ${runtime.warnings.length}</summary><ul>${runtime.warnings.map(warning => `<li>${escape(warning)}</li>`).join('')}</ul></details>` : ''}
      ${record ? this.answerView(record) : question ? '<p class="trace-muted">Loading selected answer, or it is unavailable. Refresh to retry.</p>' : ''}
      ${record ? `<details class="tq-disclosure tq-next-question" data-key="question-composer-${escape(trace)}-${escape(record.id)}" ${this.pending || sending || draft ? 'open' : ''}><summary>Ask another question</summary>${composer}</details>` : composer}
      ${history && (history.items.length || questionOffset) ? `<details class="tq-disclosure tq-history" data-key="question-history-${escape(trace)}"><summary>Previous questions · ${history.total}</summary><nav class="trace-question-history" aria-label="Saved trace questions">${history.items.map(item => `<a data-route class="${record?.id === item.id ? 'selected' : ''}" href="${escape(this.url({ question: item.id }))}" ${record?.id === item.id ? 'aria-current="true"' : ''}><span class="tq-history-question">${escape(item.question)}</span><span class="tq-history-state">${escape(item.state)}</span></a>`).join('')}</nav>
        ${history && (questionOffset || history.total > 5) ? `<nav class="trace-pagination" aria-label="Question pages">${questionOffset ? `<a data-route href="${escape(this.url({ question_offset: Math.max(0, questionOffset - 5), question: '' }))}">Newer</a>` : '<span></span>'}<span>${Math.min(questionOffset + 1, history.total)}–${Math.min(questionOffset + 5, history.total)} of ${history.total}</span>${questionOffset + 5 < history.total ? `<a data-route href="${escape(this.url({ question_offset: questionOffset + 5, question: '' }))}">Older</a>` : '<span></span>'}</nav>` : ''}
      </details>` : ''}
    </section>`;
  }
}
