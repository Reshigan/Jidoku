"""Both repository implementations, held to one set of semantics.

repository.py has always said this file parametrises over both implementations; it did not exist,
so the SQLite store's agreement with the in-memory reference was an assertion rather than a test.
It is a test now — and it is the file to extend when the Repository protocol grows a method,
because a protocol only one implementation satisfies is not an interface.
"""
import pytest
from jidoka_core.repository import InMemoryRepository, RepositoryError, SqliteRepository, open_repository

EID = "e-1"


@pytest.fixture(params=["memory", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        return InMemoryRepository()
    return SqliteRepository(str(tmp_path / "jidoka.db"))


def test_drafts_round_trip(repo):
    drafts = [{"object": "FOCostCenter", "external_code": "CC-9000", "rationale": None,
               "source": {"workbook": "tenant-extract:SF-PRD", "signed_by": "", "date": ""}}]
    repo.save_drafts(EID, drafts)
    assert repo.load_drafts(EID) == drafts


def test_an_engagement_with_no_drafts_reads_empty_not_missing(repo):
    """An unread system and a lost backlog must not look the same to the caller."""
    assert repo.load_drafts("never-seen") == []


def test_saving_drafts_replaces_rather_than_appends(repo):
    """The live system is the authority on what it currently contains."""
    repo.save_drafts(EID, [{"external_code": "CC-1"}])
    repo.save_drafts(EID, [{"external_code": "CC-2"}])
    assert repo.load_drafts(EID) == [{"external_code": "CC-2"}]


def test_drafts_are_scoped_to_their_engagement(repo):
    repo.save_drafts(EID, [{"external_code": "CC-1"}])
    repo.save_drafts("e-2", [{"external_code": "CC-2"}])
    assert repo.load_drafts(EID) == [{"external_code": "CC-1"}]


def test_stored_drafts_are_copies_not_the_callers_list(repo):
    """A caller mutating its own list must not rewrite what was persisted."""
    mine = [{"external_code": "CC-1"}]
    repo.save_drafts(EID, mine)
    mine[0]["external_code"] = "CC-999"
    assert repo.load_drafts(EID) == [{"external_code": "CC-1"}]


def test_the_ledger_has_no_update_or_delete_path(repo):
    """Append-only at the storage layer, not only in core."""
    for name in ("update_ledger", "delete_ledger", "remove_ledger"):
        assert not hasattr(repo, name)


def test_an_unsupported_db_url_is_refused_by_name():
    with pytest.raises(RepositoryError) as ex:
        open_repository("postgres://localhost/jidoka")
    assert "sqlite:///" in str(ex.value)
