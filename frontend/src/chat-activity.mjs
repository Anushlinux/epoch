import { escape, icon } from './ui.mjs';
const toolLabels = {
  'documents.list': 'Finding your files', 'documents.read': 'Reading the brief',
  'documents.inspect': 'Checking the document', 'pdf.create': 'Creating the PDF',
  'pdf.merge': 'Combining the documents', 'capabilities.request': 'Recording a missing tool',
};
export function activityView(state, debuggerMode = false) {
  const op = state.chat?.operations.find(o => o.status === 'running');
  if (!op) return '';
  const live = state.stream?.operation_id === op.id ? state.stream : null;
  let text = live?.activity || op.activity || 'Working';
  const isDebugger = op.kind === 'debugger';
  if (!isDebugger && !live && !op.stage) {
    const events = (state.environment?.events || []).filter(e => e.operation_id === op.id);
    const event = events.at(-1), p = event?.payload || {};
    if (event?.type === 'tool.called') text = toolLabels[p.tool_name] || 'Using a tool';
    else if (event?.type === 'executor.tool_started') {
      const args = p.arguments || {};
      text = toolLabels[args.tool_name || args.name] || (String(p.name).includes('discover') ? 'Finding available tools' : 'Using a tool');
    } else if (event?.type === 'executor.model_request' || event?.type === 'executor.step') text = 'Working on your request';
  }
  const label = live || op.stage ? text : text.startsWith('Hermes') || text.startsWith('Debugger') ? text : `${isDebugger ? 'Debugger' : 'Hermes'} · ${text}`;
  return `<div class="chat-working" role="status" aria-live="polite">${icon('activity')}<span id="chat-live-stage">${escape(label)}</span>${debuggerMode ? `<button type="button" data-action="stop" ${state.busy ? 'disabled' : ''}>Stop</button>` : ''}</div>`;
}
