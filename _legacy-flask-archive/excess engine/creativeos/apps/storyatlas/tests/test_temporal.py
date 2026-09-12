"""Reading time expressions off the page."""

from storyatlas_engine.comprehend.temporal import extract_time, parse_number


def test_written_numbers_and_digits_are_the_same():
    assert parse_number("three") == 3
    assert parse_number("3") == 3
    assert parse_number("twenty") == 20
    assert parse_number("nonsense") is None


def test_a_stated_year_is_absolute():
    t = extract_time("Aldric was born in the year 1102.")
    assert t.kind == "absolute"
    assert t.value == 1102


def test_a_space_calendar_year_is_recognised():
    t = extract_time("The siege ended in 1147 AR.")
    assert t.kind == "absolute"
    assert t.value == 1147


def test_a_custom_era_label_is_recognised():
    t = extract_time("It happened in Cycle 44.", era_label="Cycle")
    assert t.kind == "absolute"
    assert t.value == 44


def test_later_is_a_forward_offset():
    t = extract_time("Three years later, the war began.")
    assert t.kind == "offset"
    assert t.value == 3


def test_earlier_is_a_backward_offset():
    t = extract_time("Two years earlier, the treaty was signed.")
    assert t.kind == "offset"
    assert t.value == -2


def test_a_decade_is_ten_years():
    t = extract_time("A decade later, the city fell.")
    assert t.kind == "offset"
    assert t.value == 10


def test_sub_year_units_order_without_moving_the_year():
    t = extract_time("Three days later, she returned.")
    assert t.kind == "offset"
    assert t.value == 0


def test_that_same_year_anchors_to_the_previous_event():
    t = extract_time("Mara died that same year.")
    assert t.kind == "same"


def test_an_age_is_an_offset_from_birth():
    t = extract_time("He was crowned at the age of thirty.")
    assert t.kind == "age"
    assert t.value == 30


def test_a_bare_ordering_word_is_the_weakest_signal():
    assert extract_time("Then the gates opened.").kind == "after"
    assert extract_time("Earlier, the fleet had sailed.").kind == "before"


def test_no_time_expression_returns_none():
    assert extract_time("The hall was cold and full of smoke.") is None


def test_a_stated_year_wins_but_keeps_the_relation_for_checking():
    """The clause asserts both a date and a relation. Taking the date but
    discarding the relation would hide a contradiction between them."""
    t = extract_time("Three years later, Tobin died in the year 1150.")
    assert t.kind == "absolute"
    assert t.value == 1150
    assert t.secondary is not None
    assert t.secondary.kind == "offset"
    assert t.secondary.value == 3
