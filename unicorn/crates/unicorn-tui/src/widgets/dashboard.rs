//! The Dashboard tab: the first thing an operator sees, per the vision
//! doc's "beautiful dashboard, not a wall of text" goal.

use ratatui::layout::{Constraint, Direction, Layout, Rect};
use ratatui::style::Style;
use ratatui::widgets::{BarChart, Gauge, List, ListItem, Paragraph, Sparkline, Wrap};
use ratatui::Frame;

use crate::app::App;
use crate::widgets::primitives::{human_bytes, panel};

pub fn render(frame: &mut Frame, area: Rect, app: &App) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Length(9), Constraint::Length(9), Constraint::Min(6)])
        .split(area);

    render_resource_row(frame, rows[0], app);
    render_activity_row(frame, rows[1], app);
    render_lists_row(frame, rows[2], app);
}

fn render_resource_row(frame: &mut Frame, area: Rect, app: &App) {
    let cols = Layout::default().direction(Direction::Horizontal).constraints([Constraint::Ratio(1, 3); 3]).split(area);

    render_cpu(frame, cols[0], app);
    render_memory(frame, cols[1], app);
    render_disk(frame, cols[2], app);
}

fn render_cpu(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" CPU Usage ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let parts = Layout::default().direction(Direction::Vertical).constraints([Constraint::Length(3), Constraint::Min(0)]).split(inner);

    let gauge = Gauge::default()
        .gauge_style(Style::new().fg(app.theme.brand).bg(app.theme.surface))
        .percent(app.snapshot.cpu_percent.round().clamp(0.0, 100.0) as u16);
    frame.render_widget(gauge, parts[0]);

    let sparkline = Sparkline::default().data(&app.history.cpu).max(100).style(Style::new().fg(app.theme.brand));
    frame.render_widget(sparkline, parts[1]);
}

fn render_memory(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Memory ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let label = format!("{} / {}", human_bytes(app.snapshot.memory_used_bytes), human_bytes(app.snapshot.memory_total_bytes));

    let gauge = Gauge::default()
        .gauge_style(Style::new().fg(app.theme.info).bg(app.theme.surface))
        .label(label)
        .percent(app.snapshot.memory_percent().round().clamp(0.0, 100.0) as u16);
    frame.render_widget(gauge, inner);
}

fn render_disk(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Disk Usage ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let Some(primary) = app.snapshot.disks.first() else {
        frame.render_widget(Paragraph::new("No disks detected").style(Style::new().fg(app.theme.text_muted)), inner);
        return;
    };

    let label = format!("{}  {} / {}", primary.mount_point, human_bytes(primary.used_bytes()), human_bytes(primary.total_bytes));

    let gauge = Gauge::default()
        .gauge_style(Style::new().fg(app.theme.warning).bg(app.theme.surface))
        .label(label)
        .percent(primary.used_percent().round().clamp(0.0, 100.0) as u16);
    frame.render_widget(gauge, inner);
}

fn render_activity_row(frame: &mut Frame, area: Rect, app: &App) {
    let cols = Layout::default().direction(Direction::Horizontal).constraints([Constraint::Percentage(50), Constraint::Percentage(50)]).split(area);

    render_network(frame, cols[0], app);
    render_repo_activity(frame, cols[1], app);
}

fn render_network(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Network ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    let sparkline = Sparkline::default().data(&app.history.network_rx).style(Style::new().fg(app.theme.info));
    frame.render_widget(sparkline, inner);
}

fn render_repo_activity(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Repository Activity ", &app.theme);
    let inner = block.inner(area);
    frame.render_widget(block, area);

    if app.repositories.is_empty() {
        frame.render_widget(
            Paragraph::new(format!(
                "No repositories found under {}.\nPoint `storage.repositories_dir` at a directory \
                 of git repos, or clone one in to see it here.",
                app.config.storage.repositories_dir.display()
            ))
            .style(Style::new().fg(app.theme.text_muted))
            .wrap(Wrap { trim: true }),
            inner,
        );
        return;
    }

    let data: Vec<(&str, u64)> = app.repositories.iter().take(7).map(|repo| (repo.slug.as_str(), 1u64)).collect();

    let chart = BarChart::default()
        .bar_width(3)
        .bar_gap(1)
        .bar_style(Style::new().fg(app.theme.brand))
        .value_style(Style::new().fg(app.theme.background).bg(app.theme.brand))
        .data(&data);
    frame.render_widget(chart, inner);
}

fn render_lists_row(frame: &mut Frame, area: Rect, app: &App) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(34), Constraint::Percentage(33), Constraint::Percentage(33)])
        .split(area);

    render_top_repositories(frame, cols[0], app);
    render_recent_commits(frame, cols[1], app);
    render_alerts(frame, cols[2], app);
}

fn render_top_repositories(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Repositories ", &app.theme);

    let items: Vec<ListItem> = if app.repositories.is_empty() {
        vec![ListItem::new("(none discovered yet)").style(Style::new().fg(app.theme.text_muted))]
    } else {
        app.repositories
            .iter()
            .map(|repo| {
                let kind = if repo.is_bare { "bare" } else { "worktree" };
                ListItem::new(format!("📁 {}  ({kind})", repo.slug)).style(Style::new().fg(app.theme.text))
            })
            .collect()
    };

    frame.render_widget(List::new(items).block(block), area);
}

fn render_recent_commits(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" Recent Commits ", &app.theme);
    let items = vec![ListItem::new(
        "Select a repository on the Repositories tab to see its commit \
         log here.\n(Wire this up to `unicorn_git::open(..).recent_commits` \
         once that tab exists.)",
    )
    .style(Style::new().fg(app.theme.text_muted))];
    frame.render_widget(List::new(items).block(block), area);
}

fn render_alerts(frame: &mut Frame, area: Rect, app: &App) {
    let block = panel(" System Alerts ", &app.theme);
    let mut items = Vec::new();

    for disk in &app.snapshot.disks {
        if disk.used_percent() > 90.0 {
            items.push(
                ListItem::new(format!("⚠ Disk {} is {:.0}% full", disk.mount_point, disk.used_percent()))
                    .style(Style::new().fg(app.theme.warning)),
            );
        }
    }
    if app.snapshot.cpu_percent > 90.0 {
        items.push(ListItem::new(format!("⚠ CPU usage is {:.0}%", app.snapshot.cpu_percent)).style(Style::new().fg(app.theme.warning)));
    }
    if items.is_empty() {
        items.push(ListItem::new("✓ No active alerts").style(Style::new().fg(app.theme.success)));
    }

    frame.render_widget(List::new(items).block(block), area);
}
