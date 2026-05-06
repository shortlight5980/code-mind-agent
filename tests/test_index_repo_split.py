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
        "utils": types.ModuleType("utils"),
        "utils.logger": types.ModuleType("utils.logger"),
        "utils.config": types.ModuleType("utils.config"),
    }
    stubs["langchain_community.document_loaders"].TextLoader = object
    stubs["langchain_community.embeddings"].DashScopeEmbeddings = object
    stubs["langchain_text_splitters"].RecursiveCharacterTextSplitter = object
    stubs["langchain_chroma"].Chroma = object
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


if __name__ == "__main__":
    unittest.main()
