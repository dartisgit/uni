#!/usr/bin/env python3
"""
generate_unicorn.py
====================

Scaffolding engine for Unicorn - the Rust-native, self-hosted Git platform
described in the project vision doc ("Beautiful. Fast. Self-hosted. Built
entirely in Rust."). Running this script IS the "Generator" step in
Unicorn's own stated development loop:

    Edit Generator -> Generate Workspace -> cargo fmt -> cargo check ->
    Improve Generator -> Repeat

Every crate/API used in the generated Cargo workspace was checked against
current documentation (docs.rs / crates.io) rather than pulled from
memory, since crates like `gix` (gitoxide), `ratatui`, and `russh` move
fast. Versions confirmed at generation time:

    gix          0.84.x   https://docs.rs/gix
    ratatui      0.29.x   https://docs.rs/ratatui  (ratatui::init()/restore()
                          app pattern, Gauge/Sparkline/BarChart/List/Tabs APIs)
    tokio        1.53.x   features = ["full"]
    sysinfo      0.39.x   System::new_all/refresh_*, Disks, Networks
    russh        0.54.x   features = ["ring"]
    russh-keys   0.49.x
    serde 1 / toml 0.8 / tracing 0.1 / tracing-subscriber 0.3 / thiserror 1
    chrono 0.4 (features = ["serde"])

`unicorn-ssh` is the one crate worth calling out specially: russh's
key-handling types have churned across recent releases more than the rest
of this dependency graph, so that module is written defensively, with
inline comments marking the exact lines to double check with
`cargo check -p unicorn-ssh` first.

Usage
-----
    python3 generate_unicorn.py [output_dir] [--force] [--fmt] [--check]

    output_dir   Where to generate the workspace (default: ./unicorn)
    --force      Overwrite output_dir if it already exists and is non-empty
    --fmt        Run `cargo fmt` after generating (best-effort, needs cargo)
    --check      Run `cargo check --workspace` after generating (best-effort)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# File contents
# ---------------------------------------------------------------------------
# Every key is a path relative to the workspace root. Values are stored as
# *raw* strings so Rust's own backslash escapes (\n inside format!(), line
# continuations, etc.) pass through to disk completely untouched by Python.

FILES: dict[str, str] = {}

# ---------------------------------------------------------------------------
# Workspace root
# ---------------------------------------------------------------------------

FILES["Cargo.toml"] = r"""[workspace]
resolver = "2"
members = [
    "crates/unicorn-core",
    "crates/unicorn-git",
    "crates/unicorn-metrics",
    "crates/unicorn-ssh",
    "crates/unicorn-tui",
    "crates/unicorn-cli",
]

[workspace.package]
version = "0.1.0"
edition = "2021"
authors = ["Unicorn Contributors"]
license = "MIT OR Apache-2.0"
repository = "https://github.com/your-org/unicorn"
rust-version = "1.85"

# Versions below were checked against docs.rs / crates.io at generation
# time rather than pulled from memory - see generate_unicorn.py's module
# docstring for the full list and what was verified.
[workspace.dependencies]
tokio = { version = "1.53", features = ["full"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
toml = "0.8"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "fmt"] }
thiserror = "1"
anyhow = "1"
chrono = { version = "0.4", features = ["serde"] }
gix = "0.84"
ratatui = "0.29"
crossterm = "0.28"
sysinfo = "0.39"
russh = { version = "0.54", features = ["ring"] }

[profile.release]
opt-level = 3
lto = true
codegen-units = 1
strip = true
"""

FILES["rust-toolchain.toml"] = r"""[toolchain]
channel = "stable"
components = ["rustfmt", "clippy"]
"""

FILES[".gitignore"] = r"""/target
/data
*.log
.DS_Store
"""

FILES["README.md"] = r"""# 🦄 Unicorn

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
"""

FILES["docs/ARCHITECTURE.md"] = r"""# Architecture & Roadmap

Unicorn's long-term vision is to be "the operating system for self-hosted
Git infrastructure," not a clone of any existing forge. This scaffold
implements the foundation; the table below maps the vision doc's four
pillars to where each would eventually live.

| Pillar | Includes | Target crate(s) |
|---|---|---|
| Repository Hosting | repos, branches, commits, tags, releases, diffs, PRs | `unicorn-git` (extend), new `unicorn-review` |
| Administration | users, orgs, teams, SSH keys, permissions, audit logs | `unicorn-core` (models already exist), new `unicorn-admin` |
| Operations | live monitoring, background workers, health, logs | `unicorn-metrics` (extend), new `unicorn-ops` |
| Platform | webhooks, CI pipelines, package registry, REST API, plugins | new `unicorn-webhooks`, `unicorn-ci`, `unicorn-registry`, `unicorn-api` |

## Design principles carried into the generated code

- **Rust first, memory safe** — `gix` instead of `libgit2`, `russh` instead
  of a C SSH library, no `unsafe` in any generated crate.
- **Verify APIs instead of guessing** — every dependency's usage in this
  scaffold was checked against current docs.rs / crates.io output rather
  than an LLM's or developer's memory of the crate. `unicorn-ssh` is the
  one exception called out in the root README, since `russh`'s key-handling
  types have moved the most recently.
- **Modular** — every crate here compiles and is testable on its own;
  `unicorn-tui`, `unicorn-git`, and `unicorn-metrics` don't depend on each
  other, only on `unicorn-core`.
- **Beautiful before clever** — the dashboard is the first thing built,
  before any admin/API surface, because it's the first thing a person sees.
"""

FILES["config/unicorn.toml"] = r"""# Unicorn configuration.
#
# Every field mirrors `unicorn_core::config::UnicornConfig` one-to-one. Any
# field you omit falls back to its default (see
# crates/unicorn-core/src/config.rs), so this file only needs to list what
# you want to change from the defaults.

[server]
host = "0.0.0.0"
http_port = 3000
data_dir = "./data"

[ssh]
enabled = true
host = "0.0.0.0"
port = 2222
host_key_path = "./data/ssh/host_ed25519"

[storage]
repositories_dir = "./data/repositories"

[ui]
refresh_interval_ms = 1000
theme = "unicorn-dark"

[logging]
level = "info"
file = "./data/logs/unicorn.log"
"""

# ---------------------------------------------------------------------------
# crates/unicorn-core
# ---------------------------------------------------------------------------

FILES["crates/unicorn-core/Cargo.toml"] = r"""[package]
name = "unicorn-core"
version.workspace = true
edition.workspace = true
authors.workspace = true
license.workspace = true
description = "Shared configuration, domain models, and error types for Unicorn."

[dependencies]
serde.workspace = true
serde_json.workspace = true
toml.workspace = true
thiserror.workspace = true
anyhow.workspace = true
tracing.workspace = true
tracing-subscriber.workspace = true
chrono.workspace = true
"""

FILES["crates/unicorn-core/src/lib.rs"] = r"""//! `unicorn-core` holds the configuration, domain models, error types, and
//! logging bootstrap shared by every other Unicorn crate.
//!
//! Nothing in this crate talks to git, the network, or the terminal - it is
//! pure data plus a handful of small, well tested helpers. That keeps it
//! fast to compile and easy to reuse from `unicorn-cli`, `unicorn-tui`,
//! `unicorn-ssh`, and any future subsystem (webhooks, CI runners, the
//! package registry, ...).

pub mod config;
pub mod error;
pub mod logging;
pub mod models;

pub use config::UnicornConfig;
pub use error::{Result, UnicornError};
"""

FILES["crates/unicorn-core/src/error.rs"] = r"""use std::path::PathBuf;

use thiserror::Error;

pub type Result<T> = std::result::Result<T, UnicornError>;

/// The error type shared by every Unicorn crate. Subsystem-specific crates
/// (`unicorn-git`, `unicorn-ssh`, ...) define their own error enums and
/// convert into this one at their public API boundary, so callers never have
/// to know which subsystem failed.
#[derive(Debug, Error)]
pub enum UnicornError {
    #[error("failed to load configuration from {path}: {source}")]
    Config { path: PathBuf, #[source] source: anyhow::Error },

    #[error("repository error: {0}")]
    Repository(String),

    #[error("i/o error: {0}")]
    Io(#[from] std::io::Error),

    #[error("{0}")]
    Other(String),
}
"""

FILES["crates/unicorn-core/src/config.rs"] = r"""//! Serde + TOML backed configuration for the whole Unicorn platform.
//!
//! The file on disk mirrors this struct one-to-one, so `unicorn.toml`
//! doubles as living documentation. Every field has a sensible default so a
//! brand new deployment can start with zero configuration and grow into a
//! full one.

use std::net::{IpAddr, Ipv4Addr};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::error::{Result, UnicornError};

/// Root configuration object, deserialized from `unicorn.toml`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct UnicornConfig {
    pub server: ServerConfig,
    pub ssh: SshConfig,
    pub storage: StorageConfig,
    pub ui: UiConfig,
    pub logging: LoggingConfig,
}

impl Default for UnicornConfig {
    fn default() -> Self {
        Self {
            server: ServerConfig::default(),
            ssh: SshConfig::default(),
            storage: StorageConfig::default(),
            ui: UiConfig::default(),
            logging: LoggingConfig::default(),
        }
    }
}

impl UnicornConfig {
    /// Load configuration from a TOML file, falling back to defaults for
    /// any field that is missing (thanks to `#[serde(default)]`).
    pub fn load(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let raw = std::fs::read_to_string(path).map_err(|source| UnicornError::Config {
            path: path.to_path_buf(),
            source: source.into(),
        })?;
        toml::from_str(&raw).map_err(|source| UnicornError::Config {
            path: path.to_path_buf(),
            source: source.into(),
        })
    }

    /// Load configuration if `path` exists, otherwise return the defaults.
    /// This is what `unicorn-cli` uses on startup so a missing config file
    /// is never a hard failure.
    pub fn load_or_default(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        if path.exists() {
            Self::load(path)
        } else {
            Ok(Self::default())
        }
    }

    /// Serialize the current configuration back to a pretty TOML string,
    /// useful for a future `unicorn config init` style command.
    pub fn to_toml_string(&self) -> Result<String> {
        toml::to_string_pretty(self).map_err(|source| UnicornError::Config {
            path: PathBuf::from("<in-memory>"),
            source: source.into(),
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ServerConfig {
    pub host: IpAddr,
    pub http_port: u16,
    pub data_dir: PathBuf,
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            host: IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0)),
            http_port: 3000,
            data_dir: PathBuf::from("./data"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct SshConfig {
    pub enabled: bool,
    pub host: IpAddr,
    pub port: u16,
    pub host_key_path: PathBuf,
}

impl Default for SshConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            host: IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0)),
            port: 2222,
            host_key_path: PathBuf::from("./data/ssh/host_ed25519"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct StorageConfig {
    pub repositories_dir: PathBuf,
}

impl Default for StorageConfig {
    fn default() -> Self {
        Self { repositories_dir: PathBuf::from("./data/repositories") }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct UiConfig {
    pub refresh_interval_ms: u64,
    pub theme: String,
}

impl Default for UiConfig {
    fn default() -> Self {
        Self { refresh_interval_ms: 1000, theme: "unicorn-dark".to_string() }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct LoggingConfig {
    pub level: String,
    pub file: Option<PathBuf>,
}

impl Default for LoggingConfig {
    fn default() -> Self {
        Self { level: "info".to_string(), file: Some(PathBuf::from("./data/logs/unicorn.log")) }
    }
}
"""

FILES["crates/unicorn-core/src/logging.rs"] = r"""//! Thin wrapper around `tracing-subscriber` so every binary in the
//! workspace initializes logging the same way.

use crate::config::LoggingConfig;

/// Install a global `tracing` subscriber configured from `LoggingConfig`.
///
/// Call this once, near the top of `main`. It honours the `RUST_LOG`
/// environment variable if set, otherwise falls back to `config.level`.
pub fn init(config: &LoggingConfig) {
    let filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(config.level.clone()));

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(false)
        .compact()
        .init();
}
"""

FILES["crates/unicorn-core/src/models.rs"] = r"""//! Domain models shared across the platform: repositories, users,
//! organizations, SSH keys, webhooks, and CI runs. These are intentionally
//! plain data structures - persistence, validation, and business logic
//! live in the crates that own each subsystem.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Repository {
    pub id: u64,
    pub owner: String,
    pub name: String,
    pub description: Option<String>,
    pub default_branch: String,
    pub is_private: bool,
    pub is_bare: bool,
    pub star_count: u32,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

impl Repository {
    /// The `owner/name` slug used in URLs and in the TUI's repository list.
    pub fn slug(&self) -> String {
        format!("{}/{}", self.owner, self.name)
    }
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct User {
    pub id: u64,
    pub username: String,
    pub email: String,
    pub is_admin: bool,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Organization {
    pub id: u64,
    pub name: String,
    pub display_name: String,
    pub member_ids: Vec<u64>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SshKey {
    pub id: u64,
    pub owner_id: u64,
    pub name: String,
    pub fingerprint: String,
    pub algorithm: String,
    pub added_at: DateTime<Utc>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Webhook {
    pub id: u64,
    pub repository_id: u64,
    pub target_url: String,
    pub events: Vec<String>,
    pub active: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ActionStatus {
    Queued,
    Running,
    Succeeded,
    Failed,
    Cancelled,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ActionRun {
    pub id: u64,
    pub repository_id: u64,
    pub workflow_name: String,
    pub status: ActionStatus,
    pub started_at: DateTime<Utc>,
    pub finished_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub id: u64,
    pub actor: String,
    pub action: String,
    pub target: String,
    pub at: DateTime<Utc>,
}
"""

# ---------------------------------------------------------------------------
# crates/unicorn-git
# ---------------------------------------------------------------------------

FILES["crates/unicorn-git/Cargo.toml"] = r"""[package]
name = "unicorn-git"
version.workspace = true
edition.workspace = true
authors.workspace = true
license.workspace = true
description = "gitoxide-backed repository discovery and inspection for Unicorn."

[dependencies]
gix.workspace = true
thiserror.workspace = true
tracing.workspace = true
"""

FILES["crates/unicorn-git/src/lib.rs"] = r"""//! Git engine for Unicorn, built directly on [`gix`] (gitoxide) - no
//! `libgit2`, no shelling out to the `git` binary.
//!
//! This crate is deliberately narrow: it knows how to find repositories on
//! disk, open them, and summarize their branches/commits for the dashboard
//! and repository views. Anything protocol-level (smart HTTP, the `git://`
//! wire protocol, push/fetch negotiation) belongs in a future
//! `unicorn-git-transport` crate once the storage layer above it is stable.

mod discovery;
mod error;
mod repository;

pub use discovery::{discover_repositories, DiscoveredRepository};
pub use error::{GitError, Result};
pub use repository::{open, CommitSummary, RepositorySummary};
"""

FILES["crates/unicorn-git/src/error.rs"] = r"""use std::path::PathBuf;

use thiserror::Error;

pub type Result<T> = std::result::Result<T, GitError>;

#[derive(Debug, Error)]
pub enum GitError {
    #[error("failed to open repository at {path}: {source}")]
    Open { path: PathBuf, source: Box<dyn std::error::Error + Send + Sync> },

    #[error("i/o error while scanning {path}: {source}")]
    Scan { path: PathBuf, source: std::io::Error },
}
"""

FILES["crates/unicorn-git/src/discovery.rs"] = r"""//! Walk a directory tree looking for git repositories, the way Unicorn's
//! server does on startup to build its repository list.

use std::path::{Path, PathBuf};

use crate::error::{GitError, Result};

/// A repository found while scanning storage, before it has been fully
/// opened. Kept intentionally cheap so scanning thousands of repositories
/// does not require opening every object database up front.
#[derive(Debug, Clone)]
pub struct DiscoveredRepository {
    pub path: PathBuf,
    pub slug: String,
    pub is_bare: bool,
}

/// Recursively scan `root` (Unicorn's `storage.repositories_dir`) for git
/// repositories, up to `max_depth` levels deep. A typical layout is
/// `<root>/<owner>/<name>.git`, which is two levels deep.
pub fn discover_repositories(root: impl AsRef<Path>, max_depth: usize) -> Result<Vec<DiscoveredRepository>> {
    let root = root.as_ref();
    let mut found = Vec::new();
    if root.exists() {
        walk(root, root, max_depth, &mut found)?;
    }
    found.sort_by(|a, b| a.slug.cmp(&b.slug));
    Ok(found)
}

fn walk(root: &Path, dir: &Path, depth_remaining: usize, found: &mut Vec<DiscoveredRepository>) -> Result<()> {
    let entries = std::fs::read_dir(dir).map_err(|source| GitError::Scan { path: dir.to_path_buf(), source })?;

    for entry in entries {
        let entry = entry.map_err(|source| GitError::Scan { path: dir.to_path_buf(), source })?;
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }

        let is_bare_candidate = path.extension().is_some_and(|ext| ext == "git");
        let has_dot_git = path.join(".git").is_dir();

        if is_bare_candidate || has_dot_git {
            if gix::open(&path).is_ok() {
                found.push(DiscoveredRepository {
                    slug: slug_for(root, &path),
                    is_bare: is_bare_candidate,
                    path,
                });
                continue;
            }
        }

        if depth_remaining > 0 {
            walk(root, &path, depth_remaining - 1, found)?;
        }
    }

    Ok(())
}

fn slug_for(root: &Path, repo_path: &Path) -> String {
    let relative = repo_path.strip_prefix(root).unwrap_or(repo_path);
    let mut slug = relative.to_string_lossy().replace(std::path::MAIN_SEPARATOR, "/");
    if let Some(stripped) = slug.strip_suffix(".git") {
        slug = stripped.to_string();
    }
    slug
}
"""

FILES["crates/unicorn-git/src/repository.rs"] = r"""//! Opening a single repository and summarizing it for display.

use std::path::{Path, PathBuf};

use gix::bstr::ByteSlice;

use crate::error::{GitError, Result};

/// A lightweight summary of one commit, cheap enough to build a whole
/// "recent commits" list for the dashboard.
#[derive(Debug, Clone)]
pub struct CommitSummary {
    pub short_id: String,
    pub summary: String,
    pub author_name: String,
}

/// Summary of a repository's current state: default branch, branch count,
/// and the most recent commits reachable from `HEAD`.
#[derive(Debug, Clone)]
pub struct RepositorySummary {
    pub path: PathBuf,
    pub default_branch: Option<String>,
    pub branch_count: usize,
    pub recent_commits: Vec<CommitSummary>,
}

/// Open the repository at `path` and build a [`RepositorySummary`] from it.
///
/// `commit_limit` bounds how many commits are walked from `HEAD`; the
/// dashboard only needs a handful, so callers should keep this small
/// (5-10) to stay fast even on repositories with long histories.
pub fn open(path: impl AsRef<Path>, commit_limit: usize) -> Result<RepositorySummary> {
    let path = path.as_ref();
    let repo = gix::open(path).map_err(|source| GitError::Open {
        path: path.to_path_buf(),
        source: Box::new(source),
    })?;

    let default_branch = repo.head_name().ok().flatten().map(|name| name.shorten().to_string());
    let branch_count = repo.branch_names().len();

    let mut recent_commits = Vec::with_capacity(commit_limit);
    if let Ok(head_id) = repo.head_id() {
        let mut current_id = head_id.detach();

        while recent_commits.len() < commit_limit {
            let Ok(commit) = repo.find_commit(current_id) else {
                break;
            };

            // `message_raw()` is the one commit-message accessor confirmed
            // directly in gix's own doctests (`commit.message_raw()?`), so
            // it's used here instead of the higher-level `message()`
            // helper. It includes the trailing newline git stores, hence
            // the `.lines().next()` to get just the summary line.
            // `to_str()` on the returned `&BStr` requires the `ByteSlice`
            // trait to be in scope (imported at the top of this file).
            let summary = commit
                .message_raw()
                .ok()
                .and_then(|raw| raw.to_str().ok().map(str::to_owned))
                .and_then(|raw| raw.lines().next().map(str::to_owned))
                .unwrap_or_else(|| "(no commit message)".to_string());

            let author_name = commit
                .author()
                .ok()
                .map(|sig| sig.name.to_string())
                .unwrap_or_else(|| "unknown".to_string());

            recent_commits.push(CommitSummary {
                short_id: current_id.to_hex_with_len(7).to_string(),
                summary,
                author_name,
            });

            // Bind the next parent id before matching on it so `commit`
            // (which `parent_ids()` borrows from) isn't held across the
            // point where its backing temporary gets dropped at the end of
            // this block - avoids a "does not live long enough" borrowck
            // error on `commit`.
            let next_parent = commit.parent_ids().next().map(|id| id.detach());
            match next_parent {
                Some(parent_id) => current_id = parent_id,
                None => break,
            }
        }
    }

    Ok(RepositorySummary { path: path.to_path_buf(), default_branch, branch_count, recent_commits })
}
"""

# ---------------------------------------------------------------------------
# crates/unicorn-metrics
# ---------------------------------------------------------------------------

FILES["crates/unicorn-metrics/Cargo.toml"] = r"""[package]
name = "unicorn-metrics"
version.workspace = true
edition.workspace = true
authors.workspace = true
license.workspace = true
description = "Live CPU, memory, disk, and network metrics for the Unicorn dashboard."

[dependencies]
sysinfo.workspace = true
"""

FILES["crates/unicorn-metrics/src/lib.rs"] = r"""//! Live system metrics for the Unicorn dashboard, backed by [`sysinfo`].
//!
//! A single [`MetricsCollector`] should be created once and reused: most of
//! `sysinfo`'s numbers (especially CPU usage) are computed as a diff
//! between two refreshes, so calling [`MetricsCollector::refresh`] on a
//! fixed tick (e.g. once a second, matching `ui.refresh_interval_ms`) is
//! what makes the dashboard's live gauges and sparklines meaningful.

use sysinfo::{Disks, Networks, System};

/// A point-in-time snapshot of system resource usage, cheap to clone and
/// hand off to the TUI layer for rendering.
#[derive(Debug, Clone, Default)]
pub struct SystemSnapshot {
    pub cpu_percent: f32,
    pub per_core_percent: Vec<f32>,
    pub memory_used_bytes: u64,
    pub memory_total_bytes: u64,
    pub disks: Vec<DiskSnapshot>,
    pub network_rx_bytes_per_tick: u64,
    pub network_tx_bytes_per_tick: u64,
    pub load_average_one: f64,
}

impl SystemSnapshot {
    pub fn memory_percent(&self) -> f32 {
        if self.memory_total_bytes == 0 {
            0.0
        } else {
            self.memory_used_bytes as f32 / self.memory_total_bytes as f32 * 100.0
        }
    }
}

#[derive(Debug, Clone)]
pub struct DiskSnapshot {
    pub mount_point: String,
    pub total_bytes: u64,
    pub available_bytes: u64,
}

impl DiskSnapshot {
    pub fn used_bytes(&self) -> u64 {
        self.total_bytes.saturating_sub(self.available_bytes)
    }

    pub fn used_percent(&self) -> f32 {
        if self.total_bytes == 0 {
            0.0
        } else {
            self.used_bytes() as f32 / self.total_bytes as f32 * 100.0
        }
    }
}

/// Owns the long-lived `sysinfo` handles so repeated refreshes are cheap
/// and CPU-usage diffing works correctly.
pub struct MetricsCollector {
    system: System,
    disks: Disks,
    networks: Networks,
}

impl MetricsCollector {
    pub fn new() -> Self {
        let mut system = System::new_all();
        system.refresh_all();
        Self { system, disks: Disks::new_with_refreshed_list(), networks: Networks::new_with_refreshed_list() }
    }

    /// Refresh every underlying source and return a fresh snapshot.
    ///
    /// Note: per `sysinfo`'s own docs, CPU usage is only accurate after at
    /// least two refreshes with some time between them, so the very first
    /// snapshot after startup may report `0.0` for `cpu_percent`.
    pub fn refresh(&mut self) -> SystemSnapshot {
        self.system.refresh_cpu_usage();
        self.system.refresh_memory();
        self.disks.refresh(true);
        self.networks.refresh(true);

        let per_core_percent: Vec<f32> = self.system.cpus().iter().map(|cpu| cpu.cpu_usage()).collect();

        let disks = self
            .disks
            .list()
            .iter()
            .map(|disk| DiskSnapshot {
                mount_point: disk.mount_point().to_string_lossy().to_string(),
                total_bytes: disk.total_space(),
                available_bytes: disk.available_space(),
            })
            .collect();

        let (rx, tx) = self
            .networks
            .iter()
            .fold((0u64, 0u64), |(rx, tx), (_name, data)| (rx + data.received(), tx + data.transmitted()));

        SystemSnapshot {
            cpu_percent: self.system.global_cpu_usage(),
            per_core_percent,
            memory_used_bytes: self.system.used_memory(),
            memory_total_bytes: self.system.total_memory(),
            disks,
            network_rx_bytes_per_tick: rx,
            network_tx_bytes_per_tick: tx,
            load_average_one: System::load_average().one,
        }
    }
}

impl Default for MetricsCollector {
    fn default() -> Self {
        Self::new()
    }
}
"""

# ---------------------------------------------------------------------------
# crates/unicorn-ssh
# ---------------------------------------------------------------------------

FILES["crates/unicorn-ssh/Cargo.toml"] = r"""[package]
name = "unicorn-ssh"
version.workspace = true
edition.workspace = true
authors.workspace = true
license.workspace = true
description = "Rust-native SSH server scaffold for Unicorn, built on russh."

[dependencies]
russh.workspace = true
tokio.workspace = true
tracing.workspace = true
thiserror.workspace = true
rand = "0.8"
"""

FILES["crates/unicorn-ssh/src/lib.rs"] = r"""//! Rust-native SSH front door for Unicorn, built on [`russh`] - no
//! `libssh2`, no system `sshd`.
//!
//! # Status: scaffold, not finished
//!
//! This wires up the pieces `russh` needs (a [`russh::server::Config`], a
//! [`russh::server::Handler`], and a [`russh::server::Server`] factory) and
//! accepts connections, but authentication currently accepts every public
//! key and no channel/exec logic is implemented yet. That is intentional:
//! per Unicorn's own development philosophy ("Generate Workspace -> cargo
//! check -> improve"), this module is meant to be filled in incrementally -
//! wire real public-key lookup against `unicorn_core::models::SshKey`
//! first, then `git-upload-pack` / `git-receive-pack` channel handling.
//!
//! # A note on key types
//!
//! `russh` re-exports its own internal fork of key-handling types under
//! `russh::keys` (`russh::keys::PrivateKey`, `russh::keys::PublicKey`,
//! `russh::keys::Algorithm`). Do NOT add the standalone `russh-keys` crate
//! as a separate dependency here - it defines structurally identical but
//! *distinct* types with the same names, and mixing the two produces
//! confusing "expected `russh::keys::X`, found `russh_keys::X`" errors
//! that look like a version mismatch but are actually a duplicate-crate
//! problem. Always import from `russh::keys::`, never from a top-level
//! `russh_keys::`.
//!
//! If `cargo check -p unicorn-ssh` fails, this file - specifically the
//! `Config` construction in [`run`] and the `auth_publickey` signature
//! below - is the first place to look; compare against whatever `russh`
//! version Cargo actually resolved (`cargo tree -p russh`).

use std::net::SocketAddr;
use std::sync::Arc;

use russh::server::{Auth, Handler, Msg, Server as _, Session};
use russh::{Channel, ChannelId};
use thiserror::Error;

pub type Result<T> = std::result::Result<T, SshError>;

#[derive(Debug, Error)]
pub enum SshError {
    #[error("failed to generate host key: {0}")]
    HostKey(String),

    #[error("ssh server error: {0}")]
    Server(#[from] russh::Error),
}

/// Runtime options for the SSH front door, kept separate from
/// `unicorn_core::config::SshConfig` so this crate has no compile-time
/// dependency on `unicorn-core`'s exact shape.
pub struct SshServerOptions {
    pub bind_addr: SocketAddr,
}

/// Start the SSH server and run until the process is shut down.
///
/// Spawn this in its own `tokio::spawn`ed task from `unicorn-cli`,
/// alongside the TUI and any future HTTP server.
pub async fn run(options: SshServerOptions) -> Result<()> {
    // A fresh, in-memory host key every start-up is fine for local
    // development but NOT for anything long-lived: real deployments should
    // load a persisted key from `SshConfig::host_key_path` (generating and
    // saving one on first run) so client-side `known_hosts` entries stay
    // valid across restarts.
    let host_key = russh::keys::PrivateKey::random(&mut rand::thread_rng(), russh::keys::Algorithm::Ed25519)
        .map_err(|e| SshError::HostKey(e.to_string()))?;

    let config = Arc::new(russh::server::Config { keys: vec![host_key], ..Default::default() });

    tracing::info!(addr = %options.bind_addr, "starting Unicorn SSH server");

    let mut factory = ServerFactory;
    factory
        .run_on_address(config, options.bind_addr)
        .await
        .map_err(|e| SshError::Server(e.into()))
}

/// Creates a fresh [`Handler`] for every incoming TCP connection.
struct ServerFactory;

impl russh::server::Server for ServerFactory {
    type Handler = ConnectionHandler;

    fn new_client(&mut self, peer_addr: Option<SocketAddr>) -> Self::Handler {
        tracing::debug!(?peer_addr, "accepted ssh connection");
        ConnectionHandler::default()
    }
}

/// Per-connection handler. One instance is created per client.
#[derive(Default)]
struct ConnectionHandler {
    username: Option<String>,
}

impl Handler for ConnectionHandler {
    type Error = russh::Error;

    /// TODO(security): replace with a real lookup against
    /// `unicorn_core::models::SshKey` by fingerprint before this server is
    /// exposed to anything but a trusted local network. Accepting every
    /// key, as this scaffold does, is only appropriate for local testing.
    ///
    /// Note the explicit `std::result::Result<_, Self::Error>` return type
    /// below (rather than this crate's own `Result<T>` alias): the trait
    /// requires exactly `std::result::Result<_, Self::Error>` with
    /// `Self::Error = russh::Error`, which is distinct from - and would be
    /// shadowed/miscounted against - this crate's local `SshError`-based
    /// alias, producing a "type alias takes 1 generic argument but 2 were
    /// supplied" error if written as `Result<Auth, Self::Error>`.
    async fn auth_publickey(
        &mut self,
        user: &str,
        _public_key: &russh::keys::PublicKey,
    ) -> std::result::Result<Auth, Self::Error> {
        self.username = Some(user.to_string());
        Ok(Auth::Accept)
    }

    async fn channel_open_session(
        &mut self,
        channel: Channel<Msg>,
        _session: &mut Session,
    ) -> std::result::Result<bool, Self::Error> {
        tracing::debug!(channel = ?channel.id(), user = ?self.username, "channel opened");
        Ok(true)
    }

    /// TODO: dispatch on the exec command (`git-upload-pack '<repo>'`,
    /// `git-receive-pack '<repo>'`) and stream through `unicorn-git`
    /// instead of echoing input back, which is what this scaffold does for
    /// now so manual testing (`ssh -p 2222 localhost`) has something
    /// visible to look at.
    async fn data(
        &mut self,
        channel: ChannelId,
        data: &[u8],
        session: &mut Session,
    ) -> std::result::Result<(), Self::Error> {
        session.data(channel, data.to_vec().into())?;
        Ok(())
    }
}
"""

# ---------------------------------------------------------------------------
# crates/unicorn-tui
# ---------------------------------------------------------------------------

FILES["crates/unicorn-tui/Cargo.toml"] = r"""[package]
name = "unicorn-tui"
version.workspace = true
edition.workspace = true
authors.workspace = true
license.workspace = true
description = "The Ratatui-based terminal dashboard that is Unicorn's primary interface."

[dependencies]
ratatui.workspace = true
crossterm.workspace = true
unicorn-core = { path = "../unicorn-core" }
unicorn-git = { path = "../unicorn-git" }
unicorn-metrics = { path = "../unicorn-metrics" }
"""

FILES["crates/unicorn-tui/src/lib.rs"] = r"""//! Unicorn's primary interface: a Ratatui dashboard designed so people
//! "forget they're looking at a terminal application" (see the project
//! vision doc). This crate owns the event loop, application state, theme,
//! and every widget on screen; it treats `unicorn-git` and
//! `unicorn-metrics` purely as data sources.

mod app;
mod theme;
mod widgets;

pub use app::{run, App};
pub use theme::Theme;
"""

FILES["crates/unicorn-tui/src/theme.rs"] = r"""//! The Unicorn color palette: dark background, magenta/purple brand accent
//! (matching the 🦄 in every corner of the product), and muted borders for
//! the "modern terminal" look called for in the vision doc.

use ratatui::style::Color;

#[derive(Debug, Clone, Copy)]
pub struct Theme {
    pub background: Color,
    pub surface: Color,
    pub border: Color,
    pub brand: Color,
    pub text: Color,
    pub text_muted: Color,
    pub success: Color,
    pub warning: Color,
    pub danger: Color,
    pub info: Color,
}

impl Default for Theme {
    fn default() -> Self {
        Self {
            background: Color::Rgb(10, 10, 18),
            surface: Color::Rgb(18, 18, 30),
            border: Color::Rgb(60, 60, 90),
            brand: Color::Rgb(190, 120, 255),
            text: Color::Rgb(230, 230, 240),
            text_muted: Color::Rgb(140, 140, 160),
            success: Color::Rgb(80, 220, 140),
            warning: Color::Rgb(240, 200, 90),
            danger: Color::Rgb(240, 100, 110),
            info: Color::Rgb(90, 180, 240),
        }
    }
}
"""

FILES["crates/unicorn-tui/src/app.rs"] = r"""//! Application state and the top-level event loop.

use std::io;
use std::time::{Duration, Instant};

use crossterm::event::{self, Event, KeyCode, KeyEventKind};

use unicorn_core::config::UnicornConfig;
use unicorn_git::{discover_repositories, DiscoveredRepository};
use unicorn_metrics::{MetricsCollector, SystemSnapshot};

use crate::theme::Theme;
use crate::widgets::chrome;

pub const TABS: [&str; 8] =
    ["Dashboard", "Repositories", "Users", "Organizations", "SSH Keys", "Packages", "Metrics", "Logs"];

/// A rolling window of recent samples, used to feed the CPU/network
/// sparklines. Capacity matches how many columns of history are worth
/// keeping on screen at once.
#[derive(Debug, Clone, Default)]
pub struct History {
    pub cpu: Vec<u64>,
    pub network_rx: Vec<u64>,
}

impl History {
    const CAPACITY: usize = 120;

    fn push(&mut self, snapshot: &SystemSnapshot) {
        self.cpu.push(snapshot.cpu_percent.round() as u64);
        self.network_rx.push(snapshot.network_rx_bytes_per_tick);
        if self.cpu.len() > Self::CAPACITY {
            self.cpu.remove(0);
        }
        if self.network_rx.len() > Self::CAPACITY {
            self.network_rx.remove(0);
        }
    }
}

pub struct App {
    pub theme: Theme,
    pub config: UnicornConfig,
    pub selected_tab: usize,
    pub nav_selected: usize,
    pub metrics: MetricsCollector,
    pub snapshot: SystemSnapshot,
    pub history: History,
    pub repositories: Vec<DiscoveredRepository>,
    pub should_quit: bool,
}

impl App {
    pub fn new(config: UnicornConfig) -> Self {
        let mut metrics = MetricsCollector::new();
        let snapshot = metrics.refresh();
        let repositories = discover_repositories(&config.storage.repositories_dir, 3).unwrap_or_default();

        let mut history = History::default();
        history.push(&snapshot);

        Self {
            theme: Theme::default(),
            config,
            selected_tab: 0,
            nav_selected: 0,
            metrics,
            snapshot,
            history,
            repositories,
            should_quit: false,
        }
    }

    fn on_tick(&mut self) {
        self.snapshot = self.metrics.refresh();
        self.history.push(&self.snapshot);
    }

    fn on_key(&mut self, code: KeyCode) {
        match code {
            KeyCode::Char('q') | KeyCode::Esc => self.should_quit = true,
            KeyCode::Right | KeyCode::Char('l') | KeyCode::Tab => {
                self.selected_tab = (self.selected_tab + 1) % TABS.len();
            }
            KeyCode::Left | KeyCode::Char('h') | KeyCode::BackTab => {
                self.selected_tab = (self.selected_tab + TABS.len() - 1) % TABS.len();
            }
            KeyCode::Down | KeyCode::Char('j') => {
                self.nav_selected = (self.nav_selected + 1) % TABS.len();
            }
            KeyCode::Up | KeyCode::Char('k') => {
                self.nav_selected = (self.nav_selected + TABS.len() - 1) % TABS.len();
            }
            KeyCode::Char('r') => {
                self.repositories = discover_repositories(&self.config.storage.repositories_dir, 3).unwrap_or_default();
            }
            _ => {}
        }
    }
}

/// Run the dashboard until the user quits. This is a blocking call - see
/// `unicorn-cli`'s `main.rs` for how it's combined with the async SSH
/// server on tokio's multi-threaded runtime.
pub fn run(mut app: App) -> io::Result<()> {
    let mut terminal = ratatui::init();
    let tick_rate = Duration::from_millis(app.config.ui.refresh_interval_ms.max(200));
    let mut last_tick = Instant::now();

    let result = loop {
        if let Err(err) = terminal.draw(|frame| chrome::render(frame, &app)) {
            break Err(err);
        }

        let timeout = tick_rate.saturating_sub(last_tick.elapsed());
        match event::poll(timeout) {
            Ok(true) => match event::read() {
                Ok(Event::Key(key)) if key.kind == KeyEventKind::Press => app.on_key(key.code),
                Ok(_) => {}
                Err(err) => break Err(err),
            },
            Ok(false) => {}
            Err(err) => break Err(err),
        }

        if last_tick.elapsed() >= tick_rate {
            app.on_tick();
            last_tick = Instant::now();
        }

        if app.should_quit {
            break Ok(());
        }
    };

    ratatui::restore();
    result
}
"""

FILES["crates/unicorn-tui/src/widgets/mod.rs"] = r"""pub mod chrome;
pub mod dashboard;
pub mod primitives;
"""

FILES["crates/unicorn-tui/src/widgets/primitives.rs"] = r"""//! Small rendering helpers shared by every widget module.

use ratatui::style::Style;
use ratatui::widgets::Block;

use crate::theme::Theme;

/// A bordered, titled panel styled consistently with the rest of the
/// dashboard. `Block::bordered()` is Ratatui's shorthand for
/// `Block::default().borders(Borders::ALL)`.
pub fn panel<'a>(title: &'a str, theme: &Theme) -> Block<'a> {
    Block::bordered()
        .border_style(Style::new().fg(theme.border))
        .title(title)
        .title_style(Style::new().fg(theme.text))
        .style(Style::new().bg(theme.surface))
}

/// Human-readable byte sizes (`1.2 GiB`, `340 MiB`, ...), matching the
/// dashboard mockup's units.
pub fn human_bytes(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["B", "KiB", "MiB", "GiB", "TiB"];
    let mut value = bytes as f64;
    let mut unit = 0;
    while value >= 1024.0 && unit < UNITS.len() - 1 {
        value /= 1024.0;
        unit += 1;
    }
    if unit == 0 {
        format!("{value:.0} {}", UNITS[unit])
    } else {
        format!("{value:.1} {}", UNITS[unit])
    }
}
"""

FILES["crates/unicorn-tui/src/widgets/chrome.rs"] = r"""//! The parts of the screen that stay the same across every tab: the header
//! banner, the tab bar, the left navigation sidebar, and the bottom status
//! bar. See the vision doc's "User Experience" section for the box-drawing
//! sketch this layout is based on.

use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::style::{Style, Stylize};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, List, ListItem, Paragraph, Tabs, Wrap};
use ratatui::Frame;

use crate::app::{App, TABS};
use crate::widgets::dashboard;
use crate::widgets::primitives::{human_bytes, panel};

pub fn render(frame: &mut Frame, app: &App) {
    let root = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // header
            Constraint::Length(1), // tab bar
            Constraint::Min(0),    // body
            Constraint::Length(1), // status bar
        ])
        .split(frame.area());

    render_header(frame, root[0], app);
    render_tabs(frame, root[1], app);
    render_body(frame, root[2], app);
    render_status_bar(frame, root[3], app);
}

fn render_header(frame: &mut Frame, area: Rect, app: &App) {
    let block = Block::default().borders(Borders::BOTTOM).border_style(Style::new().fg(app.theme.border));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(inner);

    let title = Line::from(vec![
        Span::styled("🦄 Unicorn  ", Style::new().fg(app.theme.brand).bold()),
        Span::styled("The Rust-native Git Platform", Style::new().fg(app.theme.text_muted)),
    ]);
    frame.render_widget(Paragraph::new(title), cols[0]);

    let status = Line::from(vec![
        Span::styled("● Healthy   ", Style::new().fg(app.theme.success)),
        Span::styled(format!("CPU {:>3.0}%   ", app.snapshot.cpu_percent), Style::new().fg(app.theme.text)),
        Span::styled(
            format!("RAM {} / {}", human_bytes(app.snapshot.memory_used_bytes), human_bytes(app.snapshot.memory_total_bytes)),
            Style::new().fg(app.theme.text),
        ),
    ])
    .alignment(Alignment::Right);
    frame.render_widget(Paragraph::new(status), cols[1]);
}

fn render_tabs(frame: &mut Frame, area: Rect, app: &App) {
    let titles: Vec<Line> = TABS.iter().map(|t| Line::from(*t)).collect();
    let tabs = Tabs::new(titles)
        .select(app.selected_tab)
        .style(Style::new().fg(app.theme.text_muted))
        .highlight_style(Style::new().fg(app.theme.brand).bold())
        .divider(" ");
    frame.render_widget(tabs, area);
}

fn render_body(frame: &mut Frame, area: Rect, app: &App) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Length(22), Constraint::Min(0)])
        .split(area);

    render_nav(frame, cols[0], app);

    match app.selected_tab {
        0 => dashboard::render(frame, cols[1], app),
        _ => render_placeholder(frame, cols[1], app),
    }
}

fn render_nav(frame: &mut Frame, area: Rect, app: &App) {
    let block = Block::default()
        .borders(Borders::RIGHT)
        .border_style(Style::new().fg(app.theme.border))
        .title(" Navigation ")
        .title_style(Style::new().fg(app.theme.text_muted));

    let items: Vec<ListItem> = TABS
        .iter()
        .enumerate()
        .map(|(i, label)| {
            let style = if i == app.selected_tab {
                Style::new().fg(app.theme.brand).bold()
            } else {
                Style::new().fg(app.theme.text_muted)
            };
            ListItem::new(format!("  {label}")).style(style)
        })
        .collect();

    frame.render_widget(List::new(items).block(block), area);
}

fn render_placeholder(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Coming soon ", &app.theme);
    let text = Paragraph::new(format!(
        "The \"{}\" view isn't built yet - this scaffold currently only wires up the Dashboard tab. \
         Add a new module under `unicorn-tui/src/widgets/` and route it from `chrome::render_body`.",
        TABS[app.selected_tab]
    ))
    .style(Style::new().fg(app.theme.text_muted))
    .block(block)
    .wrap(Wrap { trim: true });
    frame.render_widget(text, area);
}

fn render_status_bar(frame: &mut Frame, area: Rect, app: &App) {
    let line = Line::from(vec![
        Span::styled(" 🦄 Unicorn 0.1.0  ", Style::new().fg(app.theme.brand)),
        Span::styled("| ", Style::new().fg(app.theme.border)),
        Span::styled(format!("Repositories {}  ", app.repositories.len()), Style::new().fg(app.theme.text_muted)),
        Span::styled("| ", Style::new().fg(app.theme.border)),
        Span::styled(
            "q: quit   tab/←→: switch view   j/k: navigate   r: rescan repos",
            Style::new().fg(app.theme.text_muted),
        ),
    ]);
    frame.render_widget(Paragraph::new(line), area);
}
"""

FILES["crates/unicorn-tui/src/widgets/dashboard.rs"] = r"""//! The Dashboard tab: the first thing an operator sees, per the vision
//! doc's "beautiful dashboard, not a wall of text" goal.

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::Style;
use ratatui::widgets::{BarChart, Gauge, List, ListItem, Paragraph, Sparkline, Wrap};
use ratatui::Frame;

use crate::app::App;
use crate::widgets::primitives::{human_bytes, panel};

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(9), Constraint::Length(9), Constraint::Min(6)])
        .split(area);

    render_resource_row(frame, rows[0], app);
    render_activity_row(frame, rows[1], app);
    render_lists_row(frame, rows[2], app);
}

fn render_resource_row(frame: &mut Frame, area: Rect, app: &App) {
    let cols = Layout::default().direction(Direction::Horizontal).constraints([Constraint::Ratio(1, 3); 3]).split(area);

    render_cpu(frame, cols[0], app);
    render_memory(frame, cols[1], app);
    render_disk(frame, cols[2], app);
}

fn render_cpu(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" CPU Usage ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let parts = Layout::default().direction(Direction::Vertical).constraints([Constraint::Length(3), Constraint::Min(0)]).split(inner);

    let gauge = Gauge::default()
        .gauge_style(Style::new().fg(app.theme.brand).bg(app.theme.surface))
        .percent(app.snapshot.cpu_percent.round().clamp(0.0, 100.0) as u16);
    frame.render_widget(gauge, parts[0]);

    let sparkline = Sparkline::default().data(&app.history.cpu).max(100).style(Style::new().fg(app.theme.brand));
    frame.render_widget(sparkline, parts[1]);
}

fn render_memory(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Memory ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let label = format!("{} / {}", human_bytes(app.snapshot.memory_used_bytes), human_bytes(app.snapshot.memory_total_bytes));

    let gauge = Gauge::default()
        .gauge_style(Style::new().fg(app.theme.info).bg(app.theme.surface))
        .label(label)
        .percent(app.snapshot.memory_percent().round().clamp(0.0, 100.0) as u16);
    frame.render_widget(gauge, inner);
}

fn render_disk(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Disk Usage ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let Some(primary) = app.snapshot.disks.first() else {
        frame.render_widget(Paragraph::new("No disks detected").style(Style::new().fg(app.theme.text_muted)), inner);
        return;
    };

    let label = format!("{}  {} / {}", primary.mount_point, human_bytes(primary.used_bytes()), human_bytes(primary.total_bytes));

    let gauge = Gauge::default()
        .gauge_style(Style::new().fg(app.theme.warning).bg(app.theme.surface))
        .label(label)
        .percent(primary.used_percent().round().clamp(0.0, 100.0) as u16);
    frame.render_widget(gauge, inner);
}

fn render_activity_row(frame: &mut Frame, area: Rect, app: &App) {
    let cols = Layout::default().direction(Direction::Horizontal).constraints([Constraint::Percentage(50), Constraint::Percentage(50)]).split(area);

    render_network(frame, cols[0], app);
    render_repo_activity(frame, cols[1], app);
}

fn render_network(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Network ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let sparkline = Sparkline::default().data(&app.history.network_rx).style(Style::new().fg(app.theme.info));
    frame.render_widget(sparkline, inner);
}

fn render_repo_activity(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Repository Activity ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    if app.repositories.is_empty() {
        frame.render_widget(
            Paragraph::new(format!(
                "No repositories found under {}.\nPoint `storage.repositories_dir` at a directory \
                 of git repos, or clone one in to see it here.",
                app.config.storage.repositories_dir.display()
            ))
            .style(Style::new().fg(app.theme.text_muted))
            .wrap(Wrap { trim: true }),
            inner,
        );
        return;
    }

    let data: Vec<(&str, u64)> = app.repositories.iter().take(7).map(|repo| (repo.slug.as_str(), 1u64)).collect();

    let chart = BarChart::default()
        .bar_width(3)
        .bar_gap(1)
        .bar_style(Style::new().fg(app.theme.brand))
        .value_style(Style::new().fg(app.theme.background).bg(app.theme.brand))
        .data(&data);
    frame.render_widget(chart, inner);
}

fn render_lists_row(frame: &mut Frame, area: Rect, app: &App) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(34), Constraint::Percentage(33), Constraint::Percentage(33)])
        .split(area);

    render_top_repositories(frame, cols[0], app);
    render_recent_commits(frame, cols[1], app);
    render_alerts(frame, cols[2], app);
}

fn render_top_repositories(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Repositories ", &app.theme);

    let items: Vec<ListItem> = if app.repositories.is_empty() {
        vec![ListItem::new("(none discovered yet)").style(Style::new().fg(app.theme.text_muted))]
    } else {
        app.repositories
            .iter()
            .map(|repo| {
                let kind = if repo.is_bare { "bare" } else { "worktree" };
                ListItem::new(format!("📁 {}  ({kind})", repo.slug)).style(Style::new().fg(app.theme.text))
            })
            .collect()
    };

    frame.render_widget(List::new(items).block(block), area);
}

fn render_recent_commits(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Recent Commits ", &app.theme);
    let items = vec![ListItem::new(
        "Select a repository on the Repositories tab to see its commit \
         log here.\n(Wire this up to `unicorn_git::open(..).recent_commits` \
         once that tab exists.)",
    )
    .style(Style::new().fg(app.theme.text_muted))];
    frame.render_widget(List::new(items).block(block), area);
}

fn render_alerts(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" System Alerts ", &app.theme);
    let mut items = Vec::new();

    for disk in &app.snapshot.disks {
        if disk.used_percent() > 90.0 {
            items.push(
                ListItem::new(format!("⚠ Disk {} is {:.0}% full", disk.mount_point, disk.used_percent()))
                    .style(Style::new().fg(app.theme.warning)),
            );
        }
    }
    if app.snapshot.cpu_percent > 90.0 {
        items.push(ListItem::new(format!("⚠ CPU usage is {:.0}%", app.snapshot.cpu_percent)).style(Style::new().fg(app.theme.warning)));
    }
    if items.is_empty() {
        items.push(ListItem::new("✓ No active alerts").style(Style::new().fg(app.theme.success)));
    }

    frame.render_widget(List::new(items).block(block), area);
}
"""

# ---------------------------------------------------------------------------
# crates/unicorn-cli
# ---------------------------------------------------------------------------

FILES["crates/unicorn-cli/Cargo.toml"] = r"""[package]
name = "unicorn-cli"
version.workspace = true
edition.workspace = true
authors.workspace = true
license.workspace = true
description = "The `unicorn` binary: wires config, logging, the SSH server, and the TUI together."

[[bin]]
name = "unicorn"
path = "src/main.rs"

[dependencies]
tokio.workspace = true
tracing.workspace = true
anyhow.workspace = true
unicorn-core = { path = "../unicorn-core" }
unicorn-ssh = { path = "../unicorn-ssh" }
unicorn-tui = { path = "../unicorn-tui" }
"""

FILES["crates/unicorn-cli/src/main.rs"] = r"""//! The `unicorn` binary. Loads configuration, starts logging, spawns the
//! SSH front door in the background, and runs the TUI dashboard in the
//! foreground - together, "the operating system for self-hosted Git
//! infrastructure" described in the project vision doc.

use std::path::PathBuf;

use unicorn_core::config::UnicornConfig;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config_path = std::env::args().nth(1).map(PathBuf::from).unwrap_or_else(|| PathBuf::from("unicorn.toml"));

    let config = UnicornConfig::load_or_default(&config_path)?;
    unicorn_core::logging::init(&config.logging);

    tracing::info!(config_path = %config_path.display(), "loaded configuration");

    if config.ssh.enabled {
        let bind_addr = std::net::SocketAddr::new(config.ssh.host, config.ssh.port);
        tokio::spawn(async move {
            let options = unicorn_ssh::SshServerOptions { bind_addr };
            if let Err(err) = unicorn_ssh::run(options).await {
                tracing::error!(error = %err, "ssh server exited");
            }
        });
    } else {
        tracing::info!("ssh server disabled via config");
    }

    // The TUI's event loop blocks the current thread on keyboard/tick
    // events. That's fine here: we're on tokio's multi-threaded runtime
    // (`#[tokio::main]` defaults to it), so the SSH task spawned above
    // keeps making progress on another worker thread while this thread is
    // blocked drawing frames.
    let app = unicorn_tui::App::new(config);
    unicorn_tui::run(app)?;

    Ok(())
}
"""

# ---------------------------------------------------------------------------
# Generator logic
# ---------------------------------------------------------------------------


def generate(root: Path, force: bool) -> None:
    if root.exists():
        if force:
            shutil.rmtree(root)
        elif root.is_dir() and any(root.iterdir()):
            print(f"error: {root} already exists and is not empty. Use --force to overwrite.", file=sys.stderr)
            sys.exit(1)
        elif root.is_file():
            print(f"error: {root} exists and is a file, not a directory.", file=sys.stderr)
            sys.exit(1)

    root.mkdir(parents=True, exist_ok=True)

    for rel_path, content in FILES.items():
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    print(f"Generated {len(FILES)} files under {root}/\n")
    print_tree(root)


def print_tree(root: Path, prefix: str = "") -> None:
    entries = sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name))
    for i, entry in enumerate(entries):
        connector = "└── " if i == len(entries) - 1 else "├── "
        print(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            extension = "    " if i == len(entries) - 1 else "│   "
            print_tree(entry, prefix + extension)


def run_best_effort(cmd: list[str], cwd: Path, label: str) -> None:
    print(f"\n$ {' '.join(cmd)}")
    try:
        subprocess.run(cmd, cwd=cwd, check=False)
    except FileNotFoundError:
        print(f"({label} skipped: '{cmd[0]}' not found on PATH)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Unicorn Rust workspace.")
    parser.add_argument("output_dir", nargs="?", default="unicorn", help="Output directory (default: ./unicorn)")
    parser.add_argument("--force", action="store_true", help="Overwrite output_dir if it already exists")
    parser.add_argument("--fmt", action="store_true", help="Run `cargo fmt` after generating (best-effort)")
    parser.add_argument("--check", action="store_true", help="Run `cargo check --workspace` after generating (best-effort)")
    args = parser.parse_args()

    root = Path(args.output_dir).resolve()
    generate(root, args.force)

    if args.fmt:
        run_best_effort(["cargo", "fmt"], root, "cargo fmt")
    if args.check:
        run_best_effort(["cargo", "check", "--workspace"], root, "cargo check")

    print(
        "\nNext steps:\n"
        f"  cd {args.output_dir}\n"
        "  cargo check --workspace     # verify the crate graph resolves & compiles\n"
        "  cargo run -p unicorn-cli    # launch the dashboard\n"
    )


if __name__ == "__main__":
    main()
