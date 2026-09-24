# Cereja UI execution plan

Status: technically grounded planning package with an explicitly selected product
objective, audiences, five initial capability areas and **A: Ledger** visual
direction. The selected shell specification now supports flow-traceable component
and application planning. Files and directories are accepted Compress/Decompress scope with separate
domain-safety and integration tasks. No production implementation is included.

Ledger uses a persistent bottom composer, slash discovery/autocomplete/contextual
help, rich inline views and keyboard overlays. The comparison preserves Workbench
as a non-selected alternative and the earlier 73 wireframes as functional evidence.
The browser review establishes only the bounded checks in the visual review record;
selection is not actual-terminal or user-usability validation.

## Decisions, proposals and open work

Established: independent zero-dependency Python toolkit; Windows/Linux/macOS;
explicit official application; safe text, lazy loading, buffers/diff/partial
updates, shared timers and reduced capability modes; compatibility later.
The application lets Python developers and technical Cereja library/CLI users
discover, inspect and execute existing capabilities; contributors/maintainers
are secondary users. It also serves as toolkit reference/dogfooding. It is not
only a showroom or a generic explorer/system administrator.

Measured: bounded renderer equivalence and sparse-comparison benefit, conservative
Unicode limitations, existing import baseline and local native wake primitives.
[Evidence and limitations](cereja-ui-evidence.md) distinguish actual results from
future terminal/platform tests. Local checks are not multi-platform certification.

Frozen in UI-00: [core architecture contracts](cereja-ui.md#ui-00-decision-and-coverage),
including initial scheduling/resource policies. Their implementation and platform
acceptance remain future work. Public API signatures, application bounds and
Ledger implementation details remain proposals within the selected product scope.
Numerical full-application budgets remain provisional until a real application
baseline exists. No native acceleration is justified by the current evidence.

Open: [Define Cereja UI v1 Product Scope](cereja-ui-product-scope.md), including
implementation-calibrated bounds and future acceptance evidence. Objective,
audiences, real product plus reference role and initial five-area selection are
decided: System, Tree, Context Search, Compress/Decompress and Download.
The [capability inclusion matrix](cereja-ui-capabilities.md) records bounded
execution proposals while retaining broader API/CLI discovery. This initial selection
can be adjusted with evidence from flow analysis, not silently narrowed.
Long operations without safe cooperative cancel/progress hooks remain honest
indeterminate executions; optional generic domain instrumentation is separate.
The [visual studies](cereja-ui-wireframes.html)
are historical inputs. The [selected Ledger specification](cereja-ui-visual-language.md)
and [functional UX contracts](cereja-ui-ux.md) define current planning flows.
Path-based Tree and explicit-root Search are now selected; a generic browser is
not. Optional Settings or unselected command surfaces still require a scope
decision and impact review.

## Dependency order

```text
UI-00 contracts/evidence
  +-> UI-01 capabilities, virtual backend, lifecycle
  |     +-> UI-02 POSIX backend
  |     +-> UI-03 Windows backend
  +-> UI-04 Unicode/text policy
          + UI-01 -> UI-05 cells/composition -> UI-06 diff/output
UI-02 + UI-03 + UI-06 -> UI-07 events/timers
UI-06 + UI-07 -> CORE-PERF calibration
UI-02 + UI-03 + UI-06 + UI-07 -> CORE-PLATFORM validation

SCOPE: Define Cereja UI v1 Product Scope
  -> UX: final IA, flows, wireframes, design/motion and task validation
     -> DELIVERY: derive small high-level implementation tasks
        -> layout/components -> interactive widgets -> official application
        -> real-task dogfooding + end-to-end/platform/package validation
        -> stable-core decision
        -> legacy characterization/strategy -> display integration/refactoring
```

Terminal/rendering tasks do not depend on SCOPE or UX. High-level components
derive from the selected Ledger specification. The task manifest now includes
18 concrete follow-up planning slices for layout, input, overlays, collections,
feedback, background lifecycle, shell/catalogue, all five integrations, structured
Tree traversal, optional domain instrumentation, real acceptance and later legacy
characterization. Directory handling has separate domain-safety and integration slices. These tasks do not authorize production execution.

The authoritative task definitions are [cereja-ui-tasks.json](cereja-ui-tasks.json).
Each contains its risk, dependency keys, measurable completion conditions,
documentation and expected evidence. `cereja-ui-github.json`, once created,
records verified issue URLs and milestone association. Native dependency edges
are used if supported; body links remain explicit. Neither issue creation nor
milestone membership authorizes starting production implementation.

## Experimental acceptance and stopping

The full-diff control and dirty candidate operate on identical frames. Current
tests cover a deliberately broken invalidation case as well as success cases.
Model benefit is scoped to comparison work and excludes painting, layout,
damage collection, actual writes and emulator behavior. Preserve raw samples
and source fingerprints. Repeat only for changed code or unresolved uncertainty.

Before implementation optimizations, freeze workload, source/environment,
control/treatment and pass criteria. Require zero unchanged output, deterministic
full/dirty equivalence, safe untrusted text and no idle redraw independently of
timings. Calibrate core budgets using its implementation baseline; calibrate
user-facing latency only after scope-approved application tasks exist.

Stop alternative visual exploration after the explicit Ledger selection. Keep
implementation-calibrated resource bounds in the explicit task criteria; do not substitute a dashboard, widget
gallery or additional capabilities merely to close planning.

## Requirement-by-requirement planning coverage

| Requested process item | Current evidence or next explicit gate |
| --- | --- |
| 1. Review requirements | Architecture section 1 and scope decision document distinguish fixed constraints from unresolved product scope. |
| 2. Review premises | Architecture and primary references; independent core supersedes early legacy convergence. |
| 3. Risks/gaps | Each task has risk; evidence report has platform and model limits; SCOPE owns product questions. |
| 4. Spikes | Reproducible isolated models, security/Unicode probe, queue/timers/native wake. Remaining platform integration is assigned. |
| 5. Contracts | Architecture boundaries, lifecycle, cells/text, failure transactions, events/pressure and ownership. |
| 6. Benchmarks/baselines | Raw measured local renderer/import/native results. Production core/end-to-end budget calibration explicitly remains. |
| 7. Measurable acceptance | Task criteria plus hard invariants; proposed timing values are not called proven budgets. |
| 8. IA/UX | Selected Ledger shell grammar, five flows L1-L5 and examples/help L6. |
| 9. Wireframes | Selected Ledger in the interactive exact-cell comparison; non-selected Workbench and 73 old functional references preserved. |
| 10. Navigation/interaction | Composer, insert-then-submit suggestions, parameter overlays, focus/selection/scroll and exact-target confirmation contracts. |
| 11. Design system | Selected Ledger hierarchy/tokens/cell geometry plus capability/no-motion/plain fallbacks; real-host validation assigned. |
| 12. Motion/feedback | Every requested effect evaluated; shared timers/dirty regions/fallback policy, final screen use at UX. |
| 13. Components from real flows | Flow-to-component table and 18 concrete follow-up task slices in the manifest. |
| 14. Technical order | Core DAG and conditional product/legacy tail above. |
| 15. GitHub milestone | Verified URL in publication record after creation. |
| 16. Small issues | Core issues published; selected-Ledger follow-up issues defined with explicit dependencies and evidence. Publication record is authoritative. |
| 17. Milestone association | Every published child reread with milestone number. |
| 18. Dependencies/risks/evidence | Task manifest and remote body links; native relationships verified where available. |
| 19. Tests/benchmarks/docs | Incorporated into each issue's completion criteria, not postponed wholesale. |
| 20. Later display compatibility | Explicit stable-core -> characterization -> strategy -> integration/refactor stage; no early legacy gate. |

The follow-up issues are published and dependency/milestone metadata verified.
The selected specification and final consistency review complete this planning
deliverable. No unresolved product choice is required to execute the plan. Implementation
and release acceptance remain future work even when planning is complete.

## Legacy strategy and rollout decision

After dogfooding establishes stable contracts, characterize public signatures and
observable behavior for console/Progress/State, stream restoration/capture,
nesting, concurrency, notebooks and lazy exports. Compare those against terminal
ownership and new rendering contracts. Select adapters/wrappers/facades where
semantics align; consider controlled refactoring or explicit migration when they
do not. Preserve maximum reasonable API compatibility without coupling the new
core to old internals. No deprecation choice is assumed. Each migration slice
needs regression evidence, coexistence tests, documentation and rollback scope.

## Tracking limitations

At the 2026-09-21 planning check, shared Project board access lacked the required
scope. This is a historical observation, not a current permission test. Record actual
milestone/issue metadata separately from desired board status/priority. Do not
change credentials, create substitute boards or claim board association without
verification. No due date or user priority is inferred from this dependency order.

Milestone [5](https://github.com/cereja-project/cereja/milestone/5) and issues
[294](https://github.com/cereja-project/cereja/issues/294) through
[306](https://github.com/cereja-project/cereja/issues/306) were published.
[302](https://github.com/cereja-project/cereja/issues/302) is the Product Scope
stage; [303](https://github.com/cereja-project/cereja/issues/303) depends on it
for final UX; [306](https://github.com/cereja-project/cereja/issues/306) depends
on final UX for high-level decomposition. Native dependencies and milestone
association were reread. Parent #293 owns the summary and native sub-issue list.

The initial planning publication contained technical summaries; a separate
source/data export was not authorized at that stage. The subsequent UI-00
publication packages the linked documents, spike source and raw reports together
for review. #294 tracks the publication and integration state.

The [visual review](cereja-ui-visual-review.md) describes the bounded historical
inspection. The [artifact fingerprints](cereja-ui-visual-artifacts.json) identify
the HTML bytes included here and preserve the earlier, mismatching fingerprints.
Recomputing these hashes does not establish another visual review or bind the
historical inspection to the current HTML bytes.

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

## Published selected-Ledger follow-up tasks

All 18 follow-up issues were created and reread with exact bodies, milestone 5,
native issue types and every native dependency edge verified. Together with the
13 original children, this is 31 child tasks. Parent linking is coordinated on #293.

| Key | Issue | Depends on |
| --- | --- | --- |
| UI-08 | [307](https://github.com/cereja-project/cereja/issues/307) | #299, #301, #303 |
| UI-09 | [308](https://github.com/cereja-project/cereja/issues/308) | #307, #298, #301 |
| UI-10 | [309](https://github.com/cereja-project/cereja/issues/309) | #308 |
| UI-11 | [310](https://github.com/cereja-project/cereja/issues/310) | #307, #308 |
| UI-12 | [311](https://github.com/cereja-project/cereja/issues/311) | #307, #301 |
| APP-00 | [312](https://github.com/cereja-project/cereja/issues/312) | #301, #311 |
| APP-01 | [313](https://github.com/cereja-project/cereja/issues/313) | #309, #310, #312, #303 |
| APP-02 | [314](https://github.com/cereja-project/cereja/issues/314) | #313 |
| DOMAIN-TREE | [315](https://github.com/cereja-project/cereja/issues/315) | #294 |
| APP-03 | [316](https://github.com/cereja-project/cereja/issues/316) | #313, #315 |
| APP-04 | [317](https://github.com/cereja-project/cereja/issues/317) | #313 |
| APP-05 | [318](https://github.com/cereja-project/cereja/issues/318) | #313 |
| APP-06 | [319](https://github.com/cereja-project/cereja/issues/319) | #313 |
| DOMAIN-OPS | [320](https://github.com/cereja-project/cereja/issues/320) | #294 |
| APP-ACCEPT | [321](https://github.com/cereja-project/cereja/issues/321) | #314, #316, #317, #318, #319, #304, #305, #324 |
| LEGACY-PLAN | [322](https://github.com/cereja-project/cereja/issues/322) | #321 |
| DOMAIN-ARCHIVE | [323](https://github.com/cereja-project/cereja/issues/323) | #294 |
| APP-07 | [324](https://github.com/cereja-project/cereja/issues/324) | #318, #323 |
