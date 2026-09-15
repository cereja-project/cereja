# Tests that prove backend behavior

Keep the existing runner and suite layout. Do not reorganize tests to match a
template. Norte controls the development sequence; this reference selects evidence.

- For HTTP contracts, use the framework's real test client or in-process transport.
  Check status, payload, validation and sensitive-field exclusion through the route,
  not only by directly calling its handler. Include lifecycle handling if relevant.
- For SQL, constraints, rollback and persistence, use an isolated real database.
  Observe committed state through another connection where visibility matters.
  SQLite does not prove PostgreSQL-specific behavior; use the target engine when
  the claim depends on its dialect, isolation or locking.
- For async behavior, exercise the application and the actual scheduling boundary.
  Prefer controlled events or thread-identity observations over arbitrary sleeps.
  A mocked business result alone cannot establish nonblocking behavior.
- For external integrations, replace the provider boundary, not the internal
  semantics under test. Keep live services out of ordinary unit tests.
- For filesystem persistence, use per-test temporary paths and explicit resource
  cleanup. Reopen persisted state; an in-memory fake cannot prove durability.

Use factories or fixtures when they remove meaningful setup duplication, keeping
scenario-defining inputs visible. Inject clocks or expensive operations at a real
boundary when necessary; do not weaken production security defaults for test speed.

When dependencies are restricted, `unittest` and `tempfile` replace pytest fixtures
and plugins. A failed import, skipped infrastructure test or empty discovered suite
does not establish success. Report what was actually executed and what remains
unverified; do not add tests solely to satisfy a coverage percentage.

## Sources and applicability

Checked 2026-09-09. Flask reference targets 3.1.x; FastAPI documentation is rolling;
unittest reference is Python 3.14. The choice of evidence above is a methodology
rule; confirm each project's framework/client version compatibility.

- [Flask testing](https://flask.palletsprojects.com/en/stable/testing/)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Python unittest](https://docs.python.org/3/library/unittest.html)
