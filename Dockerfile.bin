# syntax=docker/dockerfile:1
#
# Multi-stage build for Unicorn (crates/unicorn-cli -> the `unicorn` binary).
#
# Uses cargo-chef so dependency compilation is cached in its own Docker
# layer, separate from your source code - changing a .rs file won't force
# every dependency in the workspace to recompile, only cargo-chef's own
# "cook" step re-runs when Cargo.toml/Cargo.lock actually change.
#
# IMPORTANT - sqlx offline mode:
# unicorn-db uses sqlx::query! macros, which type-check SQL against a real
# database schema at compile time. This build has no Postgres available,
# so it relies on a checked-in `.sqlx/` query cache instead. Before this
# Dockerfile will build successfully, run ONCE against a real Postgres
# (with migrations applied):
#
#   cargo install sqlx-cli --no-default-features --features postgres,rustls
#   cargo sqlx prepare --workspace
#
# then commit the .sqlx/ directory this creates at the workspace root.
# SQLX_OFFLINE=true below tells the build to use that cache instead of
# trying to reach a database that isn't there.

# A pinned version here goes stale: sqlx and sysinfo (and others) bump
# their MSRV on ordinary patch releases, so a version that compiled
# cleanly one month can fail the next with "requires rustc X.Y" even
# though nothing in this repo changed. `rust:slim-bookworm` (no version
# tag) tracks whatever the current stable release is, same as `rustup
# update stable` would give you locally - if a build ever fails with an
# MSRV error again, `rustup update stable && cargo update` locally first
# to confirm it's fixed before touching this file.
#
# If reproducible builds matter more than always-current here, pin a
# specific version instead (check https://releases.rs for current
# stable) and expect to bump it periodically as dependencies require.

# ---------------------------------------------------------------------------
# Stage 1: chef - base image with cargo-chef installed, reused by both the
# planner and builder stages below so Docker can cache each independently.
# ---------------------------------------------------------------------------
FROM rust:slim-bookworm AS chef
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN cargo install --locked cargo-chef

# ---------------------------------------------------------------------------
# Stage 2: planner - computes cargo-chef's dependency "recipe" from the
# workspace's Cargo.toml/Cargo.lock files only. Copying the full source
# here is fine: this stage's own cache invalidates on every source change,
# but that's cheap (`cargo chef prepare` doesn't compile anything), and
# critically it does NOT invalidate the builder stage's dependency cache
# below, since that only depends on this stage's recipe.json output.
# ---------------------------------------------------------------------------
FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

# ---------------------------------------------------------------------------
# Stage 3: builder - restores the dependency recipe, builds every crate's
# dependencies (cached layer, only invalidated when recipe.json changes -
# i.e. when Cargo.toml/Cargo.lock actually change), then builds the real
# workspace on top.
# ---------------------------------------------------------------------------
FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
RUN cargo chef cook --release --recipe-path recipe.json

COPY . .

# See the sqlx offline mode note at the top of this file - this build has
# no Postgres available, so it relies entirely on a checked-in .sqlx/
# cache under the workspace root.
ENV SQLX_OFFLINE=true

RUN cargo build --release --bin unicorn

# ---------------------------------------------------------------------------
# Stage 4: runtime - slim Debian base, no Rust toolchain, just the compiled
# binary and whatever it needs at runtime (a CA bundle, since russh/sqlx's
# rustls-based TLS still needs root certificates to verify connections).
# ---------------------------------------------------------------------------
FROM debian:bookworm-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --create-home --shell /usr/sbin/nologin unicorn

WORKDIR /app

COPY --from=builder /app/target/release/unicorn /usr/local/bin/unicorn
COPY --from=builder /app/config/unicorn.toml /app/unicorn.toml

# /app/data is where SshConfig::host_key_path, StorageConfig::repositories_dir,
# and LoggingConfig::file all point by default (see config/unicorn.toml) -
# owned by the unprivileged user so the binary can write to it at runtime.
RUN mkdir -p /app/data && chown -R unicorn:unicorn /app

USER unicorn

# SSH front door (SshConfig::port default) and a reserved slot for a future
# HTTP/API server (ServerConfig::http_port default) - expose both now so
# the image doesn't need rebuilding just to add the port later.
EXPOSE 2222 3000

ENTRYPOINT ["/usr/local/bin/unicorn"]
CMD ["/app/unicorn.toml"]
