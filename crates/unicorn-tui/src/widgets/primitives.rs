//! Small rendering helpers shared by every widget module.

use ratatui::style::Style;
use ratatui::widgets::Block;

use crate::theme::Theme;

/// A bordered, titled panel styled consistently with the rest of the
/// dashboard. `Block::bordered()` is Ratatui's shorthand for
/// `Block::default().borders(Borders::ALL)`.
pub fn panel<'a>(title: &'a str, theme: &Theme) -> Block<'a> {
    Block::bordered()
        .border_style(Style::new().fg(theme.border))
        .title(title)
        .title_style(Style::new().fg(theme.text))
        .style(Style::new().bg(theme.surface))
}

/// Human-readable byte sizes (`1.2 GiB`, `340 MiB`, ...), matching the
/// dashboard mockup's units.
pub fn human_bytes(bytes: u64) -> String {
    const UNITS: [&str; 5] = ["B", "KiB", "MiB", "GiB", "TiB"];
    let mut value = bytes as f64;
    let mut unit = 0;
    while value >= 1024.0 && unit < UNITS.len() - 1 {
        value /= 1024.0;
        unit += 1;
    }
    if unit == 0 {
        format!("{value:.0} {}", UNITS[unit])
    } else {
        format!("{value:.1} {}", UNITS[unit])
    }
}
