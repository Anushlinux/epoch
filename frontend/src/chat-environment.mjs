import { escape } from './ui.mjs';
export const SAMPLE_PROMPT = 'Read the Northstar Studio Retreat Brief using documents.list and documents.read. Create a client-ready PDF preserving every supplied section, itinerary entry, accommodation option, budget figure and cancellation condition. Use the complete supplied content without shortening it. Report the actual PDF result.';
export const FESTIVAL_PROMPT = 'Read the Horizon Festival Sponsorship Brief. Create a client-ready PDF preserving every package, benefit and payment condition. Use the complete supplied content without shortening it.';
export const environmentLabel = value => value === 'pdf_workshop' ? 'Documents' : 'Standard tools';
export function fileControls(disabled) {
  return `<div class="pdf-file-controls"><button type="button" data-action="seed-retreat" ${disabled ? 'disabled' : ''}>Northstar example</button><button type="button" data-action="seed-festival" ${disabled ? 'disabled' : ''}>Festival example</button><label class="pdf-upload">Upload PDF<input id="pdf-upload" type="file" accept="application/pdf,.pdf" ${disabled ? 'disabled' : ''}></label></div>`;
}
export function environmentPicker(value, disabled) {
  return `<label class="compact-field" for="chat-environment">Tools<select id="chat-environment" ${disabled ? 'disabled' : ''}>${['pdf_workshop', 'default'].map(v => `<option value="${v}" ${value === v ? 'selected' : ''}>${environmentLabel(v)}</option>`).join('')}</select></label>`;
}
export function environmentView(state, { showResult = true, showTools = false } = {}) {
  if (state.chat?.environment !== 'pdf_workshop') return '';
  const env = state.environment;
  const busy = state.busy || state.pending || state.chat.operations.some(o => o.status === 'running');
  if (!env) return `<section class="pdf-environment"><h2>Files</h2><p>${escape(state.environmentError || 'Loading files and tool information…')}</p></section>`;
  const url = asset => `${state.origin}/api/chats/${state.chat.id}/assets/${asset.id}`;
  const preview = env.assets.find(a => a.id === state.previewAsset);
  const results = env.assets.filter(a => a.operation_id && a.kind === 'pdf');
  const latest = results.at(-1);
  return `<section class="pdf-environment" aria-label="Conversation files">
  ${state.environmentLoading ? '<p class="notice" role="status">Refreshing files and tool information…</p>' : ''}
  ${showResult && latest ? `<article class="file-result ${latest.verification?.passed === false ? 'result-failed' : ''}"><div><span class="result-state">${latest.verification?.passed === false ? 'Incomplete document' : latest.verification?.passed ? 'Document ready' : 'Document created'}</span><strong>${escape(latest.name)}</strong><span>${latest.page_count} ${latest.page_count === 1 ? 'page' : 'pages'}</span></div><button type="button" data-action="preview-pdf" data-id="${escape(latest.id)}">Preview</button><a href="${escape(url(latest) + '/content')}" download>Download</a></article>` : ''}
  <details class="file-library" data-key="file-library"><summary>Files <span>${env.assets.length}</span></summary>${fileControls(busy)}
  <div class="pdf-files">${env.assets.length ? env.assets.map(a => `<article class="pdf-file"><div><strong>${escape(a.name)}</strong><p>${a.kind === 'brief' ? 'Source brief' : `${a.page_count} ${a.page_count === 1 ? 'page' : 'pages'}`} ${a.verification ? `· ${a.verification.passed ? 'Content checks passed' : 'Content checks failed'}` : ''}</p></div><div class="pdf-file-actions">${a.kind === 'pdf' ? `<button type="button" data-action="preview-pdf" data-id="${escape(a.id)}">Preview</button>` : ''}<a href="${escape(url(a) + '/content')}" download>Download</a></div>${a.verification && !a.verification.passed ? `<details><summary>What is missing?</summary><ul>${a.verification.checks.filter(c => !c.passed).map(c => `<li>${escape(c.name.replaceAll('_', ' '))}${c.missing?.length ? `: ${escape(c.missing.slice(0, 4).join('; '))}` : ''}</li>`).join('')}</ul></details>` : ''}</article>`).join('') : '<p class="pdf-empty">Add a demo pack or upload PDFs to start. Adding files does not run an agent.</p>'}</div>
  </details>
  ${!env.runtime.available ? `<p class="notice">${escape(env.runtime.reason)}</p>` : ''}${state.environmentError ? `<p role="alert">${escape(state.environmentError)}</p>` : ''}
  ${preview ? `<section class="pdf-preview"><div class="pdf-preview-toolbar"><strong>${escape(preview.name)}</strong><button type="button" data-action="close-preview">Close preview</button></div><img src="${escape(url(preview) + '/pages/' + (state.previewPage || 1))}" alt="Actual rendered page ${state.previewPage || 1} of ${escape(preview.name)}"><div class="pdf-preview-toolbar"><button type="button" data-action="previous-page" ${(state.previewPage || 1) <= 1 ? 'disabled' : ''}>Previous page</button><span>Page ${state.previewPage || 1} of ${preview.page_count}</span><button type="button" data-action="next-page" ${(state.previewPage || 1) >= preview.page_count ? 'disabled' : ''}>Next page</button></div></section>` : ''}
  ${showTools ? `<details class="disclosure" data-key="pdf-tools"><summary>Tool details</summary><ul>${env.tools.map(t => `<li><code>${escape(t.name)}</code> — ${escape(t.description)}</li>`).join('')}</ul><pre>${escape(JSON.stringify({active_version: env.active_version, versions: env.versions?.versions || []}, null, 2))}</pre>${env.active_version !== 'builtin' ? `<button type="button" data-action="rollback-pdf" ${busy ? 'disabled' : ''}>Restore previous tool version</button>` : ''}</details>` : ''}</section>`;
}
