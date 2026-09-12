# Trace interface cleanup — September 12, 2026

Scope: simplify the existing trace interface without changing capture, model calls,
source evidence, metadata authority or filter approval rules.

1. Separate investigation from recorded-step inspection with clear navigation.
2. Distinguish the user's question from the local model's response, keep the next
   review/apply action prominent, and move source management/history/trials into
   secondary controls. Remove example walkthroughs from the working interface.
3. Decode nested JSON for display, present tool descriptions and parameters clearly,
   and retain original recorded content for inspection. Escape all supplied content.
4. Preserve URL selection, drafts, refresh behavior, uncertainty notices, explicit
   approval and rollback. Document the new paths and manual acceptance steps.

Validation: static source review and `git diff --check` only, as requested. Do not run
tests, syntax/lint checks, the browser, servers, Docker, SDK probes or model calls.
Delivery remains implemented but unverified. No backend setting or migration is needed.

## Current navigation

- Chat's View trace opens Analysis. The question and model assessment are separate.
  A supported suggestion leads to Review affected sources, then explicit Apply filter.
  Outcome/uncertainty remain visible; expanded Evidence contains the full findings.
- Recorded steps opens the tree and readable input/output. Citation links open this
  view and focus the selected step. Original evidence retains exact recorded content.
- Manage sources and history contains source annotations, Delivered context, Filters
  and trials, and History. Example instructions are no longer part of the working page.
- A separate Ask about these steps disclosure retains existing standalone trace
  questions. All-traces browsing, filters and pagination remain available.

## Manual checks for the user (not executed)

Hard-refresh the existing frontend with Ctrl+Shift+R. No backend restart is required.

1. Open a saved chat trace. Identify Your question and Analysis, open Evidence and
   evidence limitations, and confirm there is no example/trial/history instruction list.
2. Open a cited tool or Recorded steps. Select a describe-tool step; inspect its name,
   description, parameters and Full schema. Inspect nested JSON and plain-text outputs.
   Original evidence must still show the unchanged recorded input/output.
3. Review a supported filter. Confirm retained/excluded files, replacement and scope
   before Apply filter. Verify disabled stale/blocked reviews and the existing Undo path.
4. Use Manage sources and history to reach metadata, delivered context and old records.
   No analysis or policy action should start just from opening these controls.
5. Type an unfinished question, switch between views and back, and allow a five-second
   refresh. Confirm drafts, focused controls and expanded disclosures remain usable.
   Check citation links, old question bookmarks, narrow screens and keyboard focus.

The UI does not correct model conclusions, reconstruct omitted evidence or establish
task success. Readable previews are bounded; long or unsupported content remains in
Original evidence. This delivery has no browser/visual acceptance claim.
