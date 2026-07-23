//! Live system metrics for the Unicorn dashboard, backed by [`sysinfo`].
//!
//! A single [`MetricsCollector`] should be created once and reused: most of
//! `sysinfo`'s numbers (especially CPU usage) are computed as a diff
//! between two refreshes, so calling [`MetricsCollector::refresh`] on a
//! fixed tick (e.g. once a second, matching `ui.refresh_interval_ms`) is
//! what makes the dashboard's live gauges and sparklines meaningful.

use sysinfo::{Disks, Networks, System};

/// A point-in-time snapshot of system resource usage, cheap to clone and
/// hand off to the TUI layer for rendering.
#[derive(Debug, Clone, Default)]
pub struct SystemSnapshot {
    pub cpu_percent: f32,
    pub per_core_percent: Vec<f32>,
    pub memory_used_bytes: u64,
    pub memory_total_bytes: u64,
    pub disks: Vec<DiskSnapshot>,
    pub network_rx_bytes_per_tick: u64,
    pub network_tx_bytes_per_tick: u64,
    pub load_average_one: f64,
}

impl SystemSnapshot {
    pub fn memory_percent(&self) -> f32 {
        if self.memory_total_bytes == 0 {
            0.0
        } else {
            self.memory_used_bytes as f32 / self.memory_total_bytes as f32 * 100.0
        }
    }
}

#[derive(Debug, Clone)]
pub struct DiskSnapshot {
    pub mount_point: String,
    pub total_bytes: u64,
    pub available_bytes: u64,
}

impl DiskSnapshot {
    pub fn used_bytes(&self) -> u64 {
        self.total_bytes.saturating_sub(self.available_bytes)
    }

    pub fn used_percent(&self) -> f32 {
        if self.total_bytes == 0 {
            0.0
        } else {
            self.used_bytes() as f32 / self.total_bytes as f32 * 100.0
        }
    }
}

/// Owns the long-lived `sysinfo` handles so repeated refreshes are cheap
/// and CPU-usage diffing works correctly.
pub struct MetricsCollector {
    system: System,
    disks: Disks,
    networks: Networks,
}

impl MetricsCollector {
    pub fn new() -> Self {
        let mut system = System::new_all();
        system.refresh_all();
        Self { system, disks: Disks::new_with_refreshed_list(), networks: Networks::new_with_refreshed_list() }
    }

    /// Refresh every underlying source and return a fresh snapshot.
    ///
    /// Note: per `sysinfo`'s own docs, CPU usage is only accurate after at
    /// least two refreshes with some time between them, so the very first
    /// snapshot after startup may report `0.0` for `cpu_percent`.
    pub fn refresh(&mut self) -> SystemSnapshot {
        self.system.refresh_cpu_usage();
        self.system.refresh_memory();
        self.disks.refresh(true);
        self.networks.refresh(true);

        let per_core_percent: Vec<f32> = self.system.cpus().iter().map(|cpu| cpu.cpu_usage()).collect();

        let disks = self
            .disks
            .list()
            .iter()
            .map(|disk| DiskSnapshot {
                mount_point: disk.mount_point().to_string_lossy().to_string(),
                total_bytes: disk.total_space(),
                available_bytes: disk.available_space(),
            })
            .collect();

        let (rx, tx) = self
            .networks
            .iter()
            .fold((0u64, 0u64), |(rx, tx), (_name, data)| (rx + data.received(), tx + data.transmitted()));

        SystemSnapshot {
            cpu_percent: self.system.global_cpu_usage(),
            per_core_percent,
            memory_used_bytes: self.system.used_memory(),
            memory_total_bytes: self.system.total_memory(),
            disks,
            network_rx_bytes_per_tick: rx,
            network_tx_bytes_per_tick: tx,
            load_average_one: System::load_average().one,
        }
    }
}

impl Default for MetricsCollector {
    fn default() -> Self {
        Self::new()
    }
}
