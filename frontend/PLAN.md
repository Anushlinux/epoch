# Epoch chat and debugger implementation

Approved September 6, 2026. Base: origin/main at 4bfb841; branch codex/epoch-chat-debugger.

1. Build the shared Hermes-inspired dark shell, local Bodoni typography, separate routes, and accessible primitives.
2. Reframe real intake as chat while retaining the Phase 1 adapter and frozen-submission recovery.
3. Reframe the existing Atlas release fixture as chat and a separate six-stage debugger. Preserve evidence guards, rejected attempts, partial results, and revisions.
4. Finish responsive behavior, navigation state, inspectors, documentation, and all UI states before executing tests.
5. Run focused state/browser/intake checks, inspect desktop/mobile previews, and retain evidence and limitations.

Real and demo entrypoints stay separate. No backend, executor, evaluator, or API-contract changes. The original direction document stays unchanged. Additional repair scenarios and unsupported Hermes controls are outside this assignment.

## Completion record

Steps 1–5 are implemented. The dark chat, real intake/recovery, Atlas conversation, separate debugger, responsive navigation, accessible inspection, and documentation are complete. Verification passed with 41 state tests, 34 demo browser checks, 14 real-intake browser checks, and real HTTP persistence/retry checks. The preview is ready for user-guided visual review. See [evidence](evidence/README.md) for scope and limits.
