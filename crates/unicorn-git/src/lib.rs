//! Git engine for Unicorn, built directly on [`gix`] (gitoxide) - no
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
