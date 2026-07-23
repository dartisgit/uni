//! Thin wrapper around `tracing-subscriber` so every binary in the
//! workspace initializes logging the same way.

use crate::config::LoggingConfig;

/// Install a global `tracing` subscriber configured from `LoggingConfig`.
///
/// Call this once, near the top of `main`. It honours the `RUST_LOG`
/// environment variable if set, otherwise falls back to `config.level`.
pub fn init(config: &LoggingConfig) {
    let filter = tracing_subscriber::EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| tracing_subscriber::EnvFilter::new(config.level.clone()));

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(false)
        .compact()
        .init();
}
