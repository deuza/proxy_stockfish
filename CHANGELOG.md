# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-10-24

Maintenance release.

### Fixed

- A GUI command that merely contained the letters `go`, such as
  `setoption name SyzygyPath value /home/goku/tb`, was taken for a `go`
  command: the proxy stopped reading the GUI commands for 30 s, waiting
  for a `bestmove` that never came. Only `go` on its own, or `go`
  followed by a space and its parameters, now waits for `bestmove`
- Boolean values in `sf_options`, such as the shipped
  `"UCI_ShowWDL": true`, were sent as `True` / `False` instead of the UCI
  `true` / `false`, and Stockfish silently ignored them. They are now
  sent in lowercase

### Changed

- Log messages use lazy `%s` formatting, and `logging.exception` no
  longer repeats the exception text, which remains in the traceback
- Code cleanup with no change in behaviour: sorted imports, PEP 8 blank
  lines, no trailing whitespace, docstrings, development notes removed
  from comments, `# nosec` with a short reason on the two `subprocess`
  lines reported by bandit

## [1.0.0] - 2026-10-24

Complete rewrite of the transport layer. PuTTY is gone.

### Added

- Engine auto-configuration at startup from `config.json`: `Threads`,
  `Hash`, `MultiPV`, `Ponder` and arbitrary options through `sf_options`,
  applied between `uci` / `uciok` and `isready` / `readyok` before the GUI
  sends anything
- Native OpenSSH transport: the proxy runs the system `ssh` client, which
  makes it work unchanged on Windows 10/11, Linux and macOS
- Standard OpenSSH keys (`id_ed25519`, `id_rsa`), no `.ppk` conversion
- `ssh_options` in `config.json`: extra arguments passed to `ssh`, shipped
  with `BatchMode=yes` and `StrictHostKeyChecking=accept-new`
- `log_file` in `config.json` to choose the log file name
- `~` expansion in `key_file`, on every OS
- Timeouts on every wait for a UCI marker (`uciok`, `readyok`, `bestmove`):
  a silent engine no longer blocks the proxy forever
- Separate handling of `ssh` stderr, logged as warnings
- `BrokenPipeError` handling when the SSH session dies
- A ready-to-edit `config.json` shipped with the project
- `.gitignore` for build artefacts, logs and Python caches
- Documentation of the optional `restrict,command=` hardening of the
  server-side `authorized_keys`

### Changed

- Documentation rewritten in English
- Shipped configuration uses `sf_ponder: false` and small `sf_threads` /
  `sf_hash` values (4 / 2048) so that a first launch cannot exhaust a small
  server

### Removed

- `plink.exe` dependency and the `plink_path` configuration key
- The plink-based `proxysf.py` is replaced in place; it remains available
  under the `v0.0.1` tag

## [0.0.1] - 2025-11-21

First release.

### Added

- Python proxy forwarding UCI commands from a local GUI to a Stockfish
  running on a remote Linux server
- SSH transport through PuTTY's `plink.exe`, Windows only, `.ppk` keys
- `go infinite` / `stop` state tracking, queued command replay after
  `bestmove`
- Optional logging to `debug.log`
- French documentation

Note: the engine auto-configuration described in the README of this release
was not part of the published script. It ships for real in 1.0.0.

[1.0.1]: https://github.com/deuza/proxy_stockfish/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/deuza/proxy_stockfish/compare/v0.0.1...v1.0.0
[0.0.1]: https://github.com/deuza/proxy_stockfish/releases/tag/v0.0.1
