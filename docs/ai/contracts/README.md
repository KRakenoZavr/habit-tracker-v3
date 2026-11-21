---
covers: [docs/ai/contracts/**]
verified_at: cc7dbb2
owner: architect
---
# Contracts

One file per module boundary. Contracts are the cheapest precise context for a small model, so prefer
machine-checkable formats over prose:

| Kind | Format |
|---|---|
| HTTP API | `openapi.yaml` (OpenAPI 3.1) |
| Messages, configs, save files | JSON Schema (`*.schema.json`) |
| Python module API | `.pyi` stub or Pydantic models |
| Rust crate API | `<crate>.rs` with trait/struct signatures and doc comments, no bodies |
| C# / Unity | `I<Name>.cs` interfaces |
| C++ / Unreal | header excerpts (`*.h`) |
| TypeScript components | `*.d.ts` prop types |

Rules
- Signatures plus one-line behavior notes, error cases and invariants. No implementation.
- A contract change is its own ticket (or an ADR if it is a design change) and is done before consumers.
- Tickets copy the needed part of a contract into their Interface section, or list the file in `files_read`.

Template for a prose contract (`<module>.md`), when no typed format fits:

```text
## <function or message name>
signature: <exact signature>
does: <one sentence>
errors: <which, when>
invariants: <what always holds>
```
