---
covers: [src/**]
verified_at: none
owner: architect
---
# Gotchas (learned failure modes)
<!--
Add a line when the same mistake appears in 2+ reviews. Prune every milestone; keep under ~60 lines.
Format: - [module] what goes wrong → what to do instead. (source: T-xxxx)
-->

## all
- [tickets] A ticket's pyright command must include the test files that carry type-level criteria (Protocol checks). (source: T-0002)
- [tickets] Spell out edge inputs in Interface: non-enum values, bool/float as int, `from x import y` forms. (source: T-0001, T-0003)

## core
- Validate types, not just ranges: `True` and `1.5` are not valid targets (bool is an int subclass). (source: T-0001)

## storage
- Deletes are ONE `sa.delete(...)` + `rowcount`; get-then-delete lets two racing deletes both "succeed". (source: M1 review)
- Ids beyond int64 crash SQLite binds: guard with `_in_range` and treat them as missing. (source: M1 review)

## api
- Request models use `StrictInt`/`StrictBool`/`StrictStr`; response models have no defaults for required fields. (source: M1 review)
- Framework HTTP errors (404 route, 405) need the envelope handler too, keeping headers like `Allow`. (source: M1 review) 
