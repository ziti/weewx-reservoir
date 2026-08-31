# Security Policy

## Supported versions

This project is maintained on a best-effort basis. Security fixes are made
against the **latest release** only. Please upgrade before reporting.

| Version | Supported |
|---------|-----------|
| latest release | :white_check_mark: |
| anything older | :x: |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through
[GitHub private vulnerability reporting](https://github.com/ziti/weewx-reservoir/security/advisories/new)
— on the repository, open the **Security** tab and choose
**Report a vulnerability**. This keeps the report and the discussion private
until a fix ships.

Please include:

- a description of the issue and its impact,
- steps to reproduce or a proof of concept,
- affected version(s),
- any suggested fix.

You can expect an acknowledgement within about a week. Once a fix is ready a
new release will be published and the advisory disclosed, with credit to the
reporter unless you prefer otherwise.

## Scope notes

- This extension makes unauthenticated HTTP GET requests to the public USGS
  Water Services API using `requests`, with query parameters built from
  `[Reservoir]` in `weewx.conf`. It sends no credentials and writes nothing
  back to USGS.
- The RDB response is treated as untrusted input: columns are located by
  parameter-code suffix, values are cast defensively, and non-numeric
  sentinels are skipped. A malformed or hostile response should at worst leave
  the archive record unchanged — report it if you can make it do more.
- Anyone who can edit `weewx.conf` can already run code as the WeeWX user, so
  config-driven request construction is by design, not a vulnerability.
