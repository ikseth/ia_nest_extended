from types import SimpleNamespace

from ianest_extended.knowledge import knowledge_status, suggest_domains


class WorkflowStore:
    def __init__(self):
        self.proposals = []

    def confirmed_corpus_counts(self, domains):
        return {domain: int(domain == "linux") for domain in domains}

    def sample_corpus(self, corpus_name, max_chars):
        assert corpus_name == "manual"
        return "contenido linux y python"[:max_chars]

    def propose_domain(self, corpus_name, domain, confidence):
        self.proposals.append((corpus_name, domain, confidence))
        return domain != "codigo"


class WorkflowCore:
    def list_domains(self):
        return ("general", "linux", "codigo", "datos")

    def domain_route(self, prompt, identity):
        assert prompt == "contenido linux y python"
        assert identity.service == "knowledge"
        return SimpleNamespace(
            domain="linux",
            confidence=0.91,
            alternatives=(
                {"domain": "codigo", "confidence": 0.72},
                {"domain": "datos", "confidence": 0.4},
                {"domain": "unknown", "confidence": 0.99},
            ),
        )


def test_status_reports_gaps_and_excludes_general():
    statuses = knowledge_status(store=WorkflowStore(), core=WorkflowCore())

    assert [(item.domain, item.confirmed_corpora) for item in statuses] == [
        ("linux", 1),
        ("codigo", 0),
        ("datos", 0),
    ]


def test_suggest_applies_threshold_and_keeps_store_protection_result():
    store = WorkflowStore()

    suggestions = suggest_domains(
        store=store,
        core=WorkflowCore(),
        corpus_name="manual",
        min_confidence=0.6,
        sample_chars=2000,
    )

    assert [(item.domain, item.confidence, item.stored) for item in suggestions] == [
        ("linux", 0.91, True),
        ("codigo", 0.72, False),
    ]
    assert store.proposals == [
        ("manual", "linux", 0.91),
        ("manual", "codigo", 0.72),
    ]
