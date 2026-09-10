import { IntakeAPI } from './intake-api.mjs';

export class TraceAPI extends IntakeAPI {
  async runtime() {
    const { body } = await this.call('/api/telemetry/runtime');
    if (typeof body.collector_ready !== 'boolean') throw new Error('Collector response is unavailable.');
    if (!body.trace_index) throw new Error('Restart the updated backend to enable the trace explorer.');
    return body;
  }

  async list(params) {
    const query = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== '' && value !== null && value !== undefined) query.set(key, String(value));
    }
    const { body } = await this.call(`/api/traces?${query}`);
    if (!Array.isArray(body.items)) throw new Error('Trace list response is unavailable.');
    return body;
  }

  async trace(id, offset = 0) {
    const { body } = await this.call(`/api/traces/${encodeURIComponent(id)}?limit=200&offset=${offset}`);
    if (!body.trace || !Array.isArray(body.spans)) throw new Error('Trace detail response is unavailable.');
    return body;
  }

  async span(trace, span, raw = false) {
    const prefix = raw ? '/api/telemetry/traces' : '/api/traces';
    const { body } = await this.call(`${prefix}/${encodeURIComponent(trace)}/spans/${encodeURIComponent(span)}`);
    if (body.trace_id !== trace || body.span_id !== span) throw new Error('The span response does not match this selection.');
    return body;
  }
}
