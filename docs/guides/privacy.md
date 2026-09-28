# Process Privacy

Cereja can launch third-party tools with explicit, process-scoped privacy
policies. Supported providers are Hugging Face and OpenHands.

The policy is intentionally local to the child process. Cereja does not edit
`.bashrc`, PowerShell profiles, the Windows registry, or persistent user
credentials.

## Hugging Face offline mode

Run a command with Hub access disabled and telemetry disabled:

```bash
cereja privacy huggingface run -- python app.py
```

Open an offline child shell:

```bash
cereja privacy huggingface shell
```

The child receives:

```text
HF_HUB_DISABLE_TELEMETRY=1
DO_NOT_TRACK=1
HF_HUB_OFFLINE=1
HF_DATASETS_OFFLINE=1
TRANSFORMERS_OFFLINE=1
HF_HUB_DISABLE_IMPLICIT_TOKEN=1
```

`HF_TOKEN` and the legacy `HUGGING_FACE_HUB_TOKEN` are removed from the child
environment so an inherited credential is not forwarded accidentally.

Inspect the current process environment without printing token values:

```bash
cereja privacy huggingface status
cereja privacy huggingface status --json
```

## Explicit download session

When network access is intentionally required for one command, use `download`:

```bash
cereja privacy huggingface download -- hf download org/model
```

Cereja prompts for the Hugging Face token without echoing it and passes it only
to the child process. It is not persisted by Cereja. Telemetry remains disabled
while Hub access is online.

For a public model that does not need authentication:

```bash
cereja privacy huggingface download --no-token -- hf download org/public-model
```

For automation, explicitly name the environment variable that contains the
token:

```bash
cereja privacy huggingface download --token-env MY_HF_TOKEN -- hf download org/private-model
```

Cereja never prints the token value.

## Hugging Face Python API

The same policy is available without the CLI:

```python
from cereja.privacy import huggingface

env = huggingface.offline_environment()

result = huggingface.run(
    ["python", "app.py"],
    offline=True,
)
```

An explicit online child process can receive a temporary token:

```python
result = huggingface.run(
    ["hf", "download", "org/private-model"],
    offline=False,
    token=token,
)
```

## OpenHands process-scoped profiles

Cereja can configure child processes for OpenHands components with explicit telemetry and tracing controls.

Like the Hugging Face policy, these profiles are process-scoped: Cereja never modifies shell configurations, dotfiles, browser storage, or persistent application state.

### Components and environment policies

OpenHands requires distinct controls across different execution phases:

1. **`agent-server`**:
   The child environment receives:
   ```text
   DO_NOT_TRACK=1
   OH_TELEMETRY_EXPORTER=none
   ```
   The following telemetry destinations and credentials are explicitly removed from the child environment:
   - `OH_TELEMETRY_POSTHOG_API_KEY`
   - `OH_TELEMETRY_POSTHOG_HOST`
   - `OH_TELEMETRY_HTTP_ENDPOINT`
   - `OH_TELEMETRY_HTTP_TOKEN`

   The following tracing triggers and header credentials are also removed:
   - `LMNR_PROJECT_API_KEY`
   - `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT`
   - `OTEL_EXPORTER_OTLP_ENDPOINT`
   - `OTEL_ENDPOINT`
   - `OTEL_EXPORTER_OTLP_TRACES_HEADERS`
   - `OTEL_EXPORTER_OTLP_HEADERS`

   Authentication and encryption keys such as `SESSION_API_KEY` and `OH_SECRET_KEY` are intentionally preserved in the child environment so security controls are not weakened, but they are never printed in diagnostic reports. Model API keys and network proxies are also preserved.

2. **`canvas-build`**:
   Applies opt-out environment variables during frontend compilation:
   ```text
   DO_NOT_TRACK=1
   VITE_DO_NOT_TRACK=1
   ```
   *Note*: This setting applies during build. It does not rewrite pre-compiled bundles or modify interfaces hosted by third parties.

3. **`canvas-static`**:
   Applies opt-out flags for static web servers that support runtime opt-out injection:
   ```text
   DO_NOT_TRACK=1
   AGENT_CANVAS_DISABLE_TELEMETRY=1
   ```
   *Note*: This requires a static server implementation that inspects this flag and injects opt-out scripts into the browser document. Generic HTTP servers do not automatically support this behavior.

### OpenHands CLI

Inspect environment state for a specific component:

```bash
cereja privacy openhands status --component agent-server
cereja privacy openhands status --component agent-server --json
```

Status reports never echo raw credential values, URLs, headers, or malformed flags. Only normalized states (`set`, `unset`, `conflicting`) and presence (`present`, `absent`) are reported.

Run a command under an OpenHands privacy profile:

```bash
cereja privacy openhands run --component agent-server -- python -m openhands.agent_server
```

Child command arguments must follow `--`. Cereja does not invoke a shell to launch the command and returns the child process exit code directly.

### OpenHands Python API

```python
from cereja.privacy import openhands

# Build a child environment
env = openhands.environment("agent-server")

# Inspect environment flags without leaking secrets
report = openhands.status(component="agent-server")

# Run child process with verified arguments and profile
result = openhands.run(
    ["python", "-m", "openhands.agent_server"],
    component="agent-server",
)
```

## Security boundary and coverage limits

These features control environment variables passed to child processes. They are **not** an operating-system network sandbox, firewall, content filter, or agent confidentiality guarantee:

- **Network isolation**: `not_enforced`. Arbitrary code or tools can still make network requests using HTTP clients if the operating system permits them. Use an OS firewall, container/network namespace, VM, or equivalent isolation when the requirement is to prevent all outbound network traffic.
- **Outbound content filtering**: `not_enforced`. Tools or model calls can transmit private content over the internet if executed.
- **Model routing and auxiliary models**: `not_checked`. Selecting a local primary model does not guarantee that condensers, evaluators, or subagents are also local. Review application configuration files directly.
- **Critic**: `not_checked`. Critic evaluation settings are managed via OpenHands configuration files, not via this environment policy.
- **Webhooks**: `not_checked`. Active webhooks must be verified in application configuration.
- **Local content logging**: `not_checked`. Prompts, code diffs, and conversation history logged locally by the application are not sanitized.
- **Child process output**: stdout and stderr emitted directly by child processes are not filtered by Cereja.
- **Hosted environments**: Launching tools on shared infrastructure (such as Google Colab or cloud VMs) relies on the infrastructure provider's security boundary; environment policies do not provide network isolation or authentication for public tunnels.
