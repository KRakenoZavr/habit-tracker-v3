---
covers: [src/**]
verified_at: none
owner: architect
---
# Conventions (non-obvious only)
<!--
Only rules a competent engineer would get wrong in THIS repo. If the linter/formatter enforces it, delete it from here.
Keep under ~60 lines. Changes are flagged for line-by-line human review in the PR.
-->

## Errors
- <e.g. Domain errors are typed values (Result/exceptions subclassing AppError); never return None for failure.>

## Logging
- <e.g. Structured logs only via `log.event(name, **fields)`; no print().>

## Naming
- <e.g. Async functions end with `_async` only in the io module.>

## Testing
- <e.g. Tests are deterministic: inject clock and RNG seed; no sleeps.>
