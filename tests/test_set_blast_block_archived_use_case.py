import pytest

from application.use_cases.set_blast_block_archived import (
    SetBlastBlockArchived, SetBlastBlockArchivedCommand,
)


class Persistence:
    def __init__(self): self.calls = []
    def load_domain_version(self, block_id): return 4
    def set_archived(self, block_id, expected_version, archived, actor_id):
        self.calls.append((block_id, archived, actor_id))


def test_block_archive_and_restore_delegate_to_focused_port():
    persistence = Persistence(); use_case = SetBlastBlockArchived(persistence)
    use_case.execute(SetBlastBlockArchivedCommand(3, True, 9, True, 4))
    use_case.execute(SetBlastBlockArchivedCommand(3, False, 9, True, 5))
    assert persistence.calls == [(3, True, 9), (3, False, 9)]


@pytest.mark.parametrize("archived", [True, False])
def test_viewer_cannot_archive_or_restore_block(archived):
    persistence = Persistence(); use_case = SetBlastBlockArchived(persistence)
    with pytest.raises(PermissionError):
        use_case.execute(SetBlastBlockArchivedCommand(3, archived, 9, False, 4))
    assert persistence.calls == []
