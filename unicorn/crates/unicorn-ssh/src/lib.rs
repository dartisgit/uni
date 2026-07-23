//! Rust-native SSH front door for Unicorn, built on [`russh`] - no
//! `libssh2`, no system `sshd`.
//!
//! # Status
//!
//! Connection handling and public-key authentication are real: incoming
//! keys are fingerprinted (SHA-256, the same format `ssh-keygen -l`
//! prints) and checked against a [`KeyStore`], and unknown/mismatched keys
//! are rejected. What's still scaffold is channel/exec handling - no
//! `git-upload-pack` / `git-receive-pack` dispatch yet, so authenticated
//! sessions currently just echo bytes back (see [`ConnectionHandler::data`]).
//!
//! # A note on key types
//!
//! `russh` re-exports its own internal fork of key-handling types under
//! `russh::keys` (`russh::keys::PrivateKey`, `russh::keys::PublicKey`,
//! `russh::keys::Algorithm`, `russh::keys::HashAlg`). Do NOT add the
//! standalone `russh-keys` crate as a separate dependency here - it defines
//! structurally identical but *distinct* types with the same names, and
//! mixing the two produces confusing "expected `russh::keys::X`, found
//! `russh_keys::X`" errors that look like a version mismatch but are
//! actually a duplicate-crate problem. Always import from `russh::keys::`,
//! never from a top-level `russh_keys::`.
//!
//! If `cargo check -p unicorn-ssh` fails, compare against whatever `russh`
//! version Cargo actually resolved (`cargo tree -p russh`) - this crate's
//! `auth.rs` in particular calls `PublicKey::fingerprint`, which has moved
//! around across `russh`/`ssh-key` releases historically.

mod auth;

use std::net::SocketAddr;
use std::sync::Arc;

use russh::server::{Auth, Handler, Msg, Server as _, Session};
use russh::{Channel, ChannelId};
use thiserror::Error;

pub use auth::{AuthorizedKey, InMemoryKeyStore, KeyStore, KeyStoreError};

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
    /// Source of truth for which public keys are allowed to authenticate.
    /// `unicorn-cli` is responsible for populating this from
    /// `unicorn_core::models::SshKey` records (or, eventually, a real
    /// database) before calling [`run`].
    pub key_store: Arc<dyn KeyStore>,
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
    let host_key = russh::keys::PrivateKey::random(&mut rand::thread_rng(), russh::keys::Algorithm::Ed25519)
        .map_err(|e| SshError::HostKey(e.to_string()))?;

    let config = Arc::new(russh::server::Config { keys: vec![host_key], ..Default::default() });

    tracing::info!(addr = %options.bind_addr, "starting Unicorn SSH server");

    let mut factory = ServerFactory { key_store: options.key_store };
    factory
        .run_on_address(config, options.bind_addr)
        .await
        .map_err(|e| SshError::Server(e.into()))
}

/// Creates a fresh [`Handler`] for every incoming TCP connection. Holds the
/// shared [`KeyStore`] so every connection's handler can look keys up
/// against the same source of truth.
struct ServerFactory {
    key_store: Arc<dyn KeyStore>,
}

impl russh::server::Server for ServerFactory {
    type Handler = ConnectionHandler;

    fn new_client(&mut self, peer_addr: Option<SocketAddr>) -> Self::Handler {
        tracing::debug!(?peer_addr, "accepted ssh connection");
        ConnectionHandler { username: None, key_store: self.key_store.clone() }
    }
}

/// Per-connection handler. One instance is created per client.
struct ConnectionHandler {
    username: Option<String>,
    key_store: Arc<dyn KeyStore>,
}

impl Handler for ConnectionHandler {
    type Error = russh::Error;

    /// Authenticates the client's offered public key by fingerprinting it
    /// (SHA-256, matching `ssh-keygen -l`'s default output) and checking
    /// that fingerprint against [`KeyStore`]. Any lookup error, or simply
    /// not finding the key, rejects the connection - this fails closed by
    /// design, never open.
    ///
    /// Note the explicit `std::result::Result<_, Self::Error>` return type
    /// below (rather than this crate's own `Result<T>` alias): the trait
    /// requires exactly `std::result::Result<_, Self::Error>` with
    /// `Self::Error = russh::Error`, which is distinct from - and would be
    /// shadowed/miscounted against - this crate's local `SshError`-based
    /// alias, producing a "type alias takes 1 generic argument but 2 were
    /// supplied" error if written as `Result<Auth, Self::Error>`.
    async fn auth_publickey(
        &mut self,
        user: &str,
        public_key: &russh::keys::PublicKey,
    ) -> std::result::Result<Auth, Self::Error> {
        let fingerprint = auth::fingerprint_of(public_key);

        match self.key_store.find_key(&fingerprint).await {
            Ok(Some(authorized)) => {
                tracing::info!(
                    user,
                    fingerprint = %fingerprint,
                    owner = %authorized.owner_username,
                    "public key accepted"
                );
                self.username = Some(user.to_string());
                Ok(Auth::Accept)
            }
            Ok(None) => {
                tracing::warn!(user, fingerprint = %fingerprint, "public key rejected: not found in key store");
                Ok(Auth::reject())
            }
            Err(err) => {
                // Fail closed: a broken lookup is treated the same as "key
                // not found", never as an implicit accept.
                tracing::error!(user, fingerprint = %fingerprint, error = %err, "key store lookup failed, rejecting");
                Ok(Auth::reject())
            }
        }
    }

    async fn channel_open_session(
        &mut self,
        channel: Channel<Msg>,
        _session: &mut Session,
    ) -> std::result::Result<bool, Self::Error> {
        tracing::debug!(channel = ?channel.id(), user = ?self.username, "channel opened");
        Ok(true)
    }

    /// TODO: dispatch on the exec command (`git-upload-pack '<repo>'`,
    /// `git-receive-pack '<repo>'`) and stream through `unicorn-git`
    /// instead of echoing input back, which is what this scaffold does for
    /// now so manual testing (`ssh -p 2222 localhost`) has something
    /// visible to look at.
    async fn data(
        &mut self,
        channel: ChannelId,
        data: &[u8],
        session: &mut Session,
    ) -> std::result::Result<(), Self::Error> {
        session.data(channel, data.to_vec().into())?;
        Ok(())
    }
}
