"""Text normalisation and tokenisation shared by the parser and the vectoriser.

Kept dependency-free on purpose: no NLTK, no spaCy. Everything here is a few
lines of Python I can walk through line by line, and it has no model download
step that could fail on a fresh machine.
"""

import re

# Words that appear in almost every job description and therefore carry no
# discriminating signal. Removing them stops "the", "and", "work" from
# inflating the cosine similarity between unrelated postings.
STOPWORDS: frozenset[str] = frozenset(
    """
    a an the and or but if then than that this these those of in on at to for
    with without from by as is are was were be been being am do does did doing
    have has had having i me my we our you your he she it its they them their
    will would shall should can could may might must not no nor so such very
    about into over under again further once here there when where why how all
    any both each few more most other some only own same too s t just don now
    want wants wanted looking look seek seeking need needs role roles job jobs
    position positions opportunity opportunities work working works company
    companies team teams join joining candidate candidates ideal great good
    strong excellent experience experienced years year plus etc using use used
    who whom which what
    """.split()
)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]*")


def normalize(text: str) -> str:
    """Lowercase and squash whitespace so alias matching is predictable."""
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    """Split text into lowercase tokens.

    The token pattern keeps `+`, `#`, `.`, `/` and `-` inside a word so that
    `c++`, `c#`, `node.js`, `ci/cd` and `scikit-learn` survive as single tokens
    instead of being shredded into meaningless fragments.
    """
    tokens = _TOKEN_RE.findall(normalize(text))
    if keep_stopwords:
        return tokens
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def bigrams(tokens: list[str]) -> list[str]:
    """Adjacent token pairs, so phrases like 'machine learning' are one feature."""
    return [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]


def feature_terms(text: str) -> list[str]:
    """The full term list fed to the vectoriser: unigrams plus bigrams."""
    tokens = tokenize(text)
    return tokens + bigrams(tokens)
