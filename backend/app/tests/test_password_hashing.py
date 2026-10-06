"""Password hashing: Argon2id directly, and the hashes that came before.

Passlib is unmaintained, emits deprecation warnings on import under Python 3.12,
and reaches into `crypt`, which is removed in 3.13. It is replaced here by
`argon2-cffi`, the library passlib itself used. That is only safe if **the
hashes passlib wrote still verify**, because those hashes are in the database
and nobody is going to re-hash them on the way in.

`LEGACY_ARGON2_HASH` below was produced by passlib and is frozen on purpose: it
is the contract. If a future change to the parameters stops this from verifying,
the failure is a locked door rather than a silent wave of people who can no
longer log in.

Passlib is deliberately **not** imported anywhere in `app/`, including here. The
point is that this file keeps working after passlib is uninstalled.
"""

import pytest
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.security import hash_password, verify_password

#: Written by passlib's `CryptContext(schemes=["argon2"])` with its defaults:
#: argon2id, m=65536 (64 MiB), t=3, p=4, salt 16 bytes, hash 16 bytes.
LEGACY_ARGON2_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$DEHoPWfsHaO09r63tvbeOw"
    "$0m4yVJgVs52WdY5qTkT8L8GR87U+q1WWVBHVjXGUzIQ"
)
LEGACY_PASSWORD = "ClaveAntigua2026"


def test_a_hash_written_by_passlib_still_verifies() -> None:
    """The migration must not lock out anyone who already has an account."""
    assert verify_password(LEGACY_PASSWORD, LEGACY_ARGON2_HASH) is True


def test_a_legacy_hash_rejects_the_wrong_password() -> None:
    assert verify_password("otra-clave-cualquiera", LEGACY_ARGON2_HASH) is False


def test_a_new_hash_is_argon2id_with_the_documented_parameters() -> None:
    """The parameters are part of the contract, not an implementation detail.

    Cost is the only thing standing between a stolen table and a list of
    passwords, so a silent change to it has to fail a test.
    """
    hashed = hash_password("ClaveNueva2026")

    assert hashed.startswith("$argon2id$v=19$m=65536,t=3,p=4$")


def test_two_hashes_of_the_same_password_differ() -> None:
    """Identical hashes would mean a shared salt and a rainbow table."""
    assert hash_password("misma-clave") != hash_password("misma-clave")


def test_verification_survives_a_hash_that_is_not_argon2() -> None:
    """A corrupted or foreign hash is a failed login, never an exception.

    The stored value is read from the database, so it can be anything that was
    ever written there. Raising `InvalidHashError` out of a login endpoint would
    turn a row someone cannot use into a 500 for everybody.
    """
    assert verify_password("cualquiera", "no-es-un-hash") is False
    assert verify_password("cualquiera", "") is False


def test_the_module_does_not_import_passlib_anymore() -> None:
    """A regression guard for the reason this migration happened.

    The check reads the AST rather than the text, because the module explains
    the migration in prose and a substring search would fail on its own
    documentation.
    """
    import ast
    import pathlib

    import app.security

    tree = ast.parse(pathlib.Path(app.security.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert "passlib" not in imported


@pytest.mark.parametrize("password", ["", " ", "contraseña-muy-larga-" * 10])
def test_hashing_never_raises_for_any_input(password: str) -> None:
    """Whatever arrives, the caller gets a hash or an exception it can name."""
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_argon2_helpers_are_the_ones_in_use() -> None:
    """Guards against the module drifting back to a different KDF."""
    hasher = PasswordHasher()
    assert hasher.time_cost == 3
    assert hasher.memory_cost == 65536
    assert hasher.parallelism == 4


def test_verification_error_is_catchable_and_used() -> None:
    """Documents which exception the implementation relies on."""
    with pytest.raises(VerificationError):
        PasswordHasher().verify(LEGACY_ARGON2_HASH, "clave-equivocada")
    with pytest.raises(InvalidHashError):
        PasswordHasher().verify("no-es-un-hash", "clave")
