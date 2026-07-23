//! The `unicorn` binary. Loads configuration, starts logging, connects to
//! Postgres, spawns the SSH front door in the background, and runs the
//! TUI dashboard in the foreground - together, "the operating system for
//! self-hosted Git infrastructure" described in the project vision doc.

use std::path::PathBuf;
use std::sync::Arc;

use unicorn_core::config::UnicornConfig;
use unicorn_ssh::InMemoryKeyStore;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let config_path = std::env::args().nth(1).map(PathBuf::from).unwrap_or_else(|| PathBuf::from("unicorn.toml"));

    let config = UnicornConfig::load_or_default(&config_path)?;
    unicorn_core::logging::init(&config.logging);

    tracing::info!(config_path = %config_path.display(), "loaded configuration");

    if config.ssh.enabled {
        let bind_addr = std::net::SocketAddr::new(config.ssh.host, config.ssh.port);

        // Postgres is optional at this stage: if DATABASE_URL isn't set
        // (or the connection fails), the SSH server falls back to an
        // empty in-memory key store rather than failing to start, so the
        // TUI/dashboard side of Unicorn stays usable without a database
        // while unicorn-db is still being wired up end-to-end. Once
        // `unicorn-db` is the default path, this should become a hard
        // requirement instead of a soft fallback. Only attempted when SSH
        // is actually enabled, so a disabled SSH server never opens a
        // Postgres connection pool it won't use.
        let key_store: Arc<dyn unicorn_ssh::KeyStore> = match std::env::var("DATABASE_URL") {
            Ok(database_url) => match unicorn_db::connect(&database_url, 10).await {
                Ok(pool) => {
                    tracing::info!("using Postgres-backed SSH key store");
                    Arc::new(unicorn_db::PostgresKeyStore::new(pool))
                }
                Err(err) => {
                    tracing::error!(error = %err, "failed to connect to Postgres, falling back to empty in-memory key store");
                    Arc::new(InMemoryKeyStore::new())
                }
            },
            Err(_) => {
                tracing::warn!("DATABASE_URL not set, using empty in-memory key store (no SSH key will authenticate)");
                Arc::new(InMemoryKeyStore::new())
            }
        };

        tokio::spawn(async move {
            let options = unicorn_ssh::SshServerOptions { bind_addr, key_store };
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
