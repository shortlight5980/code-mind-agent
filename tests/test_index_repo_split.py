import importlib.util
import sys
import textwrap
import types
import unittest
from pathlib import Path


def _install_import_stubs():
    stubs = {
        "langchain_community": types.ModuleType("langchain_community"),
        "langchain_community.document_loaders": types.ModuleType("langchain_community.document_loaders"),
        "langchain_community.embeddings": types.ModuleType("langchain_community.embeddings"),
        "langchain_text_splitters": types.ModuleType("langchain_text_splitters"),
        "langchain_chroma": types.ModuleType("langchain_chroma"),
        "langchain_core": types.ModuleType("langchain_core"),
        "langchain_core.documents": types.ModuleType("langchain_core.documents"),
        "utils": types.ModuleType("utils"),
        "utils.logger": types.ModuleType("utils.logger"),
        "utils.config": types.ModuleType("utils.config"),
    }
    stubs["langchain_community.document_loaders"].TextLoader = object
    stubs["langchain_community.embeddings"].DashScopeEmbeddings = object
    stubs["langchain_text_splitters"].RecursiveCharacterTextSplitter = object
    stubs["langchain_chroma"].Chroma = object
    stubs["langchain_core.documents"].Document = object
    stubs["utils.logger"].get_logger = lambda name: types.SimpleNamespace(warning=lambda *args, **kwargs: None)
    stubs["utils.config"].Config = object
    sys.modules.update(stubs)


def _load_index_repo():
    _install_import_stubs()
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "index_repo.py"
    spec = importlib.util.spec_from_file_location("index_repo_for_tests", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


if __name__ == "__main__":
    unittest.main()
