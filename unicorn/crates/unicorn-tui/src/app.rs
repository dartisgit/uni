//! Application state and the top-level event loop.

use std::io;
use std::time::{Duration, Instant};

use crossterm::event::{self, Event, KeyCode, KeyEventKind};

use unicorn_core::config::UnicornConfig;
use unicorn_git::{discover_repositories, DiscoveredRepository};
use unicorn_metrics::{MetricsCollector, SystemSnapshot};

use crate::theme::Theme;
use crate::widgets::chrome;

pub const TABS: [&str; 8] =
    ["Dashboard", "Repositories", "Users", "Organizations", "SSH Keys", "Packages", "Metrics", "Logs"];

/// A rolling window of recent samples, used to feed the CPU/network
/// sparklines. Capacity matches how many columns of history are worth
/// keeping on screen at once.
#[derive(Debug, Clone, Default)]
pub struct History {
    pub cpu: Vec<u64>,
    pub network_rx: Vec<u64>,
}

impl History {
    const CAPACITY: usize = 120;

    fn push(&mut self, snapshot: &SystemSnapshot) {
        self.cpu.push(snapshot.cpu_percent.round() as u64);
        self.network_rx.push(snapshot.network_rx_bytes_per_tick);
        if self.cpu.len() > Self::CAPACITY {
            self.cpu.remove(0);
        }
        if self.network_rx.len() > Self::CAPACITY {
            self.network_rx.remove(0);
        }
    }
}

pub struct App {
    pub theme: Theme,
    pub config: UnicornConfig,
    pub selected_tab: usize,
    pub nav_selected: usize,
    pub metrics: MetricsCollector,
    pub snapshot: SystemSnapshot,
    pub history: History,
    pub repositories: Vec<DiscoveredRepository>,
    pub should_quit: bool,
}

impl App {
    pub fn new(config: UnicornConfig) -> Self {
        let mut metrics = MetricsCollector::new();
        let snapshot = metrics.refresh();
        let repositories = discover_repositories(&config.storage.repositories_dir, 3).unwrap_or_default();

        let mut history = History::default();
        history.push(&snapshot);

        Self {
            theme: Theme::default(),
            config,
            selected_tab: 0,
            nav_selected: 0,
            metrics,
            snapshot,
            history,
            repositories,
            should_quit: false,
        }
    }

    fn on_tick(&mut self) {
        self.snapshot = self.metrics.refresh();
        self.history.push(&self.snapshot);
    }

    fn on_key(&mut self, code: KeyCode) {
        match code {
            KeyCode::Char('q') | KeyCode::Esc => self.should_quit = true,
            KeyCode::Right | KeyCode::Char('l') | KeyCode::Tab => {
                self.selected_tab = (self.selected_tab + 1) % TABS.len();
            }
            KeyCode::Left | KeyCode::Char('h') | KeyCode::BackTab => {
                self.selected_tab = (self.selected_tab + TABS.len() - 1) % TABS.len();
            }
            KeyCode::Down | KeyCode::Char('j') => {
                self.nav_selected = (self.nav_selected + 1) % TABS.len();
            }
            KeyCode::Up | KeyCode::Char('k') => {
                self.nav_selected = (self.nav_selected + TABS.len() - 1) % TABS.len();
            }
            KeyCode::Char('r') => {
                self.repositories = discover_repositories(&self.config.storage.repositories_dir, 3).unwrap_or_default();
            }
            _ => {}
        }
    }
}

/// Run the dashboard until the user quits. This is a blocking call - see
/// `unicorn-cli`'s `main.rs` for how it's combined with the async SSH
/// server on tokio's multi-threaded runtime.
pub fn run(mut app: App) -> io::Result<()> {
    let mut terminal = ratatui::init();
    let tick_rate = Duration::from_millis(app.config.ui.refresh_interval_ms.max(200));
    let mut last_tick = Instant::now();

    let result = loop {
        if let Err(err) = terminal.draw(|frame| chrome::render(frame, &app)) {
            break Err(err);
        }

        let timeout = tick_rate.saturating_sub(last_tick.elapsed());
        match event::poll(timeout) {
            Ok(true) => match event::read() {
                Ok(Event::Key(key)) if key.kind == KeyEventKind::Press => app.on_key(key.code),
                Ok(_) => {}
                Err(err) => break Err(err),
            },
            Ok(false) => {}
            Err(err) => break Err(err),
        }

        if last_tick.elapsed() >= tick_rate {
            app.on_tick();
            last_tick = Instant::now();
        }

        if app.should_quit {
            break Ok(());
        }
    };

    ratatui::restore();
    result
}
