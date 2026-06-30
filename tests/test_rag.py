"""Tests for the offline RAG evidence layer."""

from epl_cds.extraction.rag import (
    VectorStore,
    answer_question,
    chunk_text,
    cosine,
    hashing_embed_fn,
)

CORPUS = [
    ("The diagnostic crown-rump length cutoff with no cardiac activity is 7 mm.", "crl.md"),
    ("A mean sac diameter of 25 mm or more with no embryo is diagnostic.", "msd.md"),
    ("Specificity is prioritized because a false positive can end a viable pregnancy.", "why.md"),
]


def _store():
    store = VectorStore(hashing_embed_fn())
    for text, source in CORPUS:
        store.add_text(text, source)
    return store


def test_chunking_splits_paragraphs():
    text = "Para one is here.\n\nPara two is also here."
    chunks = chunk_text(text, "x", max_chars=20)
    assert len(chunks) == 2
    assert all(c.source == "x" for c in chunks)


def test_hashing_embedder_is_deterministic_and_lexical():
    embed = hashing_embed_fn()
    assert embed("crown rump length") == embed("crown rump length")
    # Overlapping text is more similar than unrelated text.
    a = embed("crown rump length cutoff")
    related = embed("the crown rump length is measured")
    unrelated = embed("mean sac diameter embryo")
    assert cosine(a, related) > cosine(a, unrelated)


def test_retrieval_finds_relevant_passage():
    store = _store()
    hits = store.query("what is the CRL threshold for no heartbeat?", k=1)
    assert hits
    assert hits[0].chunk.source == "crl.md"


def test_answer_without_llm_returns_citations_only():
    store = _store()
    ans = answer_question("why prioritize specificity?", store, llm_fn=None)
    assert ans.synthesized is False
    assert ans.answer == ""
    assert ans.citations  # retrieval still works


def test_answer_with_llm_is_grounded_on_passages():
    store = _store()
    captured = {}

    def fake_llm(prompt: str) -> str:
        captured["prompt"] = prompt
        return "CRL >= 7 mm with no heartbeat [1]."

    ans = answer_question("CRL threshold?", store, llm_fn=fake_llm)
    assert ans.synthesized is True
    assert "7 mm" in ans.answer
    # The prompt must contain the retrieved passages (grounding).
    assert "crown-rump length" in captured["prompt"].lower()
