"""Look Schema v0.1 — validator (spec section 10).

`validate_look(look) -> ValidationReport` enforces the six rules. Errors make a Look
illegal (`report.ok is False`); warnings are advisory (forward-compat, unknown fields).

The rules, verbatim from the spec:
  1. Every operation MUST reference a cause_ref that exists in intent.transfer. Else: reject op.
  2. Every material_map_notes warning MUST have a matching do_not_transfer entry. Else: reject.
  3. `global` operations without justification: reject op.
  4. Protections are applied post-plan (executor concern) — NOT enforced here.
  5. Unknown fields: ignored with warning (forward compatibility).
  6. Unknown schema_version major: reject.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from .models import Look

KNOWN_MAJOR = "0"  # this file implements schema major version 0 (v0.1)


@dataclass
class ValidationReport:
    ok: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def __bool__(self) -> bool:          # so `if report:` means "is it legal"
        return self.ok

    def summary(self) -> str:
        head = "VALID" if self.ok else "INVALID"
        lines = [f"[{head}] {len(self.errors)} error(s), {len(self.warnings)} warning(s)"]
        lines += [f"  ERROR:   {e}" for e in self.errors]
        lines += [f"  warning: {w}" for w in self.warnings]
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
#  rule 5 helper — collect unknown (extra) fields anywhere in the tree        #
# --------------------------------------------------------------------------- #
def _collect_unknown_fields(model: BaseModel, path: str, out: list[str]) -> None:
    extra = getattr(model, "model_extra", None)
    if extra:
        for k in extra:
            out.append(f"{path}.{k}" if path else k)
    for name, value in model.__dict__.items():
        child_path = f"{path}.{name}" if path else name
        if isinstance(value, BaseModel):
            _collect_unknown_fields(value, child_path, out)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, BaseModel):
                    _collect_unknown_fields(item, f"{child_path}[{i}]", out)


# --------------------------------------------------------------------------- #
#  rule 2 helper — does any do_not_transfer entry "cover" this material note? #
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> set[str]:
    return {t for t in text.lower().replace("-", "_").replace(" ", "_").split("_") if len(t) > 2}


def _note_is_covered(note, do_not_transfer) -> bool:
    """A material warning is covered if a do_not_transfer entry mentions the material or region.

    Match is token-overlap: e.g. material 'tinted_glass' / region 'background' is covered by a
    do_not_transfer cause 'blue_tinted_glass_in_reference_background' (shares 'glass'/'background').
    """
    note_tokens = _tokens(note.material) | _tokens(note.region)
    if not note_tokens:
        # A warning with no material/region label — any disclaimer at all counts as covering it.
        return len(do_not_transfer) > 0
    for entry in do_not_transfer:
        entry_tokens = _tokens(entry.cause) | _tokens(entry.reason)
        if note_tokens & entry_tokens:
            return True
    return False


# --------------------------------------------------------------------------- #
#  the validator                                                              #
# --------------------------------------------------------------------------- #
def validate_look(look: Look) -> ValidationReport:
    report = ValidationReport()

    # rule 6 — schema version major
    major = str(look.schema_version).split(".")[0]
    if major != KNOWN_MAJOR:
        report.error(
            f"schema_version '{look.schema_version}' has unknown major version '{major}' "
            f"(this validator implements major {KNOWN_MAJOR})."
        )
        # A wrong major means we can't trust the rest — stop here.
        return report

    transfer_causes = look.intent.causes()

    # rule 1 + rule 3 — per operation
    for op in look.operations:
        cause_ref = op.justification.cause_ref if op.justification else ""
        if not cause_ref or cause_ref not in transfer_causes:
            report.error(
                f"operation '{op.op_id}': justification.cause_ref '{cause_ref}' does not exist "
                f"in intent.transfer. Every edit must be justified by a declared cause."
            )
        if op.is_global() and not (op.justification and op.justification.statement.strip()):
            report.error(
                f"operation '{op.op_id}' is a global op with no justification statement. "
                f"Scene-wide edits must explain why the cause applies to every region."
            )

    # rule 2 — every material warning must be disclaimed in do_not_transfer
    for note in look.scene_analysis.warnings():
        if not _note_is_covered(note, look.intent.do_not_transfer):
            label = note.material or note.region or "(unlabelled)"
            report.error(
                f"material_map_notes warning for '{label}' has no matching intent.do_not_transfer "
                f"entry. Environmental colour must be explicitly declared non-transferable."
            )

    # rule 5 — unknown fields become warnings (forward compatibility)
    unknown: list[str] = []
    _collect_unknown_fields(look, "", unknown)
    for path in unknown:
        report.warn(f"unknown field ignored: {path}")

    return report
