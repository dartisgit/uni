//! Unicorn's primary interface: a Ratatui dashboard designed so people
//! "forget they're looking at a terminal application" (see the project
//! vision doc). This crate owns the event loop, application state, theme,
//! and every widget on screen; it treats `unicorn-git` and
//! `unicorn-metrics` purely as data sources.

mod app;
mod theme;
mod widgets;

pub use app::{run, App};
pub use theme::Theme;
