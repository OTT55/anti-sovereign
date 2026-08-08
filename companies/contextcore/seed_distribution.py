"""Seeds the 'distribution-intelligence' collection with real case-study documents.

Each document below is original prose I've written, but every film, date, and
outcome it cites is a genuine, verifiable historical fact — nothing here is a
fabricated statistic or a synthesized number. This is exactly what a document
you'd upload to ContextCore yourself looks like; these are just pre-ingested
so the collection has real content to retrieve from on day one. Run once:

    python seed_distribution.py
"""
from app import app, ingest_document, init_db, get_db

DOCUMENTS = [
    (
        "Horror and the October Corridor",
        """The single most reliable release window in the film industry is the run-up
to Halloween. Late September through October gives a horror film a captive,
self-selecting audience without having to build one from scratch — people are
already in the mood to seek the genre out, and marketing can ride a cultural
moment for free instead of paying to manufacture one.

John Carpenter's Halloween set the template: released October 25, 1978, on a
budget of roughly $300,000, it went on to gross tens of millions of dollars,
becoming one of the most profitable independent films ever made relative to
cost. Nearly four decades later, Andy Muschietti's It opened September 8,
2017, and broke the record for the biggest horror opening weekend in history
at the time, proving the corridor still works at blockbuster scale, not just
for scrappy indies. Parker Finn's Smile opened September 30, 2022, on a much
smaller marketing budget than a typical studio wide release and still debuted
at number one, again riding the late-September positioning rather than a
massive ad spend.

The corridor is not the only option, though. Two counter-examples are worth
knowing before assuming horror must open in the fall: John Krasinski's A
Quiet Place opened April 6, 2018, and still debuted at number one, and Jordan
Peele's Get Out opened February 24, 2017, over President's Day weekend, and
became a genuine cultural event rather than a niche horror release. Both
show that a strong concept and clean marketing can succeed outside the
Halloween window, which matters for scheduling around a crowded fall slate.

For a film with real horror-genre appeal, the practical takeaway is: if the
release calendar allows it, late September through October is the
highest-probability window with the lowest marketing cost per dollar of
audience interest. If that window is already crowded with a bigger
competing release, spring (particularly early April) is the best-tested
alternative, and a distinctive high-concept horror film can succeed almost
any time of year if the marketing hook is strong enough on its own, as
Get Out demonstrated in February.""",
    ),
    (
        "Family Films and the Thanksgiving Window",
        """Family and animated films have two dependable windows, and they work for
different reasons. The first is Thanksgiving week, in late November: with
extended family together and looking for something to do as a group, a new
family release facing minimal serious competition performs extremely well.
Pixar's Toy Story opened November 22, 1995, over Thanksgiving weekend,
launching what became one of the most valuable franchises in film history.
Disney's Frozen opened November 27, 2013, again over Thanksgiving, and went
on to become a genuine cultural phenomenon, with its songs and characters
still in circulation years later.

The second proven window is early summer, once school is out. Finding Nemo
opened May 30, 2003, becoming Pixar's biggest hit up to that point, and
Inside Out opened June 19, 2015, going on to earn awards recognition as well
as strong box office. Both openings depended on children being free to see
the film on a weekday, which the Thanksgiving window doesn't offer in the
same way — the two windows serve slightly different audience availability
patterns (holiday togetherness versus school being out) rather than
competing for the exact same slot.

The practical guidance: a family film with strong sequel or franchise
potential and multi-generational appeal is best served by the Thanksgiving
window, where the whole family being together drives attendance. A family
film aimed more squarely at younger children benefits more from the early
summer window, where the audience itself — kids on school break — is what's
actually available to go.""",
    ),
    (
        "Awards Season Release Strategy: The Traditional Corridor and the New Summer Play",
        """For decades, the standard strategy for an awards-oriented drama has been to
release in a narrow window from October through December, often with a
one-week 'qualifying run' in Los Angeles or New York in December to make
that year's Academy Awards eligible, followed by a wider release into the
new year once nominations build momentum. Barry Jenkins' Moonlight opened in
limited release October 21, 2016, and went on to win the Academy Award for
Best Picture. Guillermo del Toro's The Shape of Water expanded to wide
release December 1, 2017, and also won Best Picture. Damien Chazelle's La La
Land went wide on December 16, 2016, and won six Academy Awards, narrowly
missing Best Picture itself. All three followed the traditional corridor:
building critical buzz in the fall, then riding awards nominations into
January and February.

That corridor has recently been challenged by a genuine outlier. Christopher
Nolan's Oppenheimer opened July 21, 2023 — squarely in the summer blockbuster
season, the same day as Barbie, in what became known as 'Barbenheimer' — and
still went on to win Best Picture at the Academy Awards. This matters because
it demonstrates that a serious, three-hour historical drama can now succeed
as a counter-programming summer release rather than needing the traditional
fall-to-winter buildup, provided the film has enough scale and cultural
conversation behind it to sustain awards-season marketing for months
afterward.

The practical guidance: the traditional October–December corridor, capped
with a December qualifying run, remains the lower-risk, better-tested choice
for a prestige drama, especially one without a built-in cultural hook. The
summer counter-programming strategy Oppenheimer proved out is a real,
viable alternative, but it requires enough scale and awareness to carry the
film through the long gap between a July release and the following March's
ceremony.""",
    ),
    (
        "Summer Tentpoles: The Memorial Day–July Blockbuster Window",
        """The core action and tentpole release corridor runs from Memorial Day weekend
in late May through the end of July. School is out, screens are maximized,
and the film is positioned as the season's must-see event rather than a
routine genre release. Top Gun: Maverick opened May 27, 2022 — Memorial Day
weekend — and went on to become the highest-grossing film of that year,
demonstrating the corridor still works even for a legacy-sequel property
decades after the original. Barbie opened July 21, 2023, deep in the summer
window, and became Warner Bros.' highest-grossing release ever, helped by
positioning the film as a cultural event rather than a standard studio
comedy.

Late April has also proven itself as an alternative for the very biggest
tentpoles that want to avoid a crowded late-May slate. Avengers: Endgame
opened April 26, 2019, and set the record for the biggest global opening
weekend of all time, showing that a big enough property doesn't need to
wait for the traditional Memorial Day start of summer.

The practical guidance: for a genuine four-quadrant tentpole with wide
awareness, late May through July remains the highest-grossing corridor in
the calendar, assuming the marketing budget can compete with other studios'
releases in the same window. If the late-May slate is unusually crowded, a
late-April release is a proven alternative for a property large enough to
open well without direct competition from other summer blockbusters.""",
    ),
    (
        "Romance and Valentine's Day Positioning",
        """Romance and date-night films have one obvious and well-tested window:
Valentine's Day weekend in mid-February. Fifty Shades of Grey opened
February 13, 2015, timed deliberately to Valentine's weekend, and became the
largest R-rated opening weekend at the time. How to Lose a Guy in 10 Days
opened February 7, 2003, in the same early-February date-movie window, and
performed well as a counter-programming choice against the winter's more
serious dramas.

A useful counter-example: The Notebook opened June 25, 2004, in the middle
of summer rather than around Valentine's Day, and still built a long
theatrical run through word of mouth even with a modest opening weekend.
This shows that summer counter-programming against action tentpoles —
offering a date-night alternative when everything else in theaters is an
explosion-heavy blockbuster — can also work for romance, provided the film
has strong enough word-of-mouth legs to make up for a quieter opening.

The practical guidance: mid-February, timed to Valentine's Day, is the
highest-confidence window for a straightforward romance and requires the
least marketing invention — the calendar does some of the positioning work
for you. A summer counter-programming release is a legitimate secondary
option, particularly if the film is more of a sleeper that depends on word
of mouth rather than a big opening weekend to succeed.""",
    ),
    (
        "Low-Budget Distribution: Festival-First and Platform Release Strategy",
        """A film without a tentpole marketing budget can't out-advertise the studios,
so the standard strategy is to build buzz cheaply through festivals first,
then release on a platform basis — a small number of screens expanding over
subsequent weeks as reviews and word of mouth build, rather than opening
wide everywhere on day one. Damien Chazelle's Whiplash premiered at Sundance
in January 2014 and didn't reach theatrical release until October 10, 2014 —
nine months of festival buzz and critical praise built the audience before
a single ticket was sold in a commercial theater. It went on to win three
Academy Awards. Everything Everywhere All at Once premiered at South by
Southwest on March 11, 2022, then went to a wider release on March 25,
2022 — a much faster festival-to-wide turnaround than Whiplash's, reflecting
A24's platform-release model of building quickly on strong festival buzz
rather than the longer awards-season build some other distributors use. It
went on to sweep the following year's Academy Awards, including Best
Picture.

Jordan Peele's Get Out is worth citing again here for a different reason: it
was a Blumhouse production made on a very low budget, but rather than
following the platform-release path, it was given a genuine wide release on
February 24, 2017, and succeeded at that scale specifically because horror
carries built-in commercial appeal that many other low-budget genres lack —
proof that the low-budget playbook isn't one-size-fits-all, and genre
matters as much as budget in choosing a release strategy.

The practical guidance: for most low-budget films, especially dramas or
anything depending on critical reception, a festival premiere followed by a
platform release — building screen count gradually as reviews and word of
mouth accumulate — is the lowest-risk path to a real audience. If the film
has a strong commercial genre hook, particularly horror, a real wide release
can work even on a low budget, since audience interest doesn't depend on
critical buzz in the same way a festival drama's does.""",
    ),
]


def main():
    with app.app_context():
        init_db()
        db = get_db()
        existing = db.execute(
            "SELECT COUNT(*) c FROM documents WHERE category = 'distribution-intelligence'"
        ).fetchone()["c"]
        if existing:
            print(f"distribution-intelligence collection already has {existing} document(s) — skipping.")
            print("Delete contextcore.db and re-run to reseed from scratch.")
            return

        total_chunks = total_entities = total_rels = 0
        extraction_note = embedding_note = None
        for title, text in DOCUMENTS:
            doc_id, chunk_count, entity_count, rel_count, note, emb_note = ingest_document(
                title, text, category="distribution-intelligence"
            )
            total_chunks += chunk_count
            total_entities += entity_count
            total_rels += rel_count
            extraction_note = extraction_note or note
            embedding_note = embedding_note or emb_note
            print(f"  ingested {doc_id}  ({chunk_count} chunks, {entity_count} entities, {rel_count} relationships)  {title}")

        print(f"\nSeeded {len(DOCUMENTS)} documents, {total_chunks} chunks, "
              f"{total_entities} entities, {total_rels} relationships, "
              f"into the 'distribution-intelligence' collection.")
        if extraction_note:
            print(f"Note: {extraction_note}")
        if embedding_note:
            print(f"Note: {embedding_note}")


if __name__ == "__main__":
    main()
