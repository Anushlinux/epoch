import test from 'node:test';
import assert from 'node:assert/strict';
import { executionPanel } from '../src/execution-ui.mjs';
import { supervisionView, environmentView, operationRecoveryView } from '../src/supervision-ui.mjs';

const state = () => ({ connected: true, taskId: 'task', origin: 'http://127.0.0.1:8000', events: [], runs: [], runtime: { execution_enabled: true, hermes_available: true, supervision_enabled: true, automatic_repair: true, repair_opt_in: true, repair_targets: ['checklist_serializer.py', 'qa_lookup.py', 'runbook_selector.py'], active_run_id: null }, repairRuntime: { available: true }, environment: { project: 'demo', active_version: 'builtin', versions: [], history: [], repairs: [] } });
const operation = () => ({ id: 'revision', trigger: 'initial', status: 'completed', user_input: 'Prepare release', created_at: '2026-09-06', turns_used: 8, max_turns: 20, debugger_turns: 2, executor_turns: 6, timeout_seconds: 600, verification: { passed: true }, repairs: [] });
const supervised = () => ({ ...state(), run: { id: 'run', status: 'completed', environment_version: 'builtin', supervision: { debugger_model: 'gpt-5.6-luna', current_revision_id: 'revision', operations: [operation()] } } });

test('release controls default to supervision and use current backend limits', () => {
  const html = executionPanel(state(), { release: '2.4', scenario: 'broken_checklist' });
  assert.match(html, /id="release-supervised"[^>]*checked/);
  assert.match(html, /id="release-turns"[^>]*max="20"/);
  assert.match(html, /id="release-timeout"[^>]*max="600"/);
  assert.doesNotMatch(html, /Automatic supervision, feedback revisions and environment repair are not implemented/);
  assert.match(html, /id="start-release" >Start release run/);
});

test('repair cannot present omission as checked and unavailable supervision blocks start', () => {
  const html = executionPanel(state(), { release: '2.4', scenario: 'control', repair_enabled: true, demo_omit_notification: true });
  assert.match(html, /id="release-repair"[^>]*checked/);
  assert.match(html, /id="release-omission"[^>]*disabled/);
  assert.doesNotMatch(html, /id="release-omission"[^>]*checked/);
  const unavailable = state(); unavailable.runtime.supervision_enabled = false;
  assert.match(executionPanel(unavailable, {}), /id="start-release" disabled/);
});

test('feedback and clarification use retained revisions and escape untrusted text', () => {
  const s = supervised(); s.run.status = 'needs_input';
  s.run.supervision.operations[0].questions = ['Which <channel>?'];
  const html = supervisionView(s, '</textarea><script>alert(1)</script>');
  assert.match(html, /Send clarification/);
  assert.match(html, /Which &lt;channel&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /data-revision-id="revision"/);
  assert.match(html, /Model requests: 8 \/ 20/);
});

test('repair proofs preserve absent and failed results beside publication', () => {
  const s = supervised();
  s.run.supervision.operations[0].repairs = [{ status: 'published', attempts: [{ status: 'rejected', proposal: { diagnosis: '<img onerror=x>', source: '<script>x</script>' }, diff: '+<script>x</script>', proofs: [{ kind: 'component', passed: false }] }] }];
  const html = supervisionView(s);
  for (const title of ['Adapter behavior', 'Container isolation', 'Original task replay', 'Fresh release', 'Healthy-path regression']) assert.ok(html.includes(title));
  assert.match(html, /Failed/);
  assert.match(html, /Not recorded/);
  assert.match(html, /rejected/);
  assert.match(html, /Generated adapter diff/);
  assert.doesNotMatch(html, /<script>|<img/);
});

test('rollback requires an idle published environment and keeps pinned run visible', () => {
  const s = supervised();
  assert.match(environmentView(s), /data-action="environment-rollback" disabled/);
  s.environment.active_version = 'version';
  assert.match(environmentView(s), /data-action="environment-rollback" >Roll back/);
  assert.match(environmentView(s), /This run uses version <strong>builtin/);
  s.runtime.active_run_id = 'other';
  assert.match(environmentView(s), /data-action="environment-rollback" disabled/);
});

test('uncertain operations retain exact request and block cross-run retry', () => {
  const s = supervised(); s.operationPending = { runId: 'different', origin: s.origin, payload: { client_request_id: 'saved-request' } };
  let html = operationRecoveryView(s);
  assert.match(html, /saved-request/);
  assert.doesNotMatch(html, /data-action="operation-retry"/);
  s.operationPending.runId = 'run';
  html = operationRecoveryView(s);
  assert.match(html, /data-action="operation-retry"/);
  s.operationRejected = true;
  assert.match(operationRecoveryView(s), /data-action="operation-review"/);
});

test('lookup and retrieval repairs expose investigation, fresh project and shared provenance', () => {
  const s = supervised();
  s.run.supervision.operations[0].repairs = ['qa_lookup.py', 'runbook_selector.py'].map((editable_target) => ({ editable_target, investigation: { evidence: 'observed missing capability' }, attempts: [{ proposal: { tool_contract: { name: 'directory.lookup_qa_owner' } }, proofs: [{ kind: 'fresh_release', passed: true, verification_project: 'fresh-project', source_project: 'demo' }] }] }));
  s.environment.effective_artifacts = { 'qa_lookup.py': { origin_project: 'shared-project', origin_version: 'shared-version', artifact_sha256: 'source-digest' } };
  s.run.environment_artifacts = { 'qa_lookup.py': 'pinned-version' };
  const html = supervisionView(s) + environmentView(s);
  for (const text of ['QA owner lookup repair', 'Guidance retrieval repair', 'Investigation and observed evidence', 'Generated lookup tool contract', 'fresh-project', 'shared-project', 'shared-version', 'source-digest', 'pinned-version']) assert.ok(html.includes(text), text);
  assert.match(html, /data-action="environment-rollback" disabled/);
});

test('missing capability disables repair and inspection failures remain visible', () => {
  const s = state(); s.runtime.repair_targets = ['checklist_serializer.py'];
  s.optionalErrors = ['environment: <unavailable>'];
  s.runtime.development_validation = 'phases_6_7_untested';
  const html = executionPanel(s, { scenario: 'missing_lookup', repair_enabled: true });
  assert.match(html, /id="release-repair"[^>]*disabled/);
  assert.match(html, /id="start-release" disabled/);
  assert.match(html, /environment: &lt;unavailable&gt;/);
  assert.match(html, /development acceptance is pending/);
});
