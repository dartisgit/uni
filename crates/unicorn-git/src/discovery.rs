//! Walk a directory tree looking for git repositories, the way Unicorn's
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
