//! Opening a single repository and summarizing it for display.

use std::path::{Path, PathBuf};

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

            match commit.parent_ids().next() {
                Some(parent_id) => current_id = parent_id.detach(),
                None => break,
            }
        }
    }

    Ok(RepositorySummary { path: path.to_path_buf(), default_branch, branch_count, recent_commits })
}
