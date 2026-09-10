import { IntakeAPI } from './intake-api.mjs';

export class TraceAPI extends IntakeAPI {
  async chatContext(chat, trace = '') {
    const query = trace ? `?trace_id=${encodeURIComponent(trace)}` : '';
    const { body } = await this.call(`/api/chats/${encodeURIComponent(chat)}/trace-context${query}`);
    if (body.chat_id !== chat || typeof body.title !== 'string') throw new Error('Conversation trace context is unavailable.');
    return body;
  }

  async questionRuntime() {
    const { body } = await this.call('/api/trace-questions/runtime');
    if (body.provider !== 'ollama' || typeof body.available !== 'boolean') throw new Error('Local question service is unavailable.');
    return body;
  }

  async questions(trace, offset = 0) {
    const { body } = await this.call(`/api/traces/${encodeURIComponent(trace)}/questions?limit=5&offset=${offset}`);
    if (!Array.isArray(body.items)) throw new Error('Question history is unavailable.');
    return body;
  }

  async question(trace, id) {
    const { body } = await this.call(`/api/traces/${encodeURIComponent(trace)}/questions/${encodeURIComponent(id)}`);
    if (body.trace_id !== trace || body.id !== id) throw new Error('The answer does not match this question.');
    return body;
  }

  async ask(trace, payload) {
    const { body } = await this.call(`/api/traces/${encodeURIComponent(trace)}/questions`, payload);
    if (body.trace_id !== trace || body.id !== payload.client_request_id) throw new Error('The submission acknowledgement could not be confirmed.');
    return body;
  }

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
