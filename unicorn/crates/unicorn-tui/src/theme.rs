//! The Unicorn color palette: dark background, magenta/purple brand accent
//! (matching the 🦄 in every corner of the product), and muted borders for
//! the "modern terminal" look called for in the vision doc.

use ratatui::style::Color;

#[derive(Debug, Clone, Copy)]
pub struct Theme {
    pub background: Color,
    pub surface: Color,
    pub border: Color,
    pub brand: Color,
    pub text: Color,
    pub text_muted: Color,
    pub success: Color,
    pub warning: Color,
    pub danger: Color,
    pub info: Color,
}

impl Default for Theme {
    fn default() -> Self {
        Self {
            background: Color::Rgb(10, 10, 18),
            surface: Color::Rgb(18, 18, 30),
            border: Color::Rgb(60, 60, 90),
            brand: Color::Rgb(190, 120, 255),
            text: Color::Rgb(230, 230, 240),
            text_muted: Color::Rgb(140, 140, 160),
            success: Color::Rgb(80, 220, 140),
            warning: Color::Rgb(240, 200, 90),
            danger: Color::Rgb(240, 100, 110),
            info: Color::Rgb(90, 180, 240),
        }
    }
}
