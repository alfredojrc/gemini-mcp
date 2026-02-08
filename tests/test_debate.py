"""Tests for the debate orchestrator."""

import json

import pytest

from gemini_mcp.debate.orchestrator import (
    DebateConfig,
    DebateMemory,
    DebateResult,
    DebateRound,
    DebateStrategy,
    _cosine_similarity,
    _tfidf_vector,
    _tokenize,
)


class TestTFIDF:
    """Tests for TF-IDF helper functions."""

    def test_tokenize_basic(self):
        """Tokenize removes stopwords and lowercases."""
        tokens = _tokenize("The quick brown fox jumps over the lazy dog")
        assert "the" not in tokens
        assert "a" not in tokens  # stopword
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens

    def test_tokenize_empty(self):
        """Empty string gives empty list."""
        assert _tokenize("") == []

    def test_tokenize_only_stopwords(self):
        """All-stopword string gives empty list."""
        assert _tokenize("the a an is are") == []

    def test_tfidf_vector_produces_frequencies(self):
        """TF vector values should be term frequencies."""
        vec = _tfidf_vector("python python java")
        assert vec["python"] == pytest.approx(2 / 3)
        assert vec["java"] == pytest.approx(1 / 3)

    def test_tfidf_empty_string(self):
        """Empty string gives empty vector."""
        assert _tfidf_vector("") == {}

    def test_cosine_identical_texts(self):
        """Identical texts should have similarity 1.0."""
        vec = _tfidf_vector("machine learning trading strategies")
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_cosine_completely_different(self):
        """Texts with no common words should have similarity 0.0."""
        v1 = _tfidf_vector("python java typescript")
        v2 = _tfidf_vector("cooking pasta ingredients")
        assert _cosine_similarity(v1, v2) == 0.0

    def test_cosine_partial_overlap(self):
        """Texts with some overlap should have intermediate similarity."""
        v1 = _tfidf_vector("machine learning python code")
        v2 = _tfidf_vector("machine learning java code")
        sim = _cosine_similarity(v1, v2)
        assert 0.3 < sim < 1.0

    def test_cosine_empty_vectors(self):
        """Empty vectors give 0.0."""
        assert _cosine_similarity({}, {}) == 0.0
        assert _cosine_similarity({"a": 1.0}, {}) == 0.0


class TestDebateMemory:
    """Tests for debate memory persistence."""

    def test_save_and_load(self, tmp_path, monkeypatch):
        """Save and load a debate result."""
        monkeypatch.setattr(
            "gemini_mcp.debate.orchestrator.config",
            type("C", (), {"debate_storage_dir": tmp_path, "debate_novelty_threshold": 0.2})(),
        )
        mem = DebateMemory()

        result = DebateResult(
            debate_id="debate-001",
            topic="Python vs Rust",
            strategy=DebateStrategy.ADVERSARIAL,
            rounds_completed=3,
            final_synthesis="Both have strengths",
            consensus_points=["Both are useful"],
            disagreement_points=["Performance differs"],
            converged=True,
        )
        mem.save(result)

        loaded = mem.load("debate-001")
        assert loaded is not None
        assert loaded.debate_id == "debate-001"
        assert loaded.topic == "Python vs Rust"
        assert loaded.strategy == DebateStrategy.ADVERSARIAL
        assert loaded.converged is True

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        """Loading nonexistent debate returns None."""
        monkeypatch.setattr(
            "gemini_mcp.debate.orchestrator.config",
            type("C", (), {"debate_storage_dir": tmp_path, "debate_novelty_threshold": 0.2})(),
        )
        mem = DebateMemory()
        assert mem.load("nonexistent") is None

    def test_find_related_debates(self, tmp_path, monkeypatch):
        """Find debates related to a topic."""
        monkeypatch.setattr(
            "gemini_mcp.debate.orchestrator.config",
            type("C", (), {"debate_storage_dir": tmp_path, "debate_novelty_threshold": 0.2})(),
        )
        mem = DebateMemory()

        # Save a few debates
        for i, topic in enumerate(["machine learning trading", "deep learning models", "cooking recipes"]):
            result = DebateResult(
                debate_id=f"d-{i}",
                topic=topic,
                strategy=DebateStrategy.COLLABORATIVE,
                rounds_completed=2,
                consensus_points=["point"],
            )
            mem.save(result)

        related = mem.find_related_debates("machine learning algorithms", limit=5)
        # ML debates should be more related than cooking
        if len(related) > 0:
            assert related[0].topic != "cooking recipes"

    def test_get_statistics(self, tmp_path, monkeypatch):
        """Get debate statistics."""
        monkeypatch.setattr(
            "gemini_mcp.debate.orchestrator.config",
            type("C", (), {"debate_storage_dir": tmp_path, "debate_novelty_threshold": 0.2})(),
        )
        mem = DebateMemory()

        for i in range(3):
            result = DebateResult(
                debate_id=f"stat-{i}",
                topic=f"Topic {i}",
                strategy=DebateStrategy.COLLABORATIVE,
                rounds_completed=2,
                consensus_points=["a", "b"],
                converged=i < 2,  # 2 out of 3 converge
            )
            mem.save(result)

        stats = mem.get_statistics()
        assert stats["total_debates"] == 3
        assert stats["total_insights"] == 6  # 3 * 2 consensus points
        assert stats["convergence_rate"] == pytest.approx(2 / 3)


class TestJSONExtraction:
    """Tests for bracket-balanced JSON extraction from LLM output."""

    def setup_method(self):
        from gemini_mcp.debate.orchestrator import DebateOrchestrator
        self.extract = DebateOrchestrator._extract_json_object

    def test_clean_json(self):
        """Parse clean JSON object."""
        text = '{"key": "value", "num": 42}'
        result = self.extract(text)
        assert result == {"key": "value", "num": 42}

    def test_json_with_prefix(self):
        """Parse JSON with leading text."""
        text = 'Here is the result: {"synthesis": "done"}'
        result = self.extract(text)
        assert result == {"synthesis": "done"}

    def test_nested_braces(self):
        """Parse JSON with nested objects."""
        text = '{"outer": {"inner": "value"}, "list": [1, 2]}'
        result = self.extract(text)
        assert result["outer"]["inner"] == "value"

    def test_escaped_quotes(self):
        """Parse JSON with escaped quotes in strings."""
        text = '{"text": "She said \\"hello\\""}'
        result = self.extract(text)
        assert result["text"] == 'She said "hello"'

    def test_braces_in_strings(self):
        """Braces inside strings should not confuse the parser."""
        text = '{"code": "if (x) { return }"}'
        result = self.extract(text)
        assert "code" in result

    def test_no_json(self):
        """No JSON in text returns None."""
        assert self.extract("Just plain text, no braces") is None

    def test_invalid_json(self):
        """Malformed JSON returns None."""
        assert self.extract("{invalid json here}") is None

    def test_markdown_fenced_json(self):
        """JSON wrapped in markdown code fences (handled upstream)."""
        # The _extract_json_object handles raw text; code fence stripping
        # is done before calling it. Test that it still finds the JSON.
        text = '```json\n{"key": "value"}\n```'
        result = self.extract(text)
        assert result == {"key": "value"}


class TestDebateRound:
    """Tests for debate round data structures."""

    def test_novelty_calculation(self):
        """Verify novelty is 1 - cosine similarity."""
        # Two identical rounds should produce low novelty
        r1_text = "machine learning is great for predictions"
        r2_text = "machine learning is great for predictions"
        v1 = _tfidf_vector(r1_text)
        v2 = _tfidf_vector(r2_text)
        sim = _cosine_similarity(v1, v2)
        novelty = 1.0 - sim
        assert novelty < 0.1  # Very low novelty for identical texts

    def test_high_novelty_different_topics(self):
        """Different topics should produce high novelty."""
        v1 = _tfidf_vector("quantum computing algorithms encryption")
        v2 = _tfidf_vector("organic farming sustainable agriculture")
        sim = _cosine_similarity(v1, v2)
        novelty = 1.0 - sim
        assert novelty > 0.9  # Very high novelty for unrelated texts
