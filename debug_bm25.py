from utils.bm25_index import BM25Index, tokenize

print("=== Testing tokenize ===")
print("tokenize('alpha beta beta') =", tokenize("alpha beta beta"))
print("tokenize('beta') =", tokenize("beta"))
print()

print("=== Testing BM25Index ===")
index = BM25Index()
index.fit(
    ["alpha beta beta", "gamma delta"],
    [{"source": "a.txt", "type": "doc"}, {"source": "b.txt", "type": "doc"}],
)
print("After fit: index.documents =", index.documents)

results = index.search("beta", k=1, filter_type="doc")
print("Search 'beta':", results)
print(f"len(results) = {len(results)}")
if results:
    print(f"First result: {results[0]}")

print("\n=== Testing with delete ===")
index2 = BM25Index()
index2.fit(
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

removed = index2.delete_by_sources(["src/delete_me.py", "docs/delete_me.md"])
print(f"Removed {removed} chunks")

remaining = index2.search("keep_me survivor", k=10, filter_type="code")
print(f"len(remaining) = {len(remaining)}, remaining = {remaining}")
