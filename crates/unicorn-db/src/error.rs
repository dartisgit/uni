use thiserror::Error;

pub type Result<T> = std::result::Result<T, DbError>;

#[derive(Debug, Error)]
pub enum DbError {
    #[error("failed to connect to Postgres: {0}")]
    Connect(#[source] sqlx::Error),

    #[error("failed to run database migrations: {0}")]
    Migrate(#[source] sqlx::migrate::MigrateError),

    #[error("query failed: {0}")]
    Query(#[source] sqlx::Error),
}
