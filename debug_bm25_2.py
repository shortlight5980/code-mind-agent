import sys
import math
from collections import Counter

# 检查 rank_bm25 是否可用
try:
    from rank_bm25 import BM25Okapi as RankBM25Okapi
    print("OK rank_bm25 is available")
except ImportError:
    print("NO rank_bm25 is NOT available")
    RankBM25Okapi = None

# 我们的 SimpleBM25Okapi 实现
class SimpleBM25Okapi:
    def __init__(self, corpus, k1=1.5, b=0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.doc_freqs = [Counter(doc) for doc in corpus]
        self.doc_len = [len(doc) for doc in corpus]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        self.idf = self._calculate_idf()

    def _calculate_idf(self):
        document_count = len(self.corpus)
        frequencies = Counter()
        for doc in self.corpus:
            frequencies.update(set(doc))
        return {
            token: math.log(1 + (document_count - freq + 0.5) / (freq + 0.5))
            for token, freq in frequencies.items()
        }

    def get_scores(self, query_tokens):
        scores = []
        for idx, freqs in enumerate(self.doc_freqs):
            score = 0.0
            doc_len = self.doc_len[idx]
            for token in query_tokens:
                token_freq = freqs.get(token, 0)
                if token_freq == 0:
                    continue
                denominator = token_freq + self.k1 * (
                    1 - self.b + self.b * doc_len / (self.avgdl or 1)
                )
                idf_val = self.idf.get(token, 0.0)
                token_score = idf_val * (token_freq * (self.k1 + 1) / denominator)
                score += token_score
                print(f"  token={token}, freq={token_freq}, idf={idf_val:.4f}, token_score={token_score:.4f}")
            scores.append(score)
            print(f"doc[{idx}] score = {score:.4f}")
        return scores

# 测试数据
corpus = [['alpha', 'beta', 'beta'], ['gamma', 'delta']]
query = ['beta']

print("\n=== Testing SimpleBM25Okapi ===")
simple_bm25 = SimpleBM25Okapi(corpus)
print("IDF:", simple_bm25.idf)
scores = simple_bm25.get_scores(query)
print("Scores:", scores)

if RankBM25Okapi is not None:
    print("\n=== Testing RankBM25Okapi ===")
    rank_bm25 = RankBM25Okapi(corpus)
    scores2 = rank_bm25.get_scores(query)
    print("Scores:", scores2)
