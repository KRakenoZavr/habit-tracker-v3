---
id: T-0007
title: Add retry with exponential backoff to HttpClient.get
status: ready
milestone: M2
module: io
depends_on: [T-0004]
files_owned: [src/io/http_client.py, tests/io/test_http_client.py]
files_read: [docs/ai/contracts/io.pyi]
lock_resources: []
difficulty: S
context_budget_tokens: none
max_review_rounds: none
review_round: 0
base: none
verify: ["pytest tests/io/test_http_client.py -x -q", "ruff check src/io/http_client.py", "pyright src/io/http_client.py"]
---
## Goal
`HttpClient.get` currently fails on the first transient error. Retry server errors and timeouts with exponential backoff so flaky upstreams do not break sync.

## Interface
```python
class HttpClient:
    def __init__(self, transport: Transport, *, max_retries: int = 3,
                 base_delay_s: float = 0.2, sleep: Callable[[float], None] = time.sleep) -> None: ...
    def get(self, url: str) -> Response: ...
# Retry ONLY on: status >= 500, TimeoutError. Never on 4xx.
# Delay before retry n (1-based): base_delay_s * 2**(n-1).
# After max_retries failed retries, re-raise the last error / return the last 5xx Response.
```

## Steps
1. Add `max_retries`, `base_delay_s`, `sleep` parameters to `__init__`, store them.
2. Wrap the transport call in `get` in a retry loop following the Interface rules.
3. Inject `sleep` so tests never really sleep.
4. Add tests: 5xx then 200 → returns 200 after 1 retry; 404 → no retry; timeout ×4 → raises; delays are 0.2, 0.4, 0.8.

## Acceptance criteria
- [ ] Retries 5xx and timeouts, not 4xx — `test_retries_only_transient_errors`
- [ ] Backoff delays exact — `test_backoff_delays`
- [ ] Gives up after `max_retries` — `test_gives_up_after_max_retries`

## Out of scope
- Jitter, async client, retry on POST.

## Notes from architect
- `Transport` is a Protocol; use a fake in tests, do not mock `requests`.

## Log
