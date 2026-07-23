# Architecture & Roadmap

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
