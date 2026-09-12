"""Phase 9 — the Domain Engine: the same pipeline, specialised.

The constitution's framing: *"The core engine never changes. Only ontology,
extraction rules, terminology, reasoning templates, validation rules."*

A legal corpus and a film corpus need different things extracted, and the
mistake would be to write a legal pipeline and a film pipeline. Everything that
differs between them is **data**: which entity types matter, which terms are
worth normalising, which fields a document of this kind ought to have.

So a domain is a small declarative pack, and the engine reads it. Adding a new
industry is writing a pack, not writing code — which is the test of whether the
specialisation is real or just branching in disguise.

The `general` pack is deliberately thin. A domain that claims to know
everything about every corpus knows nothing useful about any of them.
"""


class DomainPack:
    """One industry's vocabulary and expectations."""

    __slots__ = ("name", "entity_types", "terminology", "expected_fields",
                 "extraction_hint", "functional_predicates")

    def __init__(self, name, entity_types=(), terminology=None, expected_fields=(),
                 extraction_hint="", functional_predicates=()):
        self.name = name
        self.entity_types = tuple(entity_types)
        #: alias -> canonical term. The domain's own synonym table, so
        #: "plaintiff" and "claimant" stop being two different concepts.
        self.terminology = dict(terminology or {})
        #: What a document of this kind ought to record. Absence is a finding —
        #: a contract with no parties named is incomplete, and only the domain
        #: knows that.
        self.expected_fields = tuple(expected_fields)
        self.extraction_hint = extraction_hint
        self.functional_predicates = tuple(functional_predicates)

    def normalize_term(self, term):
        key = (term or "").strip().lower()
        return self.terminology.get(key, term)

    def knows_type(self, entity_type):
        return not self.entity_types or (entity_type or "").lower() in self.entity_types

    def missing_fields(self, present):
        found = {(f or "").lower() for f in present}
        return [f for f in self.expected_fields if f.lower() not in found]

    def describe(self):
        return (f"{self.name}: {len(self.entity_types)} entity type(s), "
                f"{len(self.terminology)} term(s), "
                f"{len(self.expected_fields)} expected field(s)")

    def __repr__(self):
        return f"<DomainPack {self.name}>"


GENERAL = DomainPack(
    name="general",
    entity_types=("person", "organization", "place", "date", "concept"),
    extraction_hint="Extract named people, organizations, places and dates.",
)

LEGAL = DomainPack(
    name="legal",
    entity_types=("party", "clause", "obligation", "jurisdiction", "date",
                  "person", "organization"),
    terminology={
        "claimant": "plaintiff", "complainant": "plaintiff",
        "respondent": "defendant", "accused": "defendant",
        "agreement": "contract", "deed": "contract",
        "governing law": "jurisdiction", "venue": "jurisdiction",
    },
    expected_fields=("parties", "effective_date", "jurisdiction", "termination"),
    extraction_hint=("Extract the parties, their obligations, effective and "
                     "termination dates, and the governing jurisdiction."),
    functional_predicates=("effective_date", "jurisdiction", "termination_date"),
)

FILM = DomainPack(
    name="film",
    entity_types=("character", "location", "scene", "production", "role",
                  "person", "organization"),
    terminology={
        "lead": "protagonist", "hero": "protagonist",
        "antagonist": "antagonist", "villain": "antagonist",
        "loc": "location", "int": "location", "ext": "location",
    },
    expected_fields=("title", "logline", "characters", "locations"),
    extraction_hint=("Extract characters, the locations scenes are set in, and "
                     "the productions or works they belong to."),
    functional_predicates=("title", "logline"),
)

FINANCE = DomainPack(
    name="finance",
    entity_types=("instrument", "counterparty", "account", "amount", "date",
                  "organization", "person"),
    terminology={
        "buyer": "counterparty", "seller": "counterparty",
        "notional": "amount", "principal": "amount",
        "maturity": "maturity_date", "expiry": "maturity_date",
    },
    expected_fields=("counterparties", "amount", "currency", "maturity_date"),
    extraction_hint=("Extract counterparties, amounts with their currency, and "
                     "the instrument and maturity involved."),
    functional_predicates=("amount", "currency", "maturity_date"),
)

RESEARCH = DomainPack(
    name="research",
    entity_types=("author", "institution", "method", "finding", "dataset",
                  "person", "organization"),
    terminology={
        "writer": "author", "researcher": "author",
        "university": "institution", "lab": "institution",
        "result": "finding", "conclusion": "finding",
    },
    expected_fields=("authors", "method", "findings"),
    extraction_hint=("Extract authors, their institutions, the method used and "
                     "the findings claimed."),
)

PACKS = {p.name: p for p in (GENERAL, LEGAL, FILM, FINANCE, RESEARCH)}


def get(name):
    """A pack by name, falling back to `general`.

    Falling back rather than raising: an unrecognised domain should degrade to
    generic handling, not stop the ingest. The caller can check `.name` if it
    needs to know whether its request was honoured.
    """
    return PACKS.get((name or "").strip().lower(), GENERAL)


def register(pack):
    """Add a pack at runtime — the point of packs being data."""
    PACKS[pack.name] = pack
    return pack


def audit(pack, documents):
    """Which documents are missing what their domain expects.

    Only the domain knows a contract without parties is incomplete. This is
    where that knowledge earns its place: the same corpus, audited against
    different expectations, produces different findings.
    """
    findings = []
    for doc in documents:
        missing = pack.missing_fields(doc.get("fields", ()))
        if missing:
            findings.append({
                "doc_id": doc.get("doc_id"),
                "title": doc.get("title"),
                "missing": missing,
                "note": f"a {pack.name} document usually records: {', '.join(missing)}",
            })
    return findings
