//! Serde + TOML backed configuration for the whole Unicorn platform.
//!
//! The file on disk mirrors this struct one-to-one, so `unicorn.toml`
//! doubles as living documentation. Every field has a sensible default so a
//! brand new deployment can start with zero configuration and grow into a
//! full one.

use std::net::{IpAddr, Ipv4Addr};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::error::{Result, UnicornError};

/// Root configuration object, deserialized from `unicorn.toml`.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct UnicornConfig {
    pub server: ServerConfig,
    pub ssh: SshConfig,
    pub storage: StorageConfig,
    pub ui: UiConfig,
    pub logging: LoggingConfig,
}

impl Default for UnicornConfig {
    fn default() -> Self {
        Self {
            server: ServerConfig::default(),
            ssh: SshConfig::default(),
            storage: StorageConfig::default(),
            ui: UiConfig::default(),
            logging: LoggingConfig::default(),
        }
    }
}

impl UnicornConfig {
    /// Load configuration from a TOML file, falling back to defaults for
    /// any field that is missing (thanks to `#[serde(default)]`).
    pub fn load(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        let raw = std::fs::read_to_string(path).map_err(|source| UnicornError::Config {
            path: path.to_path_buf(),
            source: source.into(),
        })?;
        toml::from_str(&raw).map_err(|source| UnicornError::Config {
            path: path.to_path_buf(),
            source: source.into(),
        })
    }

    /// Load configuration if `path` exists, otherwise return the defaults.
    /// This is what `unicorn-cli` uses on startup so a missing config file
    /// is never a hard failure.
    pub fn load_or_default(path: impl AsRef<Path>) -> Result<Self> {
        let path = path.as_ref();
        if path.exists() {
            Self::load(path)
        } else {
            Ok(Self::default())
        }
    }

    /// Serialize the current configuration back to a pretty TOML string,
    /// useful for a future `unicorn config init` style command.
    pub fn to_toml_string(&self) -> Result<String> {
        toml::to_string_pretty(self).map_err(|source| UnicornError::Config {
            path: PathBuf::from("<in-memory>"),
            source: source.into(),
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct ServerConfig {
    pub host: IpAddr,
    pub http_port: u16,
    pub data_dir: PathBuf,
}

impl Default for ServerConfig {
    fn default() -> Self {
        Self {
            host: IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0)),
            http_port: 3000,
            data_dir: PathBuf::from("./data"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct SshConfig {
    pub enabled: bool,
    pub host: IpAddr,
    pub port: u16,
    pub host_key_path: PathBuf,
}

impl Default for SshConfig {
    fn default() -> Self {
        Self {
            enabled: true,
            host: IpAddr::V4(Ipv4Addr::new(0, 0, 0, 0)),
            port: 2222,
            host_key_path: PathBuf::from("./data/ssh/host_ed25519"),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct StorageConfig {
    pub repositories_dir: PathBuf,
}

impl Default for StorageConfig {
    fn default() -> Self {
        Self { repositories_dir: PathBuf::from("./data/repositories") }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct UiConfig {
    pub refresh_interval_ms: u64,
    pub theme: String,
}

impl Default for UiConfig {
    fn default() -> Self {
        Self { refresh_interval_ms: 1000, theme: "unicorn-dark".to_string() }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct LoggingConfig {
    pub level: String,
    pub file: Option<PathBuf>,
}

impl Default for LoggingConfig {
    fn default() -> Self {
        Self { level: "info".to_string(), file: Some(PathBuf::from("./data/logs/unicorn.log")) }
    }
}
