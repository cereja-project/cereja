# Process Privacy

Cereja can launch third-party tools with explicit, process-scoped privacy
policies. The first provider is Hugging Face.

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

## Python API

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

## Security boundary

This feature controls environment variables used by Hugging Face libraries. It
is **not a network sandbox**. Arbitrary code can still make network requests
using another HTTP client if the operating system permits them.

Use an OS firewall, container/network namespace, VM, or equivalent isolation
when the requirement is to prevent all outbound network traffic.
