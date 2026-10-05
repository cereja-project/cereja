# Define Cereja UI v1 Product Scope

Status: objective/audiences and initial five capability areas selected. The latest
interaction direction is a Cereja shell/workbench with a persistent bottom command
composer, slash discovery/navigation and rich inline content. The maintainer explicitly selected Ledger (alternative A). Workbench remains a
non-selected comparison artifact. Files and directories are accepted v1 archive scope, with separate safety
stages. Detailed resource budgets remain calibration candidates. This stage precedes final application
IA, flows, wireframes and product-driven high-level component decomposition.
It does not block the independent terminal or rendering core.

## Established decisions

- Build reusable `cereja.ui` and an official application `cereja ui` using it.
- The official v1 application lets users discover, inspect and execute existing
  Cereja capabilities while serving as reference use and dogfooding of the toolkit.
- Primary users are Python developers and technical Cereja library/CLI users;
  contributors and maintainers are secondary users.
- This is not only a widget showroom, a generic file/search application, or a
  system-administration product. Real capability use and toolkit reference use
  coexist deliberately.
- Independent core, Python 3.11+, zero runtime dependencies, Windows/Linux/macOS,
  safe text, lazy imports and controlled noninteractive degradation.
- Define and validate UX before high-level widgets; use common timers/rendering
  for motion, with global disabling and low-bandwidth fallback.
- Treat legacy compatibility after stabilization through objective contract
  comparison. Existing `cereja.display` internals do not constrain the core.
- The previous design provides dashboard, examples, dogfooding and an
  illustrative System information panel. It does not settle a product scope.
- Home, System, Examples, capability catalogue and Diagnostics are views within
  the shell, not a dashboard-first navigation system. A persistent central bottom
  composer supports slash commands, suggestions/autocomplete, contextual help and
  keyboard overlays. Rich content occupies the area above it.
- This shell is not a chatbot, agent or natural-language execution system. It
  must not imitate another product's branding or visual appearance.
- Loading/Empty/Error/Success/Warning are reusable inline component states,
  not independent top-level screens. Cereja identity uses restrained cherry
  accents, focus/selection/status hierarchy and a characteristic composer.
- Each selected capability must already exist, add real interactive value,
  exercise important toolkit components and remain within Cereja's purpose.
- Selected initial proposal: System Information; Repository/Directory Tree from
  an explicit path; Context Search with explicit roots; Compress/Decompress as
  one functional area; Download from user URL to destination. Elaborate these
  flows now, and revise disproportionate complexity with evidence before freezing.
- System is a central real utility and toolkit showcase. Tree is not a full file
  browser. Download is not a full HTTP client. Compression cannot be silently
  replaced by an educational in-memory example.
- Catalogue may explain HTTP, encrypt/decrypt, protect, privacy, security,
  module and registry without making them UI-executable in v1.
- Catalogue badges: `Available` only when a UI integration actually executes;
  `CLI`, `Python API` identify existing surfaces; `Planned UI` marks future or
  unbuilt integrations. Discovery must not initialize all capabilities.
- Long operations use only real progress/speed/ETA and safe cooperative cancel.
  Existing APIs without those hooks remain executable with indeterminate Running,
  actual duration/outcome and no Cancel control. Investigate generic domain
  instrumentation separately; defer disproportionate adaptation with evidence
  instead of silently changing selected scope.

## Planning decisions and implementation gates

| Decision | Evidence/input needed | Why it changes delivery |
| --- | --- | --- |
| Operational bounds within selected five | Files and directories accepted; one active background operation; resource limits are calibration candidates. | Each service needs explicit progress, cancellation and safe publication evidence. |
| Main views and flows | Selected Ledger L1-L6 flows define command, forms, inline result and recovery. | Concrete components and tasks derive from these flows. |
| Visual language | Ledger (A) was explicitly selected by the maintainer. | Consolidate its five capability flows and derive traceable planning tasks; selection is not real-terminal/usability validation. |
| Deliberate exclusions | No full browser, full HTTP client, arbitrary code execution, disk history or unproven Cancel. Wider catalogue remains CLI/API references. | Prevents the whole CLI catalogue becoming implied UI scope. |

The selected five do not select the whole CLI catalogue or every option of each
underlying API. The source-grounded inclusion matrix and operation contracts
document gaps and proposed bounds. Synthetic examples validate reusable
components and complement real capability execution, rather than replacing it.

Help and Settings are open proposals: contextual help can improve discoverability
but adds a navigation surface; session settings expose color/motion policies but
could instead be launch options. These choices affect screens and focus paths.
A broad command launcher still adds unselected forms, secrets and operations.
The selected path-based Tree and explicit-root Search now have user authorization
for flow elaboration; they do not authorize a generic browser, file management,
automatic workspace scans or expansion into unselected operations.

## Acceptance record

Objective, primary/secondary audiences, product/reference relationship and initial
five-area proposal above were explicitly decided by the maintainer. Still record
accepted concrete screens/flows, operational bounds and exclusions, rationale and
remaining open questions. Evaluate utility, component coverage, interaction
variety, low operational risk and controllable scope together.
A response about what
the earlier design says is not acceptance of an executor proposal. Silence,
structural wireframe checks and a running toolkit demo are not product approval.

After this stage is accepted, produce the final UX/design/motion specification,
validate its task walkthroughs, then derive and register the small high-level
widget/application tasks. Preserve the distinction between that planning
authorization and production implementation authorization.

The review artifacts are [visual comparison](cereja-ui-visual-comparison.html)
and [visual-language contracts](cereja-ui-visual-language.md). The earlier 73
wireframes remain functional/responsive evidence, not the final visual language.
No general authorization to detail tasks overrides the specific instruction to
review the visual proposal before final high-level decomposition.

## Parallel technical work

Capability detection, virtual terminal, session restoration, POSIX/Windows
backends, Unicode/text safety, cell composition, diff/output transactions and
event/timer infrastructure follow product-independent requirements. Their
contracts, experiments and bounded implementation tasks can be prepared now.
Product-independent core work must not wait for an arbitrary screen choice.

## Recorded visual direction decision

The maintainer explicitly selected **A: Ledger** after reviewing the two concrete
alternatives. This is actual selection evidence, not inferred from silence or
prototype quality. The visual-alternative gate is satisfied for planning. Retain
Workbench as a non-selected comparison and the earlier 73 functional references.
Implementation is not authorized by this selection. Files and directories are accepted v1 scope with their own safety criteria.

## Accepted directory scope update

The maintainer explicitly selected **files and directories in v1, with their own
safety stages and criteria**. This decision replaces earlier pending/conditional
directory language. Directory traversal/format safety, bounded extraction, owned
staging and truthful publication/cleanup outcomes are separate domain and UI
integration tasks. Existing API behavior is not thereby certified safe.

Ledger retains ordered result blocks within a bounded ephemeral session. The
resource policy and state restoration are specified in the selected visual-language
document; the current-result-only comparison prototype does not implement that
retention extension and is not evidence that it has been runtime validated.
