# Daily GitHub static-site operations

## Scope

This is the M4 local operation path for the independently validated daily GitHub blog. It serves only
an already-built static archive. It does not collect GitHub data, invoke Hermes, select a model, or
run any broad-pipeline stage.

The static-site artifact contract is in
[docs/OUT_DIRECTORY_ORGANIZATION_SPEC.md](OUT_DIRECTORY_ORGANIZATION_SPEC.md). The blog source post
exists only when M3 promoted `post-YYYY-MM-DD.md` after provenance validation.

## Configure the private endpoint

Set one local RFC1918 IPv4 address and non-privileged port in `settings.yaml`:

```yaml
daily_site:
  bind_address: "192.168.2.13"
  port: 8765
```

Before starting the server on macOS, inspect the host inventory and select the intended private LAN
address. Replace `en0` with the interface that `networksetup` reports for the active LAN connection:

```bash
networksetup -listallhardwareports
ifconfig
ipconfig getifaddr en0
```

The server refuses an empty, wildcard, loopback, public, unassigned, or IPv6 address. It also refuses
ports outside `1024` through `65535`. The selected address is probed locally before the HTTP listener
is activated; a configuration that no longer belongs to the host therefore fails closed.

## Build the archive

Build only from M3 artifacts that have passed validation and been promoted to `post-YYYY-MM-DD.md`:

```bash
source source_me.sh && python3 pipeline/daily_github_site.py --settings settings.yaml
```

The deterministic build replaces only `out/<user>/daily_site/`. Its home page and `status.html` show
the newest source date, collection timestamp, confirmed commit and repository totals, and visible
state for every dated run:

- `Complete and published`: a complete run with a promoted post.
- `Incomplete run`: M2 completeness failed; any retained error is visible.
- `Validation failed`: an M3 validation report exists and no promoted post is available.
- `Complete, not published`: M2 completed but M3 has not promoted a post.

Review locally from the generated directory before serving:

```bash
python3 -m http.server --directory out/vosslab/daily_site 8000
```

This loopback review command is not the LAN operation command and must not be used as the private-LAN
service.

## Serve on the configured LAN address

Start the validated private listener in a terminal:

```bash
source source_me.sh && python3 pipeline/daily_github_site_server.py --settings settings.yaml
```

The default access log is `out/logs/daily_github_site/access.log`. It records the request method,
query-free path, response code, and size. Stop the foreground server with `Ctrl-C`.

Verify the listener and homepage through the configured address, not through `localhost`:

```bash
curl --fail http://192.168.2.13:8765/
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

The expected socket report names exactly the configured private address. A `0.0.0.0`, `::`, public,
or unexpected interface binding is a failed deployment check; stop the server and correct
`daily_site.bind_address` before retrying.

## Recovery and rollback

1. Stop the foreground server with `Ctrl-C`.
2. Inspect `out/<user>/daily_site/status.html` and the source run's
   `out/<user>/daily/YYYY-MM-DD/run_manifest.json`.
3. For `Validation failed`, inspect
   `out/<user>/daily/YYYY-MM-DD/validation_failures/validation_report.json`; do not copy a draft into
   a promoted post path.
4. For `Incomplete run`, retain diagnostics and rerun the M2/M3 manual workflow only after the
   collection error is resolved.
5. Rebuild with `pipeline/daily_github_site.py`; it regenerates the presentation tree from the current
   durable artifacts and removes stale static pages.
6. Restart only after `ipconfig getifaddr <interface>` again reports the configured address and
   `lsof -nP -iTCP:<port> -sTCP:LISTEN` confirms the intended private endpoint.

No service manager, schedule, public reverse proxy, DNS record, or public hosting is created by M4.
Those are separate deployment prerequisites after manual LAN review.
