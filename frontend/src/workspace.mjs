// Keep the conversation controller completely separate from evaluation controls.
const query = new URLSearchParams(location.search);
const chatRoute = ['/chat', '/', '/index.html'].includes(location.pathname);
const investigationRoute = location.pathname === '/debugger' && !query.has('task') && query.get('mode') !== 'release';
if (chatRoute && query.has('task')) {
  location.replace(`/debugger?task=${encodeURIComponent(query.get('task'))}`);
} else if (chatRoute || investigationRoute) {
  await import('./chat-ui.mjs');
} else {
  await import('./intake.mjs');
}
