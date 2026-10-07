import pandas as pd
import pytest

from rag_pipeline.evaluate import (apply_policy, is_abstain, is_correct, is_correct_lenient, metrics, pareto, score,
                                   tune, wide)


@pytest.mark.parametrize("answer,answers,expected", [
    ("Politician and soldier.", ["politician", "pol"], True),
    ("The Beatles", ["Beatles"], True),
    ("Christopher Nolan.", ["Chris Nolan"], False),
    ("I don't know.", ["paris"], False),
    ("anything", [""], False),  # empty alias must not match everything
])
def test_is_correct(answer, answers, expected):
    assert is_correct(answer, answers) is expected


def test_is_correct_folds_accents():
    assert is_correct("Sebastian Gutiérrez.", ["Sebastian Gutierrez"])


@pytest.mark.parametrize("answer,answers,expected", [
    ("Catholic.", ["Catholic Church"], True),           # partial answer
    ("Jutra.", ["Claude Jutra"], True),                 # surname only
    ("Noir crime film.", ["film noir"], True),          # reordered words
    ("Swein Forkbeard.", ["Sweyn Forkbeard"], True),    # spelling variant
    ("Slasher film.", ["horror film"], False),          # different genre
    ("Film.", ["horror film"], False),                  # too vague
    ("Anglican Church", ["Catholic Church"], False),
    ("Oklahoma.", ["Muskogee County, Oklahoma"], False),  # qualifier after the comma
    ("Melbourne.", ["Melbourne, Victoria"], True),
    ("I don't know.", ["I Know"], False),          # abstentions never match
    ("Stephen Mazur.", ["Steven Shainberg"], False),
])
def test_is_correct_lenient(answer, answers, expected):
    assert is_correct_lenient(answer, answers) is expected


def test_score_keeps_strict_alongside_lenient():
    df = score(pd.DataFrame({"answer": ["Catholic.", "Paris"], "possible_answers": [["Catholic Church"], ["paris"]]}))
    assert df["correct"].tolist() == [True, True]
    assert df["correct_strict"].tolist() == [False, True]


def test_is_abstain():
    assert is_abstain("I don’t know.") and is_abstain("I do not know")
    assert not is_abstain("Paris")


def _gen():
    # q1 popular+confident+right closed-book, q2 rare & wrong closed-book, q3 popular but unsure & wrong
    rows = []
    for qid, s_pop, closed, conf, rag in [(1, 10**5, "Paris", 0.95, "Paris"),
                                          (2, 5, "lawyer", 0.9, "politician"),
                                          (3, 10**5, "I don't know", 0.3, "Nolan")]:
        ans = {1: ["paris"], 2: ["politician"], 3: ["nolan"]}[qid]
        for with_ctx, a, c in [(False, closed, conf), (True, rag, 0.99)]:
            rows.append(dict(question_id=qid, with_context=with_ctx, answer=a, confidence=c, latency_ms=100.0,
                             question=f"q{qid}", prop="x", s_pop=s_pop, possible_answers=ans))
    return wide(score(pd.DataFrame(rows)))


def test_policies():
    w = _gen()
    never, always = metrics(apply_policy(w, "never")), metrics(apply_policy(w, "always"))
    assert never["accuracy"] == pytest.approx(1 / 3) and never["hallucination_rate"] == pytest.approx(1 / 3)
    assert never["abstain_rate"] == pytest.approx(1 / 3)
    assert always["accuracy"] == 1.0 and always["retrieval_rate"] == 1.0

    p = apply_policy(w, "adaptive", pop_t=100, conf_t=0.5)
    assert p["retrieved"].tolist() == [False, True, True]
    assert p["latency_ms"].tolist() == [100, 100, 200]  # q3 paid for the closed-book pass too
    assert metrics(p)["accuracy"] == 1.0


def test_tune_prefers_fewer_retrievals_at_equal_accuracy():
    grid, best = tune(_gen())
    best_row = grid.query("pop_threshold == @best['pop_threshold'] and conf_threshold == @best['conf_threshold']")
    assert best_row["accuracy"].iloc[0] == 1.0
    assert best_row["retrieval_rate"].iloc[0] == pytest.approx(2 / 3)


def test_tune_trades_small_accuracy_loss_for_fewer_retrievals():
    grid, best = tune(_gen(), tolerance=0.34)  # one of three questions may be given up
    best_row = grid.query("pop_threshold == @best['pop_threshold'] and conf_threshold == @best['conf_threshold']")
    assert best_row["accuracy"].iloc[0] == pytest.approx(2 / 3)
    assert best_row["retrieval_rate"].iloc[0] == pytest.approx(1 / 3)


def test_pareto_keeps_only_undominated_settings():
    grid = pd.DataFrame({"retrieval_rate": [0.0, 0.2, 0.2, 0.5, 0.9],
                         "accuracy":       [0.2, 0.5, 0.4, 0.5, 0.6]})
    front = pareto(grid)
    assert front[["retrieval_rate", "accuracy"]].values.tolist() == [[0.0, 0.2], [0.2, 0.5], [0.9, 0.6]]
