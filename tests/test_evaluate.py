import pytest

from evaluate import results_match


@pytest.mark.parametrize(
    "gold, predicted",
    [
        ([(1,), (2,)], [(2,), (1,)]),  # row order does not matter
        ([("checkout",)], [("checkout", 3)]),  # extra columns are fine
        ([(2866.6666666,)], [(2866.67,)]),  # model rounded to 2 places
        ([(79.9999999254942,)], [(80,)]),  # float maths vs integer
        ([], []),  # both empty
    ],
)
def test_same_answer_matches(gold, predicted):
    assert results_match(gold, predicted)


@pytest.mark.parametrize(
    "gold, predicted",
    [
        ([(8750.0,)], [(15900.0,)]),  # wrong value (forgot the team filter)
        ([("payments-api",)], [("payments-api",), ("auth",)]),  # extra rows
        ([("a", 1), ("b", 2)], [("a", 1)]),  # missing rows
        ([("checkout", 3)], [("checkout",)]),  # missing a column
        ([(1,)], None),  # refused or failed
    ],
)
def test_different_answer_does_not_match(gold, predicted):
    assert not results_match(gold, predicted)
