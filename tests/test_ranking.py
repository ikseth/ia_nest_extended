from ianest_extended import calculate_relevance, seed_memory_types


def test_a4_dialog_and_semantic_produce_different_orderings():
    memory_types = {item.name: item for item in seed_memory_types()}
    candidates = {
        "recent_low_meaning": {
            "age_seconds": 60.0,
            "similarity": 0.0,
            "stability": 0,
            "score": 0.0,
        },
        "old_stable_match": {
            "age_seconds": 60.0 * 60.0 * 24.0 * 365.0,
            "similarity": 1.0,
            "stability": 10,
            "score": 1.0,
        },
    }

    dialog_order = sorted(
        candidates,
        key=lambda name: calculate_relevance(
            memory_types["dialog"],
            **candidates[name],
        ),
        reverse=True,
    )
    semantic_order = sorted(
        candidates,
        key=lambda name: calculate_relevance(
            memory_types["semantic"],
            **candidates[name],
        ),
        reverse=True,
    )

    assert dialog_order == ["recent_low_meaning", "old_stable_match"]
    assert semantic_order == ["old_stable_match", "recent_low_meaning"]
