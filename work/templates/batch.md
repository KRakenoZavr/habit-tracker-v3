---
title: Define Grid and Direction types
module: core
difficulty: S
files_owned: [src/core/grid.rs]
files_read: [docs/ai/contracts/core.rs]
verify: ["cargo test -p core grid"]
---
## Goal
Pure grid types every other ticket builds on.

## Interface
```rust
pub struct Pos { pub x: i32, pub y: i32 }
pub enum Dir { Up, Down, Left, Right }
impl Pos { pub fn step(self, d: Dir, w: i32, h: i32) -> Pos; } // wraps around edges
```

## Steps
1. Add the types and `step`.
2. Unit tests for all four directions and both wrap edges.

## Acceptance criteria
- [ ] wraps at every edge — `cargo test -p core grid::wraps`

## Out of scope
- Rendering.
%%%
---
title: Snake movement and growth
module: core
difficulty: S
depends_on: ["@1"]
files_owned: [src/core/snake.rs]
files_read: [docs/ai/contracts/core.rs]
verify: ["cargo test -p core snake"]
---
## Goal
Move the snake one cell per tick; grow by one when it eats.

## Interface
```rust
pub struct Snake { /* body: VecDeque<Pos> */ }
impl Snake { pub fn new(head: Pos, len: usize) -> Self; pub fn step(&mut self, d: Dir, grow: bool); pub fn head(&self) -> Pos; }
```

## Steps
1. Implement `new`, `step`, `head`.
2. Tests: moves, grows, cannot reverse into itself.

## Acceptance criteria
- [ ] grows by one — `cargo test -p core snake::grows`
<!--
Batch file for: python scripts/agent/ticket.py new-batch work/templates/batch.md --milestone M1 --ready
- Tickets are separated by a line containing only %%%
- Frontmatter: any ticket key; omitted keys come from work/templates/ticket.md
- depends_on: "@1" = first ticket of this batch, or a real id like T-0004
- One file + one command instead of one write per ticket: far fewer architect calls.
-->
