use std::path::PathBuf;

use thiserror::Error;

pub type Result<T> = std::result::Result<T, GitError>;

#[derive(Debug, Error)]
pub enum GitError {
    #[error("failed to open repository at {path}: {source}")]
    Open { path: PathBuf, source: Box<dyn std::error::Error + Send + Sync> },

    #[error("i/o error while scanning {path}: {source}")]
    Scan { path: PathBuf, source: std::io::Error },
}
