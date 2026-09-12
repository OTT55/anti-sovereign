# Decisions — why Canonchain is built the way it is

This folder is Canonchain's memory. Every meaningful choice — which database, which
structure, how we handle login — gets a short numbered file here called an **ADR**
(*Architecture Decision Record*). Think of each one as a signed note that says:

> "On this date, we chose X over Y, for these reasons, accepting these trade-offs."

**Why we do this:** so the *why* is never lost. Months later — or in a university
interview, or when a collaborator joins — nobody has to guess why something was
done. The reasoning is written down, dated, and kept in git next to the code it
explains. Changing a past decision doesn't mean deleting its record; you add a new
ADR that supersedes it, so the history of *thinking* is preserved too.

**How to read one:** every ADR has the same four parts —
**Context** (what forced a decision), **Decision** (what we chose),
**Why** (the reasoning in plain English), and **Trade-off** (the honest cost).

## Index

- [0001 — Canonchain is the first production app; scope & stack](0001-scope-and-stack.md)
- [0002 — Database and data model](0002-database-and-data-model.md)
