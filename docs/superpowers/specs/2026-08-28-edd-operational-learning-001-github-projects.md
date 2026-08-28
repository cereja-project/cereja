# EDD Operational Learning 001 — GitHub Projects automation

## Status

Validated capability finding from case study #001 setup. This record exists so the result does not depend on chat history.

## Context

During setup of the `cereja.io` EDD case study, the ChatGPT GitHub connector could create/read/update repository issues but exposed no GitHub Projects v2 operations. Initial manual fallback risked making the human maintainer responsible for routine Project bookkeeping.

## Research result

GitHub Projects v2 is fully automatable through supported GitHub interfaces even when a particular agent connector does not expose those operations.

### GitHub CLI

The official `gh` CLI provides `gh project` commands including:

- `gh project list`
- `gh project view`
- `gh project field-list`
- `gh project field-create`
- `gh project item-add`
- `gh project item-list`
- `gh project item-edit`

Project access requires the authenticated token to include the `project` scope. GitHub documents `gh auth refresh -s project` as the way to add it when necessary.

`gh project item-edit` can select a Project by number/owner, an issue by URL, a field by name, and a single-select value by option name. This is sufficient for the EDD Project fields (`Status`, `Type`, `Area`, `Risk`, `Evidence`) without requiring agents to hard-code GraphQL node IDs.

### GraphQL fallback

GitHub's Projects v2 GraphQL API exposes the lower-level primitives required for automation:

- `addProjectV2ItemById`
- `updateProjectV2ItemFieldValue`

Adding an item and updating its fields are separate mutations. This is a supported fallback when `gh project` is unavailable but an authenticated GraphQL-capable environment exists.

## Decision

Do **not** redesign EDD around manual Project maintenance merely because one connector lacks Projects v2 operations.

Preferred capability order for an execution environment:

1. use a connected GitHub Projects capability when available;
2. otherwise use authenticated `gh project` commands in a trusted development environment;
3. otherwise use authenticated GitHub GraphQL Projects v2 operations;
4. require human Project bookkeeping only when none of the supported authenticated mechanisms is available.

Repository Issues remain sufficient sources of task instructions and evidence. Project metadata is an operational view and must not be the only location of information required to execute a task.

## Security boundary

Agents must not request or persist raw GitHub tokens in project files, prompts, issue bodies, logs, or experiment artifacts. Authentication should be supplied by the host/environment (for example existing `gh` authentication or a managed connector).

A missing `project` permission is a capability constraint, not justification to broaden token permissions silently. Human authorization is required when authentication scope must be changed.

## Knowledge candidate

### Pattern candidate: capability fallback ladder

When an agent-facing connector lacks a capability that the underlying platform officially supports, investigate supported authenticated interfaces before converting the missing connector operation into a permanent human step or redesigning the workflow.

### Antipattern candidate: connector-shaped methodology

Do not make methodology architecture mirror limitations of one agent host/connector. Host capability gaps should be explicit execution-environment constraints with supported fallbacks.

## Implication for case study #001

The current ChatGPT session cannot directly mutate the Project because its GitHub connector exposes no Projects v2 actions. This does **not** imply that future EDD execution agents must require manual Project updates. A development-agent environment with authenticated GitHub CLI can manage the Project programmatically.

This distinction should be included when recording the agent/toolchain environment for each EDD task.

## Primary references checked

- GitHub CLI manual: `gh project`
- GitHub CLI manual: `gh project item-add`
- GitHub CLI manual: `gh project item-edit`
- GitHub CLI manual: `gh project field-list`
- GitHub documentation: Using the API to manage Projects
- GitHub GraphQL Projects v2 mutations
