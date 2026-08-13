"""A small TF-IDF vectoriser and cosine similarity, written from scratch.

Why not scikit-learn? Three reasons, and I am happy to defend all three:

1. It is ~60 lines. Pulling in a 30 MB dependency (plus a pinned NumPy/SciPy
   build that breaks on some Windows setups) to do 60 lines of arithmetic is a
   bad trade for this project.
2. I can explain every number the matcher produces. In an interview about an
   AI feature, "sklearn returned 0.62" is a worse answer than being able to
   point at the exact IDF term that caused it.
3. The corpus is small enough (tens to low hundreds of job postings) that the
   O(n) pass here is instant. If it were millions of documents I would reach
   for a real vector database and precomputed embeddings instead.

Formulae used
-------------
    tf(t, d)  = count(t in d) / len(d)
    idf(t)    = ln((1 + N) / (1 + df(t))) + 1        (smoothed, never zero)
    tfidf     = tf * idf, then L2-normalised per document
    cosine    = dot product of two L2-normalised vectors
"""

import math
from collections import Counter

from app.matching.text import feature_terms


class TfidfIndex:
    """An in-memory TF-IDF index built fresh per matching request.

    Rebuilding per request is intentional: job postings change while the app is
    running and the corpus is tiny, so a stale cache would cost more in
    correctness than the rebuild costs in time.
    """

    def __init__(self, documents: list[str]) -> None:
        self.term_lists: list[list[str]] = [feature_terms(doc) for doc in documents]
        self.n_docs: int = len(self.term_lists)

        # Document frequency: in how many documents does each term appear?
        doc_freq: Counter[str] = Counter()
        for terms in self.term_lists:
            doc_freq.update(set(terms))
        self.doc_freq = doc_freq

        # Smoothed IDF. The +1s keep the value finite for terms that appear in
        # every document (or in none, for an unseen query term).
        self.idf: dict[str, float] = {
            term: math.log((1 + self.n_docs) / (1 + freq)) + 1.0
            for term, freq in doc_freq.items()
        }
        self.default_idf: float = math.log(1 + self.n_docs) + 1.0

        self.vectors: list[dict[str, float]] = [self._vectorize(terms) for terms in self.term_lists]

    def _vectorize(self, terms: list[str]) -> dict[str, float]:
        """Turn a term list into an L2-normalised sparse TF-IDF vector."""
        if not terms:
            return {}

        counts = Counter(terms)
        length = len(terms)
        vector = {
            term: (count / length) * self.idf.get(term, self.default_idf)
            for term, count in counts.items()
        }

        norm = math.sqrt(sum(weight * weight for weight in vector.values()))
        if norm == 0:
            return {}
        return {term: weight / norm for term, weight in vector.items()}

    def vectorize_query(self, query: str) -> dict[str, float]:
        """Vectorise a query using the IDF weights learned from the corpus."""
        return self._vectorize(feature_terms(query))

    def similarity(self, query_vector: dict[str, float], doc_index: int) -> float:
        """Cosine similarity between a query vector and one indexed document."""
        doc_vector = self.vectors[doc_index]
        if not query_vector or not doc_vector:
            return 0.0
        # Iterate the smaller dict - the query is almost always shorter.
        smaller, larger = (
            (query_vector, doc_vector)
            if len(query_vector) <= len(doc_vector)
            else (doc_vector, query_vector)
        )
        return sum(weight * larger.get(term, 0.0) for term, weight in smaller.items())

    def top_overlapping_terms(self, query_vector: dict[str, float], doc_index: int, k: int = 5) -> list[str]:
        """The terms contributing most to a given similarity score.

        This is what lets the UI say *why* a job scored well rather than just
        showing a number.
        """
        doc_vector = self.vectors[doc_index]
        contributions = [
            (term, weight * doc_vector.get(term, 0.0))
            for term, weight in query_vector.items()
            if term in doc_vector
        ]
        contributions.sort(key=lambda pair: pair[1], reverse=True)
        return [term.replace("_", " ") for term, score in contributions[:k] if score > 0]
