"""Status codes whose names changed between Starlette releases.

Starlette 1.x renamed two constants and kept the old spellings as deprecated
aliases:

| deprecated                        | current                     |
| --------------------------------- | --------------------------- |
| `HTTP_422_UNPROCESSABLE_ENTITY`    | `HTTP_422_UNPROCESSABLE_CONTENT` |
| `HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE` | `HTTP_416_RANGE_NOT_SATISFIABLE` |

Referencing the old name warns on 1.x; referencing the new name raises
`AttributeError` on 0.4x, which this project still declares support for through
`fastapi>=0.116,<1`. The numeric value is 422 and 416 in every release, so the
project names them once here instead of depending on which Starlette happens to
be installed. Both spellings mean the same thing; only the library changed.

The alternative — pinning FastAPI to one minor and using its names — was rejected
because it would make the host checkout and the container disagree about what
the dependency set is, which is exactly the class of problem the pinned ceilings
in `pyproject.toml` exist to prevent.
"""

#: 422. The request was well formed but could not be processed.
HTTP_422_UNPROCESSABLE = 422

#: 416. The requested byte range does not exist in the resource.
HTTP_416_RANGE_NOT_SATISFIABLE = 416

#: 413. The payload is larger than this endpoint accepts. Renamed to
#: `HTTP_413_CONTENT_TOO_LARGE` in Starlette 1.x, same situation as 422 and 416,
#: and it was being spelled out by hand in three routers while this module
#: existed precisely so nobody had to.
HTTP_413_CONTENT_TOO_LARGE = 413

__all__ = [
    "HTTP_413_CONTENT_TOO_LARGE",
    "HTTP_416_RANGE_NOT_SATISFIABLE",
    "HTTP_422_UNPROCESSABLE",
]
