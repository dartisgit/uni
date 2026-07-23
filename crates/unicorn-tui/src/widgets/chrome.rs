//! The parts of the screen that stay the same across every tab: the header
//! banner, the tab bar, the left navigation sidebar, and the bottom status
//! bar. See the vision doc's "User Experience" section for the box-drawing
//! sketch this layout is based on.

use ratatui::layout::{Alignment, Constraint, Direction, Layout, Rect};
use ratatui::style::{Style, Stylize};
use ratatui::text::{Line, Span};
use ratatui::widgets::{Block, Borders, List, ListItem, Paragraph, Tabs, Wrap};
use ratatui::Frame;

use crate::app::{App, TABS};
use crate::widgets::dashboard;
use crate::widgets::primitives::{human_bytes, panel};

pub fn render(frame: &mut Frame, app: &App) {
    let root = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(3), // header
            Constraint::Length(1), // tab bar
            Constraint::Min(0),    // body
            Constraint::Length(1), // status bar
        ])
        .split(frame.area());

    render_header(frame, root[0], app);
    render_tabs(frame, root[1], app);
    render_body(frame, root[2], app);
    render_status_bar(frame, root[3], app);
}

fn render_header(frame: &mut Frame, area: Rect, app: &App) {
    let block = Block::default().borders(Borders::BOTTOM).border_style(Style::new().fg(app.theme.border));
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)])
        .split(inner);

    let title = Line::from(vec![
        Span::styled("🦄 Unicorn  ", Style::new().fg(app.theme.brand).bold()),
        Span::styled("The Rust-native Git Platform", Style::new().fg(app.theme.text_muted)),
    ]);
    frame.render_widget(Paragraph::new(title), cols[0]);

    let status = Line::from(vec![
        Span::styled("● Healthy   ", Style::new().fg(app.theme.success)),
        Span::styled(format!("CPU {:>3.0}%   ", app.snapshot.cpu_percent), Style::new().fg(app.theme.text)),
        Span::styled(
            format!("RAM {} / {}", human_bytes(app.snapshot.memory_used_bytes), human_bytes(app.snapshot.memory_total_bytes)),
            Style::new().fg(app.theme.text),
        ),
    ])
    .alignment(Alignment::Right);
    frame.render_widget(Paragraph::new(status), cols[1]);
}

fn render_tabs(frame: &mut Frame, area: Rect, app: &App) {
    let titles: Vec<Line> = TABS.iter().map(|t| Line::from(*t)).collect();
    let tabs = Tabs::new(titles)
        .select(app.selected_tab)
        .style(Style::new().fg(app.theme.text_muted))
        .highlight_style(Style::new().fg(app.theme.brand).bold())
        .divider(" ");
    frame.render_widget(tabs, area);
}

fn render_body(frame: &mut Frame, area: Rect, app: &App) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Length(22), Constraint::Min(0)])
        .split(area);

    render_nav(frame, cols[0], app);

    match app.selected_tab {
        0 => dashboard::render(frame, cols[1], app),
        _ => render_placeholder(frame, cols[1], app),
    }
}

fn render_nav(frame: &mut Frame, area: Rect, app: &App) {
    let block = Block::default()
        .borders(Borders::RIGHT)
        .border_style(Style::new().fg(app.theme.border))
        .title(" Navigation ")
        .title_style(Style::new().fg(app.theme.text_muted));

    let items: Vec<ListItem> = TABS
        .iter()
        .enumerate()
        .map(|(i, label)| {
            let style = if i == app.selected_tab {
                Style::new().fg(app.theme.brand).bold()
            } else {
                Style::new().fg(app.theme.text_muted)
            };
            ListItem::new(format!("  {label}")).style(style)
        })
        .collect();

    frame.render_widget(List::new(items).block(block), area);
}

fn render_placeholder(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Coming soon ", &app.theme);
    let text = Paragraph::new(format!(
        "The \"{}\" view isn't built yet - this scaffold currently only wires up the Dashboard tab. \
         Add a new module under `unicorn-tui/src/widgets/` and route it from `chrome::render_body`.",
        TABS[app.selected_tab]
    ))
    .style(Style::new().fg(app.theme.text_muted))
    .block(block)
    .wrap(Wrap { trim: true });
    frame.render_widget(text, area);
}

fn render_status_bar(frame: &mut Frame, area: Rect, app: &App) {
    let line = Line::from(vec![
        Span::styled(" 🦄 Unicorn 0.1.0  ", Style::new().fg(app.theme.brand)),
        Span::styled("| ", Style::new().fg(app.theme.border)),
        Span::styled(format!("Repositories {}  ", app.repositories.len()), Style::new().fg(app.theme.text_muted)),
        Span::styled("| ", Style::new().fg(app.theme.border)),
        Span::styled(
            "q: quit   tab/←→: switch view   j/k: navigate   r: rescan repos",
            Style::new().fg(app.theme.text_muted),
        ),
    ]);
    frame.render_widget(Paragraph::new(line), area);
}
