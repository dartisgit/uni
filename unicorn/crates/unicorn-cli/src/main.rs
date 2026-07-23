//! The `unicorn` binary. Loads configuration, starts logging, spawns the
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
