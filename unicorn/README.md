# 🦄 Unicorn

**The Rust-native Git Platform**
Beautiful. Fast. Self-hosted. Built entirely in Rust.

## What this is

This is a *generated scaffold*, not a finished product. Per Unicorn's own
development philosophy, the workspace is produced by a Python generator
(`generate_unicorn.py`) rather than hand-maintained file by file:

```
Edit Generator -> Generate Workspace -> cargo fmt -> cargo check -> Improve Generator -> Repeat
```

Re-running the generator regenerates every file here from scratch, so
treat this directory as build output: make structural changes in the
generator script, not by hand-editing the files it owns.

## What's implemented

| Area | Crate | Status |
|---|---|---|
| Dashboard TUI (Ratatui) | `unicorn-tui` | ✅ working — CPU/memory/disk/network widgets, tabs, nav sidebar |
| Repository discovery & inspection | `unicorn-git` | ✅ working — built on `gix` (gitoxide), no `libgit2` |
| Live system metrics | `unicorn-metrics` | ✅ working — built on `sysinfo` |
| Configuration & domain models | `unicorn-core` | ✅ working — Serde + TOML |
| SSH front door | `unicorn-ssh` | 🚧 scaffold — accepts connections; does not yet serve `git-upload-pack` / `git-receive-pack` |
| Everything else in the long-term vision (webhooks, CI, package registry, REST API, plugins, admin UI) | — | 📋 not started, see `docs/ARCHITECTURE.md` |

## Quickstart

```bash
cd unicorn
cargo check --workspace   # first thing to run - verify the crate graph resolves & compiles
cargo run -p unicorn-cli  # launch the dashboard (reads ./unicorn.toml if present, see config/)
```

Keyboard shortcuts in the dashboard: `tab` / `←` `→` switch tabs, `j` `k`
move the nav selection, `r` rescans `storage.repositories_dir` for
repositories, `q` / `esc` quits.

## Layout

```
crates/
  unicorn-core     shared config, domain models, error types, logging bootstrap
  unicorn-git      gitoxide-backed repository discovery & inspection
  unicorn-metrics  sysinfo-backed CPU / memory / disk / network snapshots
  unicorn-ssh      russh-backed SSH server (scaffold, see module docs)
  unicorn-tui      the Ratatui dashboard - the primary interface
  unicorn-cli      the `unicorn` binary that wires it all together
```

## A note on `unicorn-ssh`

`russh`'s key-handling types have churned across recent releases more than
the rest of this dependency graph, so that crate is the one place in this
scaffold written defensively, with inline `TODO` / verification comments
rather than treated as finished. Run `cargo check -p unicorn-ssh` first if
you hit build errors after generating.
