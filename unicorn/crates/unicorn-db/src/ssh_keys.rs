//! Postgres-backed implementation of `unicorn_ssh::KeyStore`.
//!
//! This is the intended replacement for `unicorn_ssh::InMemoryKeyStore`
//! once real accounts exist: `unicorn-cli` builds a [`PostgresKeyStore`]
//! from the same connection pool as everything else and hands it to
//! `unicorn_ssh::SshServerOptions` as `Arc<dyn KeyStore>` - no change
//! needed in `unicorn-ssh` itself, since it only ever depends on the
//! `KeyStore` trait, never on a concrete backend.
//!
//! # Build note: sqlx's compile-time query checking
//!
//! The `sqlx::query!` macro below checks its SQL against a real database
//! schema at `cargo build` time - either a live Postgres reachable via
//! `DATABASE_URL`, or a checked-in offline cache. Until one of those
//! exists, this crate will not compile. Once Postgres is up and
//! migrations have been applied (`unicorn_db::connect` does this), run:
//!
//!     cargo sqlx prepare --workspace
//!
//! from the workspace root (`cargo install sqlx-cli` first if needed).
//! That generates a `.sqlx/` directory to check into the repo, so CI and
//! other machines can build without needing live database access.

use async_trait::async_trait;
use sqlx::PgPool;
use unicorn_ssh::{AuthorizedKey, KeyStore, KeyStoreError};

pub struct PostgresKeyStore {
    pool: PgPool,
}

impl PostgresKeyStore {
    pub fn new(pool: PgPool) -> Self {
        Self { pool }
    }
}

#[async_trait]
impl KeyStore for PostgresKeyStore {
    async fn find_key(&self, fingerprint: &str) -> std::result::Result<Option<AuthorizedKey>, KeyStoreError> {
        // Joins to users so `owner_username` (what unicorn-ssh logs and
        // what `ConnectionHandler` treats as the authenticated identity)
        // comes back as the actual username, not a bare numeric id.
        let row = sqlx::query!(
            r#"
            SELECT ssh_keys.fingerprint, users.username AS owner_username
            FROM ssh_keys
            JOIN users ON users.id = ssh_keys.owner_id
            WHERE ssh_keys.fingerprint = $1
            "#,
            fingerprint
        )
        .fetch_optional(&self.pool)
        .await
        .map_err(|e| KeyStoreError::Backend(e.to_string()))?;

        Ok(row.map(|r| AuthorizedKey { fingerprint: r.fingerprint, owner_username: r.owner_username }))
    }
}
