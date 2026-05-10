import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


class BM25IndexTests(unittest.TestCase):
    def test_search_filters_by_metadata_type_and_ranks_keyword_matches(self):
        from utils.bm25_index import BM25Index

        index = BM25Index()
        index.fit(
            [
                "def parse_user_id(value): return int(value)",
                "deployment guide for docker compose",
                "class UserRepository: def find_user(self): pass",
            ],
            [
                {"source": "repo/users.py", "type": "code"},
                {"source": "docs/deploy.md", "type": "doc"},
                {"source": "repo/repository.py", "type": "code"},
            ],
        )

        results = index.search("parse_user_id user", k=5, filter_type="code")

        self.assertEqual(2, len(results))
        self.assertEqual("repo/users.py", results[0][1]["source"])
        self.assertTrue(all(metadata["type"] == "code" for _, metadata, _ in results))

    def test_save_and_load_preserves_search_results(self):
        from utils.bm25_index import BM25Index

        index = BM25Index()
        index.fit(
            ["alpha beta beta", "gamma delta"],
            [{"source": "a.txt", "type": "doc"}, {"source": "b.txt", "type": "doc"}],
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bm25.pkl"
            index.save(str(path))

            loaded = BM25Index.load(str(path))
            results = loaded.search("beta", k=1, filter_type="doc")

        self.assertEqual("a.txt", results[0][1]["source"])

    def test_delete_by_sources_removes_matching_chunks_and_rebuilds_index(self):
        from utils.bm25_index import BM25Index

        index = BM25Index()
        index.fit(
            [
                "def delete_me(): return 'target'",
                "def keep_me(): return 'survivor'",
                "target docs",
            ],
            [
                {"source": "src/delete_me.py", "type": "code"},
                {"source": "src/keep_me.py", "type": "code"},
                {"source": "docs/delete_me.md", "type": "doc"},
            ],
        )

        removed = index.delete_by_sources(["src/delete_me.py", "docs/delete_me.md"])

        self.assertEqual(2, removed)
        deleted_sources = {
            metadata["source"]
            for _, metadata, _ in index.search("delete_me target", k=10)
        }
        self.assertFalse({"src/delete_me.py", "docs/delete_me.md"} & deleted_sources)
        remaining = index.search("keep_me survivor", k=10, filter_type="code")
        self.assertEqual(1, len(remaining))
        self.assertEqual("src/keep_me.py", remaining[0][1]["source"])


class FusionTests(unittest.TestCase):
    def test_rrf_fuse_deduplicates_by_source_and_content_hash(self):
        from utils.fusion import rrf_fuse

        vec_a = {"content": "same content", "metadata": {"source": "a.py"}}
        bm25_a = {"content": "same content", "metadata": {"source": "a.py"}}
        bm25_b = {"content": "other content", "metadata": {"source": "b.py"}}

        fused = rrf_fuse([[vec_a], [bm25_b, bm25_a]], rrf_k=60)

        self.assertEqual(2, len(fused))
        self.assertEqual("same content", fused[0]["content"])
        self.assertGreater(fused[0]["score"], fused[1]["score"])


class RetrievalHelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_hybrid_retrieval_fuses_vector_and_bm25_by_type(self):
        from agent.tools.retrieve_and_summarize import _retrieve_documents

        class FakeVectorDb:
            async def asimilarity_search(self, query, k, filter):
                if filter["type"] == "doc":
                    return [SimpleNamespace(page_content="vector doc", metadata={"source": "doc.md", "type": "doc"})]
                return [SimpleNamespace(page_content="shared code", metadata={"source": "app.py", "type": "code"})]

        class FakeBM25:
            def search(self, query, k, filter_type=None):
                if filter_type == "doc":
                    return [("bm25 doc", {"source": "bm25.md", "type": "doc"}, 3.0)]
                return [("shared code", {"source": "app.py", "type": "code"}, 9.0)]

        service_manager = SimpleNamespace(
            vectordb=FakeVectorDb(),
            bm25_index=FakeBM25(),
            retrieval_k={"docs": 2, "codes": 2},
            bm25_retrieval_k={"docs": 2, "codes": 2},
            retrieval_config={"mode": "hybrid", "rrf_k": 60, "identifier_boost": 0.0},
        )

        docs = await _retrieve_documents("shared code", service_manager)

        self.assertEqual(3, len(docs))
        self.assertEqual(["doc", "doc", "code"], [doc.metadata["type"] for doc in docs])
        self.assertEqual(1, sum(1 for doc in docs if doc.page_content == "shared code"))


if __name__ == "__main__":
    unittest.main()
