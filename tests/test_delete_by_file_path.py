import unittest
from unittest.mock import patch

from scripts import delete_by_file_path


class DeleteByFilePathTests(unittest.TestCase):
    def test_collect_target_sources_normalizes_file_path(self):
        with patch.object(delete_by_file_path.os.path, "isdir", return_value=False), \
             patch.object(delete_by_file_path.os.path, "abspath", return_value="C:\\repo\\src\\app.py"):
            sources = delete_by_file_path._collect_target_sources("src/app.py")

        self.assertEqual(["C:/repo/src/app.py"], sources)

    def test_delete_bm25_documents_saves_index_after_removal(self):
        class FakeIndex:
            def __init__(self):
                self.saved_to = None

            def delete_by_sources(self, sources):
                self.sources = sources
                return 2

            def save(self, path):
                self.saved_to = path

        fake_index = FakeIndex()

        with patch.object(delete_by_file_path.Config, "get", return_value="bm25.pkl"), \
             patch.object(delete_by_file_path.os.path, "exists", return_value=True), \
             patch.object(delete_by_file_path.BM25Index, "load", return_value=fake_index):
            removed = delete_by_file_path._delete_bm25_documents_by_sources(["C:/repo/src/app.py"])

        self.assertEqual(2, removed)
        self.assertEqual(["C:/repo/src/app.py"], fake_index.sources)
        self.assertEqual("bm25.pkl", fake_index.saved_to)


if __name__ == "__main__":
    unittest.main()
