use std::path::PathBuf;

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
