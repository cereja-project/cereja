# Modern stack integrations

Apply only to the frameworks and major versions already selected by the project.

## FastAPI

Choose `async def` for awaitable I/O. A synchronous route or dependency declared
with `def` runs in a worker thread; ordinary helper calls do not receive that
automatic treatment. Offload a synchronous I/O helper called inside an async
route, or keep the route synchronous when appropriate. Do not convert a working
synchronous application merely for stylistic consistency.

Preserve dependency injection, lifecycle and routing conventions. Verify public
status codes, validation errors and response fields through the actual ASGI app.

## Pydantic v2

Model construction can coerce inputs; choose strict validation only where the
contract requires it. Keep input and output boundaries explicit where their fields
or permissions differ. For PATCH, distinguish omitted fields from explicit null
using the project's update semantics (for example `model_dump(exclude_unset=True)`).
Review serialization of private fields; do not return a persistence object without
checking the externally exposed representation. Do not apply v2 APIs to v1 projects.

## SQLAlchemy 2.x

Keep the existing Session or AsyncSession model. Each concurrent task needs its own
AsyncSession; it is mutable transaction state. In async code, plan relationship
loading explicitly to avoid accidental implicit I/O. Use eager loading or targeted
queries according to access patterns, and verify query counts before optimizing.

## Sources and applicability

Checked 2026-09-09. FastAPI documentation is rolling; confirm the project's pinned
version before relying on a version-specific API. Pydantic guidance targets v2 and
SQLAlchemy guidance targets 2.x; these are not migration requirements.

- [FastAPI concurrency](https://fastapi.tiangolo.com/async/)
- [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
- [Pydantic serialization](https://docs.pydantic.dev/latest/concepts/serialization/)
- [SQLAlchemy async sessions and implicit I/O](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
