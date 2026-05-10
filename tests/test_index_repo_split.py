import importlib.util
import sys
import textwrap
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


def _install_import_stubs():
    stubs = {
        "langchain_community": types.ModuleType("langchain_community"),
        "langchain_community.document_loaders": types.ModuleType("langchain_community.document_loaders"),
        "langchain_community.embeddings": types.ModuleType("langchain_community.embeddings"),
        "langchain_text_splitters": types.ModuleType("langchain_text_splitters"),
        "langchain_chroma": types.ModuleType("langchain_chroma"),
        "langchain_core": types.ModuleType("langchain_core"),
        "langchain_core.documents": types.ModuleType("langchain_core.documents"),
    }
    stubs["langchain_community.document_loaders"].TextLoader = object
    stubs["langchain_community.embeddings"].DashScopeEmbeddings = object
    stubs["langchain_text_splitters"].RecursiveCharacterTextSplitter = object
    stubs["langchain_chroma"].Chroma = object
    stubs["langchain_core.documents"].Document = object
    return stubs


def _load_index_repo():
    stubs = _install_import_stubs()
    originals = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "index_repo.py"
        spec = importlib.util.spec_from_file_location("index_repo_for_tests", script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in originals.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


index_repo = _load_index_repo()


class PythonAstSplitTests(unittest.TestCase):
    def test_keeps_small_class_as_single_block_with_decorators(self):
        content = textwrap.dedent(
            '''
            import os

            @decorator
            class Service(Base):
                """service docs"""

                async def run(self):
                    return "ok"

            def helper():
                return 1
            '''
        ).strip()

        blocks = index_repo.extract_python_classes_and_functions(content, max_class_length=3000)

        self.assertEqual(3, len(blocks))
        self.assertEqual("import os", blocks[0])
        self.assertTrue(blocks[1].startswith("@decorator\nclass Service(Base):"))
        self.assertIn('async def run(self):\n        return "ok"', blocks[1])
        self.assertEqual("def helper():\n    return 1", blocks[2])

    def test_splits_large_class_by_ast_methods(self):
        content = textwrap.dedent(
            '''
            class Big:
                class Nested:
                    def nested_method(self):
                        return "nested"

                @property
                def name(self):
                    return "big"

                async def load(self):
                    return 42
            '''
        ).strip()

        blocks = index_repo.extract_python_classes_and_functions(content, max_class_length=10)

        self.assertEqual(
            [
                'class Big:\n    class Nested:\n        def nested_method(self):\n            return "nested"',
                '    @property\n    def name(self):\n        return "big"',
                '    async def load(self):\n        return 42',
            ],
            blocks,
        )

    def test_falls_back_to_scanner_for_invalid_python(self):
        content = textwrap.dedent(
            '''
            class Broken:
                def ok(self):
                    return 1

            def helper():
                return (
            '''
        ).strip()

        blocks = index_repo.extract_python_classes_and_functions(content, max_class_length=3000)

        self.assertEqual(2, len(blocks))
        self.assertTrue(blocks[0].startswith("class Broken:"))
        self.assertTrue(blocks[1].startswith("def helper():"))


class CodeSplitterStrategyTests(unittest.TestCase):
    def test_file_type_classification_separates_code_and_docs(self):
        self.assertTrue(index_repo.is_supported_code_file("service.py"))
        self.assertTrue(index_repo.is_supported_doc_file("README.md"))
        self.assertFalse(index_repo.is_supported_code_file("README.md"))

    def test_python_strategy_is_selected_and_keeps_existing_behavior(self):
        content = textwrap.dedent(
            '''
            import os

            def helper():
                return os.getcwd()
            '''
        ).strip()

        splitter = index_repo.get_code_splitter(".py")
        blocks = splitter.split(content, max_class_length=3000)

        self.assertIsInstance(splitter, index_repo.PythonCodeSplitter)
        self.assertEqual(["import os", "def helper():\n    return os.getcwd()"], blocks)

    def test_tree_sitter_strategy_splits_javascript_exports_and_functions(self):
        content = textwrap.dedent(
            '''
            import React from "react";

            export function greet(name) {
              return `Hello, ${name}`;
            }

            const Hello = ({ name }) => {
              return <div>Hello, {name}</div>;
            };
            '''
        ).strip()

        splitter = index_repo.get_code_splitter(".jsx")
        blocks = splitter.split(content, max_class_length=3000)

        self.assertIsInstance(splitter, index_repo.TreeSitterCodeSplitter)
        self.assertEqual(3, len(blocks))
        self.assertEqual('import React from "react";', blocks[0])
        self.assertTrue(blocks[1].startswith("export function greet"))
        self.assertTrue(blocks[2].startswith("const Hello"))

    def test_tree_sitter_strategy_splits_go_functions_and_methods(self):
        content = textwrap.dedent(
            '''
            package main

            func greet(name string) string {
                return "hello " + name
            }

            func (s Service) Run() error {
                return nil
            }
            '''
        ).strip()

        blocks = index_repo.get_code_splitter(".go").split(content, max_class_length=3000)

        self.assertEqual(3, len(blocks))
        self.assertEqual("package main", blocks[0])
        self.assertTrue(blocks[1].startswith("func greet"))
        self.assertTrue(blocks[2].startswith("func (s Service) Run"))

    def test_unsupported_code_extension_uses_regex_fallback(self):
        content = "fn main() {}\n\nstruct App;"

        splitter = index_repo.get_code_splitter(".unknown")

        self.assertIsInstance(splitter, index_repo.RegexCodeSplitter)
        self.assertEqual([content], splitter.split(content, max_class_length=3000))

    def test_exclude_dirs_keeps_cache_and_packages_as_separate_entries(self):
        self.assertIn("cache", index_repo.exclude_dirs)
        self.assertIn("packages", index_repo.exclude_dirs)
        self.assertNotIn("cachepackages", index_repo.exclude_dirs)

    def test_directory_exclusion_supports_glob_patterns(self):
        self.assertTrue(index_repo.should_exclude_dir("service.egg-info"))
        self.assertTrue(index_repo.should_exclude_dir("node_modules"))
        self.assertFalse(index_repo.should_exclude_dir("src"))

    def test_index_repo_skips_unsupported_non_code_files(self):
        processed_files = []

        class FakeConfig:
            bm25_path = "bm25.pkl"

            @staticmethod
            def load():
                return None

            @staticmethod
            def get(key, default=None):
                values = {
                    "repo.path": "repo",
                    "chroma.persist_dir": "db",
                    "chroma.chunk_size.doc": 800,
                    "chroma.chunk_size.code": 2000,
                    "chroma.chunk_overlap": 100,
                    "splitting.max_class_length": 3000,
                    "embeddings.model": "model",
                    "bm25.persist_path": FakeConfig.bm25_path,
                }
                return values.get(key, default)

            @staticmethod
            def get_env(key):
                return None

        class FakeTextLoader:
            def __init__(self, path, encoding=None):
                processed_files.append(path)

            def load(self):
                return []

        with (
            patch.object(index_repo, "Config", FakeConfig),
            patch.object(index_repo, "TextLoader", FakeTextLoader),
            patch.object(index_repo.os, "walk", return_value=[("repo", [], ["guide.md", "notes.json"])]),
        ):
            index_repo.index_repo("repo", "db")

        self.assertEqual(["repo/guide.md"], processed_files)

    def test_code_chunks_use_configured_code_chunk_size(self):
        class FakeDoc:
            def __init__(self, page_content, metadata=None):
                self.page_content = page_content
                self.metadata = metadata or {}

        class FakeConfig:
            bm25_path = "bm25.pkl"

            @staticmethod
            def load():
                return None

            @staticmethod
            def get(key, default=None):
                values = {
                    "repo.path": "repo",
                    "chroma.persist_dir": "db",
                    "chroma.chunk_size.doc": 800,
                    "chroma.chunk_size.code": 12,
                    "chroma.chunk_overlap": 100,
                    "splitting.max_class_length": 3000,
                    "embeddings.model": "model",
                    "bm25.persist_path": FakeConfig.bm25_path,
                }
                return values.get(key, default)

            @staticmethod
            def get_env(key):
                return None

        class FakeTextLoader:
            def __init__(self, path, encoding=None):
                pass

            def load(self):
                return [FakeDoc("def helper():\n    return 'abcdefghijklmnopqrstuvwxyz'")]

        captured_chunks = []

        def fake_document(page_content, metadata):
            captured_chunks.append(page_content)
            return FakeDoc(page_content, metadata)

        with TemporaryDirectory() as temp_dir:
            FakeConfig.bm25_path = str(Path(temp_dir) / "bm25.pkl")
            with (
                patch.object(index_repo, "Config", FakeConfig),
                patch.object(index_repo, "TextLoader", FakeTextLoader),
                patch.object(index_repo, "Document", fake_document),
                patch.object(index_repo.os, "walk", return_value=[("repo", [], ["service.py"])]),
            ):
                index_repo.index_repo("repo", temp_dir)

        self.assertEqual(["def helper()"], captured_chunks)


if __name__ == "__main__":
    unittest.main()
