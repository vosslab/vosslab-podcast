# Install

This repository runs from a source checkout. Installation creates the physical,
repository-local `.venv` used by the general content runner, date-owned publication
command, and developer tools.

## Requirements

- Bash and Python 3.12.
- Runtime packages in [`pip_requirements.txt`](../pip_requirements.txt).
- Developer packages in [`pip_requirements-dev.txt`](../pip_requirements-dev.txt) for tests.
- The configured local `vosslab-daily-blog` checkout for a real daily publication.

## Install steps

1. Obtain the source checkout and change to its root.
2. Create the required physical Python environment:

   ```bash
   python3.12 -m venv .venv
   ```

3. Install runtime and developer dependencies from the checkout:

   ```bash
   .venv/bin/pip install -r pip_requirements.txt -r pip_requirements-dev.txt
   ```

4. Load the repository environment before Python commands:

   ```bash
   source source_me.sh
   ```

`source_me.sh` verifies Python 3.12, puts `.venv/bin` first on `PATH`, and exposes
the repository pipeline modules.

## Live publication setup

The checked-in daily-blog routes invoke `hermes chat`; a live publication also needs
the configured GitHub credential source and the local publisher checkout named in
[`settings.yaml`](../settings.yaml). Keep provider credentials out of that file.

The included systemd user unit calls `./make_blog.py --yesterday` at 04:00
America/Chicago. Install it only on a host prepared for live publication:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/vosslab-daily-publication.service ~/.config/systemd/user/
cp deploy/vosslab-daily-publication.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now vosslab-daily-publication.timer
```

See [`DAILY_BLOG_OPERATIONS.md`](DAILY_BLOG_OPERATIONS.md) for operating boundaries.

## Verify install

This verified command checks the selected interpreter and its YAML dependency without
collecting evidence, calling a model, or importing a post:

```bash
source source_me.sh && python3 -c 'import sys, yaml; assert sys.version_info[:2] == (3, 12)'
```

Inspect the public command interface separately:

```bash
./make_blog.py --help
```

Run the controlled no-egress publication proof when validating a checkout:

```bash
source source_me.sh && python3 tests/e2e/e2e_daily_publication.py
```

It uses disposable roots and deterministic route responses; it never requires Hermes,
network access, or a configured publisher checkout.

## Troubleshooting

### Environment rejected

Recreate `.venv` with Python 3.12. The bootstrap rejects a missing, symbolic-link,
or non-3.12 repository environment.

## Known gaps

- TODO: verify the optional live Hermes route on each intended publication host.
