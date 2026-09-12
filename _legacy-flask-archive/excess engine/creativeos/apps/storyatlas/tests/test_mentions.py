"""Recognising an entity however loosely the prose names it."""

from storyatlas_engine.comprehend.mentions import (
    MentionIndex, aliases_for, discover_names,
)


def test_a_full_name_generates_the_short_forms_a_writer_uses():
    forms = aliases_for("Chancellor Aldric Vane")
    assert "aldric" in forms
    assert "vane" in forms
    assert "aldric vane" in forms


def test_a_connective_never_becomes_an_alias():
    """Regression. "Order of the Broken Crown" once produced "of" as an alias,
    which then matched "the age **of** thirty" — misattributing the event and
    corrupting every date computed from it."""
    forms = aliases_for("Order of the Broken Crown")
    assert "of" not in forms
    assert "the" not in forms
    assert "order" in forms


def test_a_named_thing_does_not_swallow_the_place_it_is_named_after():
    """Regression. "Dawnhold Accord" claimed "Dawnhold" as a short form, so a
    treaty and the city it was named after merged into one entity.

    A person shortens either way — first name or surname. A named *thing*
    shortens by its head noun only: "the Accord", never "Dawnhold".
    """
    accord = aliases_for("Dawnhold Accord")
    assert "accord" in accord
    assert "dawnhold" not in accord

    person = aliases_for("Aldric Vane")
    assert {"aldric", "vane"} <= person


def test_the_treaty_and_the_city_stay_separate_entities():
    names = discover_names(
        "Mara Sadel died at Dawnhold in the year 1140. "
        "Kell Varo signed the Dawnhold Accord in 1155."
    )
    assert "Dawnhold Accord" in names
    assert "Dawnhold" in names


def test_short_forms_resolve_to_the_full_name():
    index = MentionIndex(["Chancellor Aldric Vane", "Mara Sadel"])
    found = index.find("Aldric turned to Mara.")
    assert [f[0] for f in found] == ["Chancellor Aldric Vane", "Mara Sadel"]


def test_mentions_do_not_overlap():
    index = MentionIndex(["Aldric Vane"])
    found = index.find("Aldric Vane stood alone.")
    assert len(found) == 1


def test_a_multiword_name_is_trusted_on_one_mention():
    names = discover_names("Aldric Vane crossed the bridge at dusk.")
    assert "Aldric Vane" in names


def test_a_name_spanning_connectives_stays_whole():
    """Regression: this used to fragment into "Order of" and "Broken Crown"."""
    names = discover_names(
        "Tobin founded the Order of the Broken Crown. "
        "The Order of the Broken Crown endured."
    )
    assert "Order of the Broken Crown" in names
    assert "Order of" not in names


def test_a_lone_capital_needs_repetition_before_it_is_believed():
    """Every sentence starts with a capital, so one is not evidence of a name."""
    names = discover_names("Winter came. Snow fell on the hall.")
    assert "Winter" not in names
    assert "Snow" not in names


def test_a_repeated_single_name_is_believed():
    names = discover_names("Aldric waited. Later, Aldric spoke. Aldric left.")
    assert "Aldric" in names


def test_the_fullest_form_absorbs_the_shorter_one():
    names = discover_names(
        "Aldric Vane entered. Aldric sat. Aldric Vane rose again."
    )
    assert "Aldric Vane" in names
    assert "Aldric" not in names
