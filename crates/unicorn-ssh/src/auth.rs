//! Public-key lookup for SSH authentication.
//!
//! This module intentionally has zero dependency on `unicorn-core` - it
//! defines its own minimal [`AuthorizedKey`] shape and a [`KeyStore`]
//! trait, so `unicorn-ssh` stays compilable and testable in isolation.
//! `unicorn-cli` is responsible for bridging real `unicorn_core::models::
//! SshKey` records into an [`InMemoryKeyStore`] (or a future
//! database-backed implementation) at startup.

use std::collections::HashMap;
use std::sync::RwLock;

use async_trait::async_trait;
use thiserror::Error;

/// A public key this server will accept, keyed by its SHA-256 fingerprint
/// (the `SHA256:...` format `ssh-keygen -l` prints - the same format
/// [`fingerprint_of`] produces from an incoming connection).
#[derive(Debug, Clone)]
pub struct AuthorizedKey {
    /// `SHA256:<base64>` - see [`fingerprint_of`].
    pub fingerprint: String,
    /// Username / account this key authenticates as.
    pub owner_username: String,
}

#[derive(Debug, Error)]
pub enum KeyStoreError {
    #[error("key store backend error: {0}")]
    Backend(String),
}

/// Abstraction over "where do authorized public keys live". The SSH
/// handler only ever calls [`KeyStore::find_key`] - it never needs to know
/// whether keys come from memory, a config file, or (eventually) a real
/// database.
#[async_trait]
pub trait KeyStore: Send + Sync {
    /// Look up a key by its SHA-256 fingerprint. Returns `Ok(None)` for
    /// "no such key" (a normal, expected outcome - most connection
    /// attempts from the internet will not match anything) and `Err` only
    /// for an actual backend failure (e.g. a database being unreachable).
    /// Callers must treat both `Ok(None)` and `Err` as "do not authenticate
    /// this connection" - see `ConnectionHandler::auth_publickey` in
    /// `lib.rs`, which fails closed on either.
    async fn find_key(&self, fingerprint: &str) -> std::result::Result<Option<AuthorizedKey>, KeyStoreError>;
}

/// A simple thread-safe, in-memory [`KeyStore`], suitable for local
/// development and as the default until a persistent backend exists.
/// Safe to share across every connection via `Arc<dyn KeyStore>`.
#[derive(Default)]
pub struct InMemoryKeyStore {
    keys: RwLock<HashMap<String, AuthorizedKey>>,
}

impl InMemoryKeyStore {
    pub fn new() -> Self {
        Self::default()
    }

    /// Build a store pre-populated with `keys`, e.g. from
    /// `unicorn_core::models::SshKey` records loaded at startup.
    pub fn from_keys(keys: impl IntoIterator<Item = AuthorizedKey>) -> Self {
        let store = Self::new();
        for key in keys {
            store.add_key(key);
        }
        store
    }

    /// Add or replace a key. Safe to call at runtime (e.g. from a future
    /// "add SSH key" admin action) since it only takes a write lock for
    /// the duration of the insert.
    pub fn add_key(&self, key: AuthorizedKey) {
        if let Ok(mut keys) = self.keys.write() {
            keys.insert(key.fingerprint.clone(), key);
        }
    }

    /// Remove a key by fingerprint, e.g. when a user revokes it.
    pub fn remove_key(&self, fingerprint: &str) {
        if let Ok(mut keys) = self.keys.write() {
            keys.remove(fingerprint);
        }
    }
}

#[async_trait]
impl KeyStore for InMemoryKeyStore {
    async fn find_key(&self, fingerprint: &str) -> std::result::Result<Option<AuthorizedKey>, KeyStoreError> {
        let keys = self
            .keys
            .read()
            .map_err(|_| KeyStoreError::Backend("key store lock was poisoned".to_string()))?;
        Ok(keys.get(fingerprint).cloned())
    }
}

/// Compute the SHA-256 fingerprint of a public key in the standard
/// `SHA256:<base64>` form (the same string `ssh-keygen -l` prints, and
/// what a person would paste in when registering a key with Unicorn).
///
/// `HashAlg::default()` is SHA-256 as of `ssh-key` (the crate `russh::keys`
/// re-exports), matching `ssh-keygen`'s own default since OpenSSH 6.8 -
/// verified against current docs.rs output rather than assumed, since this
/// is exactly the kind of detail that's easy to get subtly wrong (older
/// tooling defaults to MD5, which uses a different, colon-separated
/// format and would silently never match anything stored here).
pub fn fingerprint_of(public_key: &russh::keys::PublicKey) -> String {
    public_key.fingerprint(Default::default()).to_string()
}
