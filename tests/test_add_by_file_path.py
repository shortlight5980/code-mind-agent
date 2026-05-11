import importlib.util
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def _install_import_stubs():
    utils_config = types.ModuleType("utils.config")
    utils_logger = types.ModuleType("utils.logger")

    class StubConfig:
        @staticmethod
        def load():
            return None

        @staticmethod
        def get(key, default=None):
            return default

        @staticmethod
        def get_env(key, default=""):
            return default

    class StubLogger:
        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def error(self, *args, **kwargs):
            return None

    utils_config.Config = StubConfig
    utils_logger.get_logger = lambda name="codemind": StubLogger()

    stubs = {
        "langchain_community": types.ModuleType("langchain_community"),
        "langchain_community.document_loaders": types.ModuleType("langchain_community.document_loaders"),
        "langchain_community.embeddings": types.ModuleType("langchain_community.embeddings"),
        "langchain_text_splitters": types.ModuleType("langchain_text_splitters"),
        "langchain_chroma": types.ModuleType("langchain_chroma"),
        "langchain_core": types.ModuleType("langchain_core"),
        "langchain_core.documents": types.ModuleType("langchain_core.documents"),
        "utils.config": utils_config,
        "utils.logger": utils_logger,
    }
    stubs["langchain_community.document_loaders"].TextLoader = object
    stubs["langchain_community.embeddings"].DashScopeEmbeddings = object
    stubs["langchain_text_splitters"].RecursiveCharacterTextSplitter = object
    stubs["langchain_chroma"].Chroma = object

    class FakeDocument:
        def __init__(self, page_content, metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}

    stubs["langchain_core.documents"].Document = FakeDocument
    return stubs


def _load_add_by_file_path():
    stubs = _install_import_stubs()
    originals = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "add_by_file_path.py"
        spec = importlib.util.spec_from_file_location("add_by_file_path_for_tests", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in originals.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


add_by_file_path = _load_add_by_file_path()


class AddByFilePathTests(unittest.TestCase):
    def test_collect_indexable_files_accepts_file_and_skips_unsupported(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            py_file = root / "service.py"
            py_file.write_text("def run():\n    return 1\n", encoding="utf-8")
            json_file = root / "settings.json"
            json_file.write_text("{}", encoding="utf-8")

            self.assertEqual(
                [py_file.resolve().as_posix()],
                add_by_file_path.collect_indexable_files(str(py_file)),
            )
            self.assertEqual([], add_by_file_path.collect_indexable_files(str(json_file)))

    def test_add_documents_by_source_reuses_index_repo_split_and_index_functions(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            py_file = root / "service.py"
            py_file.write_text("def run():\n    return 1\n", encoding="utf-8")

            class FakeConfig:
                @staticmethod
                def load():
                    return None

                @staticmethod
                def get(key, default=None):
                    values = {
                        "chroma.persist_dir": "db",
                        "bm25.persist_path": "bm25.pkl",
                        "embeddings.model": "model",
                    }
                    return values.get(key, default)

            fake_chunk = object()
            captured = {}

            def fake_build_chunks(file_paths):
                captured["file_paths"] = file_paths
                return [fake_chunk]

            def fake_deduplicate_chunks_by_hash(chunks):
                captured["deduplicated_chunks"] = chunks
                return chunks

            def fake_save_indexes(chunks, persist_dir, embedding_model, bm25_persist_path):
                captured["chunks"] = chunks
                captured["persist_dir"] = persist_dir
                captured["embedding_model"] = embedding_model
                captured["bm25_persist_path"] = bm25_persist_path
                return len(chunks)

            with (
                patch.object(add_by_file_path, "Config", FakeConfig),
                patch.object(add_by_file_path, "build_chunks", side_effect=fake_build_chunks),
                patch.object(add_by_file_path, "deduplicate_chunks_by_hash", side_effect=fake_deduplicate_chunks_by_hash),
                patch.object(add_by_file_path, "save_indexes", side_effect=fake_save_indexes),
            ):
                added_count = add_by_file_path.add_documents_by_source(str(py_file))

        self.assertEqual(1, added_count)
        self.assertEqual([py_file.resolve().as_posix()], captured["file_paths"])
        self.assertEqual([fake_chunk], captured["deduplicated_chunks"])
        self.assertEqual([fake_chunk], captured["chunks"])
        self.assertEqual("db", captured["persist_dir"])
        self.assertEqual("model", captured["embedding_model"])
        self.assertEqual("bm25.pkl", captured["bm25_persist_path"])


if __name__ == "__main__":
    unittest.main()
