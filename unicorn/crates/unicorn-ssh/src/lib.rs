//! Rust-native SSH front door for Unicorn, built on [`russh`] - no
//! `libssh2`, no system `sshd`.
//!
//! # Status: scaffold, not finished
//!
//! This wires up the pieces `russh` needs (a [`russh::server::Config`], a
//! [`russh::server::Handler`], and a [`russh::server::Server`] factory) and
//! accepts connections, but authentication currently accepts every public
//! key and no channel/exec logic is implemented yet. That is intentional:
//! per Unicorn's own development philosophy ("Generate Workspace -> cargo
//! check -> improve"), this module is meant to be filled in incrementally -
//! wire real public-key lookup against `unicorn_core::models::SshKey`
//! first, then `git-upload-pack` / `git-receive-pack` channel handling.
//!
//! `russh`'s key-handling types (`PrivateKey`, `PublicKey`, `Algorithm`)
//! have moved around more than the rest of this crate's dependencies
//! across recent releases. If `cargo check -p unicorn-ssh` fails, this
//! file - specifically the `Config` construction in [`run`] and the
//! `auth_publickey` signature below - is the first place to look; compare
//! against whatever `russh`/`russh-keys` version Cargo actually resolved
//! (`cargo tree -p russh -p russh-keys`).

use std::net::SocketAddr;
use std::sync::Arc;

use russh::server::{Auth, Handler, Msg, Server as _, Session};
use russh::{Channel, ChannelId};
use thiserror::Error;

pub type Result<T> = std::result::Result<T, SshError>;

#[derive(Debug, Error)]
pub enum SshError {
    #[error("failed to generate host key: {0}")]
    HostKey(String),

    #[error("ssh server error: {0}")]
    Server(#[from] russh::Error),
}

/// Runtime options for the SSH front door, kept separate from
/// `unicorn_core::config::SshConfig` so this crate has no compile-time
/// dependency on `unicorn-core`'s exact shape.
pub struct SshServerOptions {
    pub bind_addr: SocketAddr,
}

/// Start the SSH server and run until the process is shut down.
///
/// Spawn this in its own `tokio::spawn`ed task from `unicorn-cli`,
/// alongside the TUI and any future HTTP server.
pub async fn run(options: SshServerOptions) -> Result<()> {
    // A fresh, in-memory host key every start-up is fine for local
    // development but NOT for anything long-lived: real deployments should
    // load a persisted key from `SshConfig::host_key_path` (generating and
    // saving one on first run) so client-side `known_hosts` entries stay
    // valid across restarts.
    let host_key = russh_keys::PrivateKey::random(&mut rand::thread_rng(), russh_keys::Algorithm::Ed25519)
        .map_err(|e| SshError::HostKey(e.to_string()))?;

    let config = Arc::new(russh::server::Config { keys: vec![host_key], ..Default::default() });

    tracing::info!(addr = %options.bind_addr, "starting Unicorn SSH server");

    let mut factory = ServerFactory;
    factory.run_on_address(config, options.bind_addr).await.map_err(SshError::Server)
}

/// Creates a fresh [`Handler`] for every incoming TCP connection.
struct ServerFactory;

impl russh::server::Server for ServerFactory {
    type Handler = ConnectionHandler;

    fn new_client(&mut self, peer_addr: Option<SocketAddr>) -> Self::Handler {
        tracing::debug!(?peer_addr, "accepted ssh connection");
        ConnectionHandler::default()
    }
}

/// Per-connection handler. One instance is created per client.
#[derive(Default)]
struct ConnectionHandler {
    username: Option<String>,
}

impl Handler for ConnectionHandler {
    type Error = russh::Error;

    /// TODO(security): replace with a real lookup against
    /// `unicorn_core::models::SshKey` by fingerprint before this server is
    /// exposed to anything but a trusted local network. Accepting every
    /// key, as this scaffold does, is only appropriate for local testing.
    async fn auth_publickey(&mut self, user: &str, _public_key: &russh_keys::PublicKey) -> Result<Auth, Self::Error> {
        self.username = Some(user.to_string());
        Ok(Auth::Accept)
    }

    async fn channel_open_session(&mut self, channel: Channel<Msg>, _session: &mut Session) -> Result<bool, Self::Error> {
        tracing::debug!(channel = ?channel.id(), user = ?self.username, "channel opened");
        Ok(true)
    }

    /// TODO: dispatch on the exec command (`git-upload-pack '<repo>'`,
    /// `git-receive-pack '<repo>'`) and stream through `unicorn-git`
    /// instead of echoing input back, which is what this scaffold does for
    /// now so manual testing (`ssh -p 2222 localhost`) has something
    /// visible to look at.
    async fn data(&mut self, channel: ChannelId, data: &[u8], session: &mut Session) -> Result<(), Self::Error> {
        session.data(channel, data.to_vec().into())?;
        Ok(())
    }
}
