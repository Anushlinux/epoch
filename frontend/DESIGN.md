# Epoch chat and debugger

The September 6 redesign follows the user's Hermes Desktop screenshot: a charcoal canvas, narrow sidebar, oversized serif EPOCH wordmark, and a quiet bottom composer. Chat and Debugger have separate URLs and share a restrained visual system.

## Type and surfaces

Canvas #1d1f20; rail #191b1d; composer #111315; primary text #cbd0d4; secondary #a0a5ab. System sans-serif supports repeated work; locally bundled Bodoni Moda supplies the display wordmark. Source: https://github.com/google/fonts/tree/main/ofl/bodonimoda; the SIL Open Font License is retained in fonts/OFL.txt. Monospace is reserved for technical evidence.

Sidebar width is 232px on desktop. Controls use small outline icons, 6–10px radii, visible focus, and immediate press feedback. Frequent updates and keyboard navigation do not animate. Occasional mobile navigation transitions use 200ms easing; reduced motion removes movement. Reduced transparency and increased contrast preferences have explicit styles.

## Chat

The empty state has the wordmark and one invitation: Describe the result you want. Saved requests become conversations with an explicit system receipt. The current API supports intake only: each conversation is one saved request, and further work starts through New chat. Connection configuration is secondary. Unknown acknowledgements retain the original frozen payload and exact retry controls.

The demo presents the existing Atlas release example through a conversation. Checkpoint sources, observable activity, repair links, artifacts, and feedback revisions remain inspectable. Custom fixture requests never receive invented progress. Demo playback stays manual and labeled.

## Debugger

A vertical pipeline shows Failure, Diagnosis, Candidate change, Verification, Publish, and Resume task. Its state is derived from existing records, never timers or frontend pass decisions. Rejected attempts remain visible. Active repair and delivered task remain separate. Secondary Activity, Checkpoints, and History tabs expose the full evidence.

At narrow widths, navigation becomes an accessible drawer. The composer follows the visual viewport when the keyboard opens. Code scrolling remains inside inspectors. Text stays readable and full requests remain available even when sidebar titles truncate.
