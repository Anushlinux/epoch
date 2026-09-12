import { escape } from './ui.mjs';

// Presentation only: source values are never mutated. JSON number lexemes stay
// strings internally so IDs, large integers and precise decimals are not rounded.
class JsonNumber {
  constructor(text) { this.text = text; }
}
class PreviewOmitted {}
const LIMITS = { parseChars: 256_000, nodes: 3_000, depth: 16, fields: 60, items: 40, text: 16_000, totalText: 64_000 };
const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value) && !(value instanceof JsonNumber) && !(value instanceof PreviewOmitted);
const priority = new Set(['error', 'errors', 'isError', 'ok', 'status', 'status_message']);
const entries = value => Object.entries(value).sort(([a], [b]) => Number(priority.has(b)) - Number(priority.has(a)));

function parseJson(text) {
  let at = 0, nodes = 0;
  const fail = () => { throw new Error('Unreadable preview JSON'); };
  const whitespace = () => { while (/[\x20\t\r\n]/.test(text[at] || '\0')) at++; };
  function quoted() {
    const start = at++;
    while (at < text.length) {
      const char = text[at++];
      if (char === '\\') at++;
      else if (char === '"') return JSON.parse(text.slice(start, at));
    }
    fail();
  }
  function value(depth) {
    if (++nodes > LIMITS.nodes || depth > LIMITS.depth) fail();
    whitespace();
    const char = text[at];
    if (char === '"') return quoted();
    if (char === '{' || char === '[') {
      const array = char === '[', end = array ? ']' : '}';
      const result = array ? [] : Object.create(null);
      at++;
      whitespace();
      if (text[at] === end) { at++; return result; }
      while (at < text.length) {
        whitespace();
        let key;
        if (!array) {
          if (text[at] !== '"') fail();
          key = quoted();
          // Do not silently discard duplicate fields in captured evidence.
          if (own(result, key)) fail();
          whitespace();
          if (text[at++] !== ':') fail();
        }
        const child = value(depth + 1);
        if (array) result.push(child); else result[key] = child;
        whitespace();
        const next = text[at++];
        if (next === end) return result;
        if (next !== ',') fail();
      }
      fail();
    }
    for (const [literal, result] of [['true', true], ['false', false], ['null', null]]) {
      if (text.startsWith(literal, at)) { at += literal.length; return result; }
    }
    const number = text.slice(at).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (!number) fail();
    at += number[0].length;
    return new JsonNumber(number[0]);
  }
  const result = value(0);
  whitespace();
  if (at !== text.length) fail();
  return result;
}

function prepare(value, context, depth = 0) {
  if (++context.nodes > LIMITS.nodes || depth > LIMITS.depth) {
    context.shortened = true;
    return new PreviewOmitted();
  }
  if (typeof value === 'string') {
    // Decode JSON envelopes, including quoted JSON inside MCP text results.
    // Ordinary prose (including invalid JSON) is left exactly as recorded.
    for (let layer = 0; layer < 8 && typeof value === 'string'; layer++) {
      const candidate = value.trim();
      if (!['{', '[', '"'].includes(candidate[0])) break;
      if (candidate.length > context.parseChars) { context.shortened = true; break; }
      context.parseChars -= candidate.length;
      try { value = parseJson(candidate); } catch { break; }
    }
    if (typeof value === 'string') {
      const limit = Math.min(LIMITS.text, context.textLeft);
      if (value.length > limit) { context.shortened = true; value = value.slice(0, limit) + '\n[Preview shortened]'; }
      context.textLeft = Math.max(0, context.textLeft - value.length);
      return value;
    }
  }
  if (value instanceof JsonNumber) {
    if (value.text.length > LIMITS.text || value.text.length > context.textLeft) {
      context.shortened = true;
      return new PreviewOmitted();
    }
    context.textLeft -= value.text.length;
    return value;
  }
  if (value === null || typeof value !== 'object') return value;
  if (context.seen.has(value)) { context.shortened = true; return new PreviewOmitted(); }
  context.seen.add(value);
  if (Array.isArray(value)) {
    const result = value.slice(0, LIMITS.items).map(item => prepare(item, context, depth + 1));
    if (value.length > LIMITS.items) { context.shortened = true; result.push(new PreviewOmitted()); }
    return result;
  }
  const result = Object.create(null), fields = entries(value);
  for (const [key, child] of fields.slice(0, LIMITS.fields)) {
    if (key.length > 1_024) { context.shortened = true; continue; }
    result[key] = prepare(child, context, depth + 1);
  }
  if (fields.length > LIMITS.fields) context.shortened = true;
  return result;
}

function plain(value) {
  if (value instanceof JsonNumber) return value.text;
  if (value instanceof PreviewOmitted) return '[Preview shortened]';
  if (value === undefined) return 'Not recorded';
  return typeof value === 'string' ? value : pretty(value);
}

function pretty(value, level = 0) {
  if (value instanceof JsonNumber) return value.text;
  if (value instanceof PreviewOmitted) return '"[Preview shortened]"';
  if (value === undefined) return '"[Not recorded]"';
  if (typeof value === 'bigint') return String(value);
  if (value === null || typeof value !== 'object') return JSON.stringify(value);
  const indent = '  '.repeat(level), next = indent + '  ';
  const parts = Array.isArray(value) ? value.map(child => pretty(child, level + 1)) : Object.entries(value).map(([key, child]) => `${JSON.stringify(key)}: ${pretty(child, level + 1)}`);
  const [start, end] = Array.isArray(value) ? ['[', ']'] : ['{', '}'];
  return parts.length ? `${start}\n${next}${parts.join(',\n' + next)}\n${indent}${end}` : start + end;
}

function schemaType(schema, depth = 0) {
  if (!object(schema) || depth > 5) return 'See schema';
  if (typeof schema.type === 'string') return schema.type;
  if (Array.isArray(schema.type)) return schema.type.map(plain).join(' or ');
  const alternatives = schema.anyOf || schema.oneOf;
  if (Array.isArray(alternatives)) return [...new Set(alternatives.map(item => schemaType(item, depth + 1)))].join(' or ');
  if (typeof schema.$ref === 'string') return `Reference: ${schema.$ref.split('/').pop()}`;
  return 'See schema';
}

function toolSchema(value) {
  if (!object(value) || typeof value.name !== 'string' || typeof value.description !== 'string') return null;
  for (const key of ['input_schema', 'inputSchema', 'schema']) {
    const schema = value[key];
    if (object(schema) && (schema.type === 'object' || object(schema.properties))) return { schema, key };
  }
  return null;
}

function formattedJson(value) {
  return `<pre class="trace-readable-json" tabindex="0">${escape(pretty(value))}</pre>`;
}

function toolDescription(value, { schema, key: schemaKey }, context, depth) {
  const properties = object(schema.properties) ? Object.entries(schema.properties) : [];
  const required = new Set(Array.isArray(schema.required) ? schema.required.filter(item => typeof item === 'string') : []);
  const rows = properties.map(([name, parameter]) => {
    const spec = object(parameter) ? parameter : {};
    const choices = Array.isArray(spec.enum) ? `<p class="trace-tool-choices">Choices: ${spec.enum.map(item => `<code>${escape(plain(item))}</code>`).join(', ')}</p>` : '';
    const defaultValue = own(spec, 'default') ? `<p class="trace-tool-default">Default: <code>${escape(plain(spec.default))}</code></p>` : '';
    return `<tr><th scope="row"><code>${escape(name)}</code><span class="trace-tool-required">${required.has(name) ? 'Required' : 'Optional'}</span></th><td><span class="trace-tool-type">${escape(schemaType(spec))}</span>${typeof spec.description === 'string' ? `<p class="trace-readable-prose">${escape(spec.description)}</p>` : ''}${choices}${defaultValue}</td></tr>`;
  }).join('');
  const extra = Object.fromEntries(Object.entries(value).filter(([key]) => !['name', 'description', schemaKey].includes(key)));
  const statuses = Object.fromEntries(Object.entries(extra).filter(([key]) => priority.has(key)));
  const metadata = Object.fromEntries(Object.entries(extra).filter(([key]) => !priority.has(key)));
  return `<article class="trace-tool-description"><header><span class="trace-readable-label">Tool</span><h5>${escape(value.name)}</h5></header><p class="trace-readable-prose">${escape(value.description)}</p>${Object.keys(statuses).length ? renderValue(statuses, context, depth + 1) : ''}<h6>Parameters</h6>${rows ? `<div class="trace-tool-table-wrap"><table class="trace-tool-table"><thead><tr><th scope="col">Parameter</th><th scope="col">Details</th></tr></thead><tbody>${rows}</tbody></table></div>` : '<p class="trace-readable-empty">No parameters listed.</p>'}<details class="trace-readable-details" data-key="${escape(context.key + '-schema-' + context.detail++)}"><summary>Full schema</summary>${formattedJson(schema)}</details>${Object.keys(metadata).length ? `<details class="trace-readable-details" data-key="${escape(context.key + '-metadata-' + context.detail++)}"><summary>Tool metadata</summary>${renderValue(metadata, context, depth + 1)}</details>` : ''}</article>`;
}

function renderValue(value, context, depth = 0) {
  if (value instanceof PreviewOmitted) return '<p class="trace-readable-empty">Additional content is available in Original evidence.</p>';
  if (value === null) return '<span class="trace-readable-empty">null</span>';
  if (value === undefined) return '<span class="trace-readable-empty">Not recorded</span>';
  if (value instanceof JsonNumber) return `<code>${escape(value.text)}</code>`;
  if (typeof value === 'string') return value.length ? `<div class="trace-readable-prose">${escape(value)}</div>` : '<span class="trace-readable-empty">Empty text</span>';
  if (typeof value !== 'object') return `<code>${escape(String(value))}</code>`;
  if (depth > 7) return formattedJson(value);
  const schema = toolSchema(value);
  if (schema) return toolDescription(value, schema, context, depth);
  if (Array.isArray(value)) {
    if (!value.length) return '<span class="trace-readable-empty">Empty list</span>';
    return `<ol class="trace-readable-list">${value.map(item => `<li>${renderValue(item, context, depth + 1)}</li>`).join('')}</ol>`;
  }
  const fields = entries(value);
  if (!fields.length) return '<span class="trace-readable-empty">Empty object</span>';
  // Exact transport-only envelopes can be removed without dropping status or
  // error information. Any additional field keeps the whole object visible.
  if (fields.length === 1 && ['result', 'content'].includes(fields[0][0])) return renderValue(fields[0][1], context, depth);
  if (fields.length === 2 && value.type === 'text' && own(value, 'text')) return renderValue(value.text, context, depth);
  return `<dl class="trace-readable-fields">${fields.map(([key, child]) => `<div class="trace-readable-field${priority.has(key) ? ' trace-readable-status' : ''}"><dt>${escape(key)}</dt><dd>${renderValue(child, context, depth + 1)}</dd></div>`).join('')}</dl>`;
}

/** A bounded readable preview. Keep the original source inspector alongside it. */
export function renderTraceContent(value, options = {}) {
  const context = { nodes: 0, parseChars: LIMITS.parseChars, textLeft: LIMITS.totalText, seen: new WeakSet(), shortened: false, key: String(options.key || 'content'), detail: 0 };
  const prepared = prepare(value, context);
  const html = renderValue(prepared, context);
  return `<div class="trace-readable">${html}${context.shortened ? '<p class="trace-readable-limit">Preview shortened. Open Original evidence for the complete record.</p>' : ''}</div>`;
}
