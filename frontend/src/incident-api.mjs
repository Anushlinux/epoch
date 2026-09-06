import { IntakeAPI, IntakeError, apiOrigin } from './intake-api.mjs';

export const INCIDENT_PENDING_KEY = 'epoch.incident.pending.v1';
const object = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
const uuid = (value) => typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
const strings = (value) => Array.isArray(value) && value.every((item) => typeof item === 'string');
const ensure = (condition, message = 'The incident response does not match the server contract.') => { if (!condition) throw new IntakeError(message, 0, 'contract'); };
export function incidentRecord(value) {
  ensure(object(value) && uuid(value.id) && typeof value.title === 'string' && typeof value.project_id === 'string' && ['open', 'monitoring'].includes(value.status) && strings(value.run_ids) && Number.isInteger(value.evidence_count));
  return value;
}
export function importPayload(text, id = crypto.randomUUID()) {
  let parsed;
  try { parsed = JSON.parse(text); } catch { throw new IntakeError('Enter valid JSON containing an array of Slack or support records.'); }
  const records = Array.isArray(parsed) ? parsed : parsed?.records;
  ensure(Array.isArray(records) && records.length > 0 && records.length <= 200, 'Provide between 1 and 200 Slack or support records.');
  for (const record of records) {
    ensure(object(record) && ['slack', 'support'].includes(record.source_type) && ['source_id', 'timestamp', 'project_id', 'text'].every((key) => typeof record[key] === 'string' && record[key].trim()) && Number.isFinite(Date.parse(record.timestamp)), 'Every record needs source_type (slack or support), source_id, timestamp, project_id and text.');
  }
  return { client_request_id: id, records };
}
function pendingRecord(value) {
  ensure(object(value) && value.version === 1 && ['import', 'analyze', 'questions'].includes(value.kind) && object(value.payload) && uuid(value.payload.client_request_id));
  const endpoint = value.kind === 'import' ? '/api/evidence/import' : `/api/incidents/${value.incidentId}/${value.kind}`;
  ensure(value.endpoint === endpoint && (value.kind === 'import' || uuid(value.incidentId)));
  return { ...value, origin: apiOrigin(value.origin) };
}
export class IncidentAPI extends IntakeAPI {
  constructor(origin, fetcher) { super(origin, fetcher, 70000); }
  async list(project = '', offset = 0) {
    const query = new URLSearchParams({ limit: '50', offset: String(offset) });
    if (project) query.set('project_id', project);
    const { body } = await this.call(`/api/incidents?${query}`);
    ensure(object(body) && Array.isArray(body.items) && Number.isInteger(body.total) && strings(body.warnings));
    body.items.forEach(incidentRecord); return body;
  }
  async detail(id) {
    ensure(uuid(id), 'The incident ID is invalid.');
    const { body } = await this.call(`/api/incidents/${id}`);
    incidentRecord(body);
    ensure(body.id === id && ['evidence', 'decisions', 'repairs', 'analyses', 'warnings'].every((key) => Array.isArray(body[key])) && object(body.recurrence));
    return body;
  }
  async telemetry() { const { body } = await this.call('/api/telemetry/runtime'); ensure(object(body)); return body; }
  async write(pending) {
    const { body } = await this.call(pending.endpoint, pending.payload);
    ensure(object(body) && body.id === pending.payload.client_request_id, 'The acknowledgement does not match the saved incident request. Retain its ID for recovery.');
    if (pending.kind === 'import') ensure(Number.isInteger(body.imported) && Number.isInteger(body.deduplicated) && strings(body.evidence_ids) && strings(body.incident_ids));
    else ensure(typeof body.status === 'string' && strings(body.evidence_ids) && Array.isArray(body.hypotheses) && Array.isArray(body.missing_evidence));
    return body;
  }
}

// Reads may repeat while this page is visible. Writes require an explicit action and a retained identity.
export class IncidentWorkspace {
  constructor({ storage, apiFactory = (origin) => new IncidentAPI(origin), onChange = () => {}, pollMs = 5000 }) {
    Object.assign(this, { storage, apiFactory, onChange, pollMs });
    this.generation = 0; this.context = ''; this.timer = null;
    this.state = { origin: '', connected: false, visible: false, selected: '', project: '', offset: 0, list: null, incident: null, telemetry: null, loading: false, busy: false, pending: null, rejected: false, recovery: false, error: '', notice: '', warnings: [] };
    try { const raw = storage.getItem(INCIDENT_PENDING_KEY); if (raw) this.state.pending = pendingRecord(JSON.parse(raw)); }
    catch { this.state.recovery = true; this.state.error = 'Saved incident action is unavailable or corrupt. New incident writes are blocked.'; }
  }
  stop() { clearTimeout(this.timer); this.timer = null; this.generation++; this.refreshing = null; }
  setContext(origin, connected, visible, selected = '', project = '', offset = 0) {
    const key = JSON.stringify([origin, connected, visible, selected, project, offset]);
    if (key === this.context) return;
    this.context = key; this.stop();
    const changedOrigin = this.state.origin !== origin;
    if (changedOrigin || this.state.selected !== selected) this.state.incident = null;
    if (changedOrigin || this.state.project !== project) this.state.list = null;
    if (changedOrigin) this.state.telemetry = null;
    Object.assign(this.state, { origin, connected, visible, selected, project, offset });
    if (connected && visible) { this.api = this.apiFactory(origin); void this.refresh(); }
  }
  async refresh() {
    const s = this.state;
    if (!s.connected || !s.visible || this.refreshing) return this.refreshing;
    clearTimeout(this.timer); const generation = this.generation, api = this.api;
    s.loading = true;
    this.refreshing = Promise.resolve().then(async () => {
      const results = await Promise.allSettled([api.list(s.project, s.offset), s.selected ? api.detail(s.selected) : Promise.resolve(null), api.telemetry()]);
      if (generation !== this.generation) return;
      s.warnings = [];
      results.forEach((result, index) => {
        const key = ['list', 'incident', 'telemetry'][index];
        if (result.status === 'fulfilled') s[key] = result.value;
        else s.warnings.push(`${key}: ${result.reason.message}`);
      });
    }).finally(() => {
      if (generation !== this.generation) return;
      this.refreshing = null; s.loading = false; this.onChange();
      if (s.connected && s.visible) this.timer = setTimeout(() => void this.refresh(), this.pollMs);
    });
    return this.refreshing;
  }
  async submit(kind, input = '') {
    const s = this.state;
    if (s.busy || s.pending || s.recovery || !s.connected) return false;
    try {
      ensure(['import', 'analyze', 'questions'].includes(kind));
      const payload = kind === 'import' ? importPayload(input) : { client_request_id: crypto.randomUUID(), ...(kind === 'questions' ? { question: input.trim() } : {}) };
      ensure(kind !== 'questions' || payload.question.length > 0, 'Enter a question about this incident.');
      const value = pendingRecord({ version: 1, origin: s.origin, kind, incidentId: kind === 'import' ? null : s.selected, endpoint: kind === 'import' ? '/api/evidence/import' : `/api/incidents/${s.selected}/${kind}`, payload });
      this.storage.setItem(INCIDENT_PENDING_KEY, JSON.stringify(value));
      s.pending = value; s.rejected = false;
    } catch (error) { s.error = `Nothing was sent. ${error.message}`; this.onChange(); return false; }
    return this.retry();
  }
  async retry() {
    const s = this.state, pending = s.pending;
    if (s.busy || s.recovery || s.rejected || !s.connected || !pending || pending.origin !== s.origin) return false;
    s.busy = true; s.error = ''; s.notice = ''; this.onChange();
    try {
      const result = await this.api.write(pending);
      this.storage.removeItem(INCIDENT_PENDING_KEY); s.pending = null;
      s.notice = pending.kind === 'import' ? `Imported ${result.imported} records; ${result.deduplicated} duplicates retained existing evidence.` : `Incident action recorded: ${result.status}. Inspect the answer, citations and missing evidence below.`;
      return true;
    } catch (error) {
      s.rejected = [400, 403, 404, 409, 413, 422].includes(error.status);
      s.error = s.rejected ? `${error.message} The rejected request is retained for review.` : `${error.message} Acknowledgement is unknown. Retry only the saved request; no automatic model retry occurs.`;
      return false;
    } finally { s.busy = false; this.onChange(); await this.refresh(); }
  }
  reviewRejected() {
    if (!this.state.rejected || this.state.busy) return;
    try { this.storage.removeItem(INCIDENT_PENDING_KEY); this.state.pending = null; this.state.rejected = false; this.state.error = ''; }
    catch { this.state.error = 'Unable to clear the rejected request. Restore browser storage first.'; }
    this.onChange();
  }
}
