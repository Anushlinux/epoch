// Context survives page changes and browser history without a second session store.
export const chatID = value => /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(value || '');
export function tracesURL(chat = '', operation = null) {
  const query = new URLSearchParams();
  if (chatID(chat)) { query.set('chat', chat); query.set('session_id', chat); }
  if (/^[0-9a-f]{32}$/.test(operation?.trace_id || '')) query.set('trace', operation.trace_id);
  // The root is exported at completion. Let active users inspect already-ended tools.
  if (operation?.trace_capture === 'stored' && /^[0-9a-f]{16}$/.test(operation.trace_span_id || '')) query.set('span', operation.trace_span_id);
  return `/traces${query.size ? `?${query}` : ''}`;
}
