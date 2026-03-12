"""KnowledgeStoreSnapshot — filesystem snapshot for test isolation.

Context manager that captures a copy of the knowledge store directory
before tests run and restores it on exit, ensuring test mutations don't
persist across test sessions.

Usage:
    with KnowledgeStoreSnapshot(store_path="/path/to/kb_store"):
        # Mutate knowledge store freely
        kb.add_piece(...)
        kb.remove_piece(...)
    # Original state is restored here
"""

import os
import shutil
import tempfile


class KnowledgeStoreSnapshot:
    """Context manager for filesystem-level knowledge store snapshots.

    On enter: copies store_path to a temp directory.
    On exit: restores the original from the backup (even on exception).

    Attributes:
        store_path: Path to the knowledge store directory to snapshot.
    """

    def __init__(self, store_path: str):
        self.store_path = store_path
        self._backup_path = None

    def capture(self) -> str:
        """Create a backup copy of the store directory.

        Returns:
            Path to the backup directory.
        """
        self._backup_path = tempfile.mkdtemp(prefix="kb_snapshot_")
        if os.path.exists(self.store_path):
            # Copy contents, not the directory itself
            backup_store = os.path.join(self._backup_path, "store")
            shutil.copytree(self.store_path, backup_store)
        return self._backup_path

    def restore(self) -> None:
        """Restore the store directory from the backup."""
        if self._backup_path is None:
            return
        backup_store = os.path.join(self._backup_path, "store")
        if os.path.exists(self.store_path):
            shutil.rmtree(self.store_path)
        if os.path.exists(backup_store):
            shutil.copytree(backup_store, self.store_path)
        # Clean up temp backup
        shutil.rmtree(self._backup_path, ignore_errors=True)
        self._backup_path = None

    def __enter__(self):
        self.capture()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.restore()
        return False
