//! `unicorn-core` holds the configuration, domain models, error types, and
//! logging bootstrap shared by every other Unicorn crate.
//!
//! Nothing in this crate talks to git, the network, or the terminal - it is
//! pure data plus a handful of small, well tested helpers. That keeps it
//! fast to compile and easy to reuse from `unicorn-cli`, `unicorn-tui`,
//! `unicorn-ssh`, and any future subsystem (webhooks, CI runners, the
//! package registry, ...).

pub mod config;
pub mod error;
pub mod logging;
pub mod models;

pub use config::UnicornConfig;
pub use error::{Result, UnicornError};
