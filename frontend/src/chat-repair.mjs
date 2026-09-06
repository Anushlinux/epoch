import { escape } from './ui.mjs';
import { activityView } from './chat-activity.mjs';
export function repairView(state, blocked) {
  if (state.chat?.environment !== 'pdf_workshop') return '';
  const actions = state.environment?.actions || [];
  const current = state.chat.operations.filter(o => ['repair_tool', 'create_tool'].includes(o.action)).at(-1);
  const running = state.chat.operations.some(o => o.status === 'running');
  const available = actions.some(a => a.eligible);
  const failed = state.environment?.assets.filter(a => a.verification?.passed === false).at(-1);
  const title = running ? 'Repair in progress' : current?.status === 'completed' ? 'Repair completed' : current?.status === 'failed' ? 'Repair stopped' : current?.status === 'cancelled' ? 'Repair cancelled' : current?.status === 'interrupted' ? 'Repair interrupted' : available ? 'Ready to fix' : 'Waiting for a task';
  const description = running ? '' : current?.analysis?.answer || (available ? (failed ? `${failed.name} did not pass its checks.` : 'This request needs a tool that is not available yet.') : 'Run a task in chat to capture its results.');
  return `<section class="debugger-action pdf-repair-action"><h2>${title}</h2>${description ? `<p class="repair-summary">${escape(description)}</p>` : ''}${activityView(state, true)}
  ${!running ? actions.map(a => `<div class="pdf-repair-choice"><button type="button" class="primary-action" data-action="pdf-environment-action" data-kind="${escape(a.action)}" ${blocked || !a.eligible || !state.runtime?.debugger?.available ? 'disabled' : ''}>${a.action === 'repair_tool' ? 'Fix PDF tool' : 'Create merge tool'}</button>${!a.eligible ? `<span>${escape(a.reason)}</span>` : ''}</div>`).join('') : ''}
  ${!state.runtime?.debugger?.available ? '<p class="notice">Debugger is unavailable. Check the connection settings.</p>' : ''}
  ${current?.error ? `<p role="alert">${escape(current.error.message)}</p>` : ''}
  ${current?.analysis?.published_version && current.status !== 'completed' ? '<p>Tool published. Task recovery is not complete.</p>' : ''}
  ${current?.analysis?.attempts?.length ? `<details class="disclosure" data-key="repair-checks"><summary>Changes and verification</summary>${current.analysis.attempts.map(a => `<details class="disclosure" data-key="pdf-attempt-${a.number}"><summary>Candidate ${a.number} · ${escape(a.status)}</summary><ul>${(a.proofs || []).map(p => `<li>${escape(p.kind.replaceAll('_',' '))}: ${p.passed ? 'Passed' : 'Failed'}</li>`).join('')}</ul><pre>${escape(a.diff || 'Source is being generated.')}</pre>${a.error ? `<p>${escape(a.error)}</p>` : ''}</details>`).join('')}</details>` : ''}</section>`;
}
