# Install

This repository runs from a source checkout. Installation creates the physical
repository-local `.venv` that [`source_me.sh`](../source_me.sh) verifies and uses
for the command-line tools.

## Requirements

- Bash and Python 3.12. `source_me.sh` rejects a missing, symbolic-link, or
  non-3.12 `.venv`.
- Runtime packages in [`pip_requirements.txt`](../pip_requirements.txt).
- Developer packages in [`pip_requirements-dev.txt`](../pip_requirements-dev.txt)
  when running tests.
- The non-Python packages in [`Brewfile`](../Brewfile) when using the matching
  macOS audio or local-model features.
- macOS `say` for the one-voice renderer in
  [`pipeline/script_to_audio_say.py`](../pipeline/script_to_audio_say.py).

## Install steps

1. Obtain the source checkout and change to its root.
2. Create the required physical Python environment:

   ```bash
   python3.12 -m venv .venv
   ```

3. Install the runtime and developer dependencies into that environment:

   ```bash
   .venv/bin/pip install -r pip_requirements.txt -r pip_requirements-dev.txt
   ```

4. Load the repository environment before running a repository command:

   ```bash
   source source_me.sh
   ```

   This puts `.venv/bin` first on `PATH` and exposes `pipeline/` plus the
   local LLM wrapper through `PYTHONPATH`.

## Daily publication, model routes, and timer

The generic install supports route-free commands, tests, fixture preparation,
and offline E2Es. It does not provision the host-local editorial model command.
The checked-in `daily_blog.routes.*` entries in
[`settings.yaml`](../settings.yaml) invoke `hermes chat` and must resolve in the
same environment used by a manual command or the systemd service. The bootstrap
also adds `$HOME/nsh/local-llm-wrapper` to `PYTHONPATH` for the current host
integration.

Before attempting publication, provide the configured model/provider commands
in the host environment. `make_blog.py` owns date selection and launches one
publication run. Hermes supplies configured author and referee model execution
inside that run. Evidence collection, validation, date locking, bundle writing,
and local import remain deterministic; Hermes does not own a schedule or a
second publication loop.

Repository discovery requires `GITHUB_TOKEN`. The runtime first accepts an explicitly injected
value, then reads only `GITHUB_TOKEN` from `$HERMES_HOME/.env` (default `~/.hermes/.env`). Keep the
token in that runtime credential source rather than `settings.yaml`. The checked-in service sets
`HERMES_HOME=/home/vosslab/.hermes`; it does not source the complete dotenv file.

For unattended publication, install the checked-in systemd user unit and timer.
The timer calls `./make_blog.py --yesterday` directly at 04:00
America/Chicago. Systemd owns that schedule and service lifecycle. The command
preserves an already-published date and exits successfully, so it never waits
for terminal input.

```bash
mkdir -p ~/.config/systemd/user
cp deploy/vosslab-daily-publication.service ~/.config/systemd/user/
cp deploy/vosslab-daily-publication.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now vosslab-daily-publication.timer
```

See [`DAILY_BLOG_OPERATIONS.md`](DAILY_BLOG_OPERATIONS.md#scheduling) for the operator checks and
the publication ownership boundary.

## Maker experiment access

The active production interface is v3-historical policy v3. The v4-maker policy
v3 is a private, non-publishing experiment and needs no special installation.
Its capture command invokes configured author and referee routes, while its
deterministic attestation command invokes no route. A live historical
calibration is a separate opt-in operation: it requires the durable
data-sharing setting and `--approve-historical-post-sharing` for that one
invocation. See [`USAGE.md`](USAGE.md#maker-experiment) for the exact sequence.

## Verify install

Confirm the selected interpreter, YAML dependency, and primary runner interface
plus the root blog interface without creating pipeline artifacts or calling a
model route:

```bash
source source_me.sh && python3 -c 'import sys, yaml; assert sys.version_info[:2] == (3, 12); print(sys.version)'
./make_blog.py --help
```

## Troubleshooting

### `source_me.sh` rejects the environment

Recreate `.venv` with the first two installation commands. The bootstrap only
accepts a physical repository-local Python 3.12 environment.

### `--no-api-calls` cannot find cached data

[`automation/run_local_pipeline.py`](../automation/run_local_pipeline.py)
requires a prior fetched JSONL below `out/<github_username>/`. Use this option
only after a suitable fetch output exists.

## Known gaps

- TODO: verify the optional Qwen multi-speaker renderer on each intended
  machine and model runtime.
- TODO: complete an operator-approved live historical calibration and maker
  capture before considering a v4 activation decision.
