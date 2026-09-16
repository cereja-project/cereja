# Standard-library backend work

Honor the dependency boundary for runtime and tests. Use `unittest`,
`unittest.mock`, `tempfile` and `contextlib` when third-party test tools are excluded.
Keep the existing runner if only runtime dependencies are restricted.

Use `sqlite3` for local relational persistence when it fits the requirements, with
bound parameters, explicit transaction ownership and deterministic connection
closure. A connection context manager commits or rolls back; it does not close the
connection. Prefer explicit closure or `contextlib.closing` when owning it.

`http.server` is suitable for bounded local development utilities, not a general
production backend default. Its basic security checks do not supply a production
deployment architecture. If production requirements cannot be met within the
dependency constraint, surface that conflict rather than quietly dropping either.

Use existing dataclasses or ordinary types for internal data, with explicit boundary
validation where needed. Do not recreate an ORM, validation framework or web stack
to preserve a dependency count.

For unpredictable security tokens, use `secrets`. For compatible secret-value
comparisons, use `hmac.compare_digest`, respecting accepted types. These APIs are
not a complete password-storage or encryption design; use established libraries
and protocols when required, or explain a conflicting dependency restriction.
Do not invent nonce/IV rules: requirements depend on the cryptographic algorithm.

## Sources and applicability

Checked 2026-09-09 against Python 3.14 documentation. Check the supported Python
version; `sqlite3.autocommit` is available from 3.12 and differs from legacy
transaction control. Avoid silently changing a project's transaction mode.

- [sqlite3 connection and transaction control](https://docs.python.org/3/library/sqlite3.html)
- [http.server security limitations](https://docs.python.org/3/library/http.server.html)
- [unittest](https://docs.python.org/3/library/unittest.html)
- [secrets](https://docs.python.org/3/library/secrets.html)
- [hmac.compare_digest](https://docs.python.org/3/library/hmac.html#hmac.compare_digest)
