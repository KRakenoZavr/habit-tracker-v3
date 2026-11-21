# Profile: Rust
- Layout: cargo workspace; one crate per module in `modules.yaml`. Crate boundaries are ticket-ownership boundaries.
- Gates (`verify.commands`): `cargo fmt --all --check`, `cargo clippy --workspace --all-targets -- -D warnings`, `cargo nextest run --workspace` (or `cargo test`).
- Ticket verify: `cargo check -p <crate>`, `cargo clippy -p <crate> -- -D warnings`, `cargo nextest run -p <crate> <filter>`.
- Contracts: public traits and types in a small `*-api` crate or in `docs/ai/contracts/<crate>.rs` stubs.
- Feed compiler errors back verbatim (truncated to the tail): they are the best feedback a small model gets.
- Lock resources: `Cargo.lock`, root `Cargo.toml`, any crate's `Cargo.toml` `[dependencies]` section.
- Avoid `unsafe` and new macros in S/M tickets. Generic-heavy or lifetime-heavy APIs → `difficulty: L`.
- Games (Bevy etc.): keep systems small and pure over components; document components/systems in `docs/architecture/game/ecs.yaml`.
- `.gitignore`: `target/`
