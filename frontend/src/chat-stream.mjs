import { apiOrigin } from './intake-api.mjs';

const terminal = new Set(['completed', 'failed', 'cancelled', 'interrupted']);
export class ChatStream {
  constructor({ origin, chat, operation, onUpdate, onFinish, onIssue,
    factory = url => new EventSource(url, { withCredentials: false }) }) {
    this.chat = chat; this.operation = operation; this.sequence = -1; this.closed = false;
    this.state = { operation_id: operation, text: '', block: 0, status: 'running', activity: 'Starting Hermes' };
    this.onUpdate = onUpdate; this.onFinish = onFinish; this.onIssue = onIssue;
    this.source = factory(`${apiOrigin(origin)}/api/chats/${encodeURIComponent(chat)}/operations/${encodeURIComponent(operation)}/events`);
    for (const type of ['snapshot', 'stage', 'answer_delta', 'answer_reset', 'complete', 'unavailable']) {
      this.source.addEventListener(type, event => this.receive(type, event));
    }
    this.source.onerror = () => {
      if (!this.closed) this.onIssue('Live connection interrupted. Reconnecting; saved messages continue to refresh.');
    };
  }

  receive(type, event) {
    if (this.closed) return;
    try {
      const frame = JSON.parse(event.data), data = frame.data;
      if (frame.chat_id !== this.chat || frame.operation_id !== this.operation || frame.type !== type
          || !Number.isSafeInteger(frame.sequence) || frame.sequence < 0 || !data || typeof data !== 'object') throw new Error('Live response identity could not be confirmed.');
      if (type === 'unavailable') {
        this.close(); this.onIssue('Live preview unavailable. Reading the saved conversation.');
        this.onFinish(); return;
      }
      if (type !== 'snapshot' && frame.sequence <= this.sequence) return;
      if (type !== 'snapshot' && frame.sequence !== this.sequence + 1) throw new Error('Live response sequence changed. Reading the saved conversation.');
      if (type === 'snapshot') {
        if (typeof data.text !== 'string' || data.text.length > 256000 || !Number.isSafeInteger(data.block)) throw new Error('Live snapshot is unavailable.');
        this.state = { ...data, operation_id: this.operation };
      } else if (type === 'answer_delta') {
        if (data.block !== this.state.block || typeof data.text !== 'string') throw new Error('Live response block changed.');
        this.state.text = (this.state.text + data.text).slice(0, 256000);
        this.state.truncated = data.truncated;
      } else if (type === 'answer_reset') {
        if (!Number.isSafeInteger(data.block) || data.block <= this.state.block) throw new Error('Invalid response boundary.');
        Object.assign(this.state, { text: '', block: data.block, truncated: false });
      } else {
        if (data.activity !== undefined && typeof data.activity !== 'string') throw new Error('Invalid progress event.');
        Object.assign(this.state, data);
      }
      this.sequence = frame.sequence;
      this.onUpdate({ ...this.state });
      if (terminal.has(this.state.status)) { this.close(); this.onFinish(this.state); }
    } catch (error) {
      this.close(); this.onIssue(error.message); this.onFinish();
    }
  }

  close() { this.closed = true; this.source.close(); }
}
