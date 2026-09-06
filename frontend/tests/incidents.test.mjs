import test from 'node:test';
import assert from 'node:assert/strict';
import { IncidentAPI, IncidentWorkspace, INCIDENT_PENDING_KEY, importPayload } from '../src/incident-api.mjs';
import { incidentsView } from '../src/incident-ui.mjs';

const id = crypto.randomUUID(), evidenceId = crypto.randomUUID();
const report = { source_type: 'support', source_id: 'ticket-1', timestamp: '2026-09-06T10:00:00Z', project_id: 'demo', text: '<script>Untrusted report</script>' };
const incident = () => ({ id, title: 'Checklist failure', status: 'open', project_id: 'demo', workflow: 'release', run_ids: [], evidence_count: 1, evidence: [{ ...report, id: evidenceId, trusted: false }], decisions: [{ evidence_id: evidenceId, decision: 'included', reasons: ['Project and run association'] }], repairs: [], recurrence: { before: { affected: 1, comparable: 2 }, after: { affected: 0, comparable: 0 }, recovered_runs: 0, verification_runs: 0, excluded_runs: 3 }, analyses: [{ status: 'completed', answer: 'A report exists; cause is unknown.', evidence_ids: [evidenceId, 'missing-id'], hypotheses: ['Possible adapter failure'], missing_evidence: ['Live service evidence'] }], warnings: [] });
const memory = () => { const map = new Map(); return { getItem: (key) => map.get(key) ?? null, setItem: (key, value) => map.set(key, value), removeItem: (key) => map.delete(key) }; };
function setup(t, storage = memory(), write) {
  const calls = [];
  const api = { list: async () => { calls.push('list'); return { items: [incident()], total: 1, warnings: [] }; }, detail: async () => incident(), telemetry: async () => ({ collector_ready: true }), write: write || (async (pending) => { calls.push(pending); return { id: pending.payload.client_request_id, status: 'completed' }; }) };
  const w = new IncidentWorkspace({ storage, apiFactory: () => api, pollMs: 60000 });
  t.after(() => w.stop());
  w.setContext('http://127.0.0.1:8000', true, true, id);
  return { w, calls, storage };
}
test('JSON imports require real external records and preserve supplied source identity', () => {
  assert.deepEqual(importPayload(JSON.stringify([report])).records, [report]);
  assert.throws(() => importPayload('{invalid'), /valid JSON/);
  assert.throws(() => importPayload(JSON.stringify([{ ...report, source_type: 'epoch' }])), /slack or support/);
  assert.throws(() => importPayload('[]'), /between 1 and 200/);
});
test('incident reads do not trigger models and stop polling when hidden', async (t) => {
  const { w, calls } = setup(t); await w.refresh();
  assert.deepEqual(calls, ['list']);
  assert.ok(w.timer);
  w.setContext(w.state.origin, true, false, id);
  await w.refresh();
  assert.equal(w.timer, null); assert.deepEqual(calls, ['list']);
});
test('unknown analysis acknowledgement survives reload and retries exactly once on explicit action', async (t) => {
  let submitted;
  const first = setup(t, memory(), async (value) => { submitted = structuredClone(value); throw new Error('Lost response'); });
  await first.w.refresh(); await first.w.submit('questions', 'Why did this fail?');
  assert.match(first.w.state.error, /Acknowledgement is unknown/);
  assert.deepEqual(JSON.parse(first.storage.getItem(INCIDENT_PENDING_KEY)), submitted);
  const second = setup(t, first.storage); await second.w.refresh();
  assert.deepEqual(second.calls, ['list']);
  await second.w.submit('analyze'); assert.deepEqual(second.calls, ['list']);
  await second.w.retry();
  assert.deepEqual(second.calls.find((value) => typeof value === 'object'), submitted);
  assert.equal(first.storage.getItem(INCIDENT_PENDING_KEY), null);
});
test('incident response must acknowledge the retained request identity', async () => {
  const api = new IncidentAPI('http://localhost:8000', async () => new Response(JSON.stringify({ id: crypto.randomUUID(), status: 'completed', evidence_ids: [], hypotheses: [], missing_evidence: [] })));
  await assert.rejects(api.write({ endpoint: `/api/incidents/${id}/analyze`, kind: 'analyze', payload: { client_request_id: crypto.randomUUID() } }), /acknowledgement/);
});
test('incident view separates trusted facts, reports, recurrence and cited explanations', () => {
  const html = incidentsView({ connected: true, incident: incident(), list: { items: [incident()], total: 1 }, selected: id, project: '', offset: 0, telemetry: { collector_ready: true, cloud_enabled: false, cloud_export_accepted: true, cloud_readback_verified: false } });
  for (const text of ['Untrusted observation', 'Project and run association', '1 affected / 2 comparable', 'Excluded runs: 3', 'Cloud export: disabled', 'Cloud export accepted: recorded', 'Cloud readback: not verified', 'A report exists', 'Cited evidence unavailable: missing-id']) assert.ok(html.includes(text), text);
  assert.ok(html.includes(`href="#evidence-${evidenceId}"`));
  assert.doesNotMatch(html, /<script>/);
});

test('local trace references use the configured backend origin and unsafe sources stay text', () => {
  const value = incident();
  value.evidence[0].source_ref = '/api/telemetry/traces/abcdef/spans/012345';
  const state = { incident: value, origin: 'http://127.0.0.1:8123' };
  assert.match(incidentsView(state), /href="http:\/\/127\.0\.0\.1:8123\/api\/telemetry\/traces\/abcdef\/spans\/012345"/);
  value.evidence[0].source_ref = 'javascript:alert(1)';
  assert.doesNotMatch(incidentsView(state), /href="javascript:/);
});
