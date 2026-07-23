//! Postgres persistence for Unicorn.
//!
//! This crate owns the connection pool, schema migrations, and every
//! query function that touches the database. `unicorn-core`'s domain
//! models (`User`, `Repository`, `SshKey`, ...) stay plain data structs
//! with no database awareness of their own - this crate is the only place
//! that knows SQL exists, matching the same boundary pattern already used
//! for `unicorn-git` (knows gix, not the database) and `unicorn-ssh`
//! (knows russh, not the database).
//!
//! # Connecting
//!
//! [`connect`] takes the database URL explicitly rather than reading
//! `DATABASE_URL` itself - callers (`unicorn-cli`'s `main.rs`) decide
//! where that value comes from. A local Postgres won't run inside Termux
//! directly; point this at a Postgres reachable over the network (a VPS,
//! a Docker host, etc.) during development on-device.

mod error;
mod ssh_keys;

pub use error::{DbError, Result};
pub use ssh_keys::PostgresKeyStore;

use sqlx::postgres::PgPoolOptions;
use sqlx::PgPool;

/// Embeds every `.sql` file under `migrations/` into the compiled binary,
/// so `unicorn-cli` doesn't need a `migrations/` folder alongside it at
/// runtime - the migrations travel with the binary itself.
static MIGRATOR: sqlx::migrate::Migrator = sqlx::migrate!("./migrations");

/// Connect to Postgres and run any pending migrations before returning
/// the pool. Call this once at startup; the returned [`PgPool`] is cheap
/// to clone and safe to share across every task (SSH connections, the
/// TUI, a future HTTP server) via `Arc` or by cloning directly, since
/// `PgPool` is itself a handle around a shared connection pool.
///
/// `max_connections` should stay modest for a single-instance deployment
/// - Postgres's own default `max_connections` is commonly 100, and this
/// process is not the only thing that may need a connection slot.
pub async fn connect(database_url: &str, max_connections: u32) -> Result<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(max_connections)
        .connect(database_url)
        .await
        .map_err(DbError::Connect)?;

    MIGRATOR.run(&pool).await.map_err(DbError::Migrate)?;

    tracing::info!(max_connections, "connected to Postgres and applied migrations");

    Ok(pool)
}
