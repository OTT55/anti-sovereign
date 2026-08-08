"""Phase 1 acceptance — `pytest tests/test_schema.py` green.

Covers the four behaviours the build plan names:
  * a valid look passes
  * a look with an unjustified op fails (rule 1)
  * a look with a material warning but no do_not_transfer fails (rule 2)
plus the global-op justification (rule 3), the schema-version guard (rule 6),
unknown-field warnings (rule 5), and the default protection clamp values.
"""

from src.schema import (
    Look, validate_look, default_protections, SemanticClass,
    Operation, Target, Justification, Intent, TransferCause, DoNotTransfer,
    MaterialMapNote,
)
from src.schema.models import SceneAnalysis


def _op(op_id="op_001", semantic_class=SemanticClass.skin, cause_ref="low_warm_sunlight",
        statement="Skin lit by low sun warms toward amber in highlights only."):
    return Operation(
        op_id=op_id,
        target=Target(semantic_class=semantic_class),
        justification=Justification(cause_ref=cause_ref, statement=statement),
    )


def _valid_look():
    return Look(
        name="Dusty Golden Hour",
        intent=Intent(
            transfer=[TransferCause(cause="low_warm_sunlight", effect="warm skin highlights")],
        ),
        operations=[_op()],
    )


# --- a valid look passes -----------------------------------------------------
def test_valid_look_passes():
    report = validate_look(_valid_look())
    assert report.ok, report.summary()
    assert report.errors == []


# --- rule 1: an operation whose cause_ref isn't declared fails ---------------
def test_unjustified_op_fails():
    look = _valid_look()
    look.operations.append(_op(op_id="op_002", cause_ref="teal_shadows_from_nowhere"))
    report = validate_look(look)
    assert not report.ok
    assert any("op_002" in e and "cause_ref" in e for e in report.errors)


# --- rule 2: a material warning with no do_not_transfer entry fails ----------
def test_material_warning_without_do_not_transfer_fails():
    look = _valid_look()
    look.scene_analysis = SceneAnalysis(
        material_map_notes=[
            MaterialMapNote(region="background", material="tinted_glass", hue_deg=210,
                            warning="environmental color — do not treat as lighting")
        ]
    )
    # intent.do_not_transfer is empty -> must fail
    report = validate_look(look)
    assert not report.ok
    assert any("do_not_transfer" in e for e in report.errors)


# --- rule 2 (positive): warning WITH a matching do_not_transfer passes -------
def test_material_warning_with_matching_disclaimer_passes():
    look = _valid_look()
    look.scene_analysis = SceneAnalysis(
        material_map_notes=[
            MaterialMapNote(region="background", material="tinted_glass", hue_deg=210,
                            warning="environmental color — do not treat as lighting")
        ]
    )
    look.intent.do_not_transfer = [
        DoNotTransfer(cause="blue_tinted_glass_in_reference_background",
                      reason="material color specific to reference environment")
    ]
    report = validate_look(look)
    assert report.ok, report.summary()


# --- rule 3: a global op with no justification statement fails ---------------
def test_global_op_without_statement_fails():
    look = _valid_look()
    look.intent.transfer.append(TransferCause(cause="atmospheric_haze", effect="lifted blacks"))
    look.operations.append(
        Operation(
            op_id="op_g",
            target=Target(semantic_class=SemanticClass.glob),
            justification=Justification(cause_ref="atmospheric_haze", statement="   "),
        )
    )
    report = validate_look(look)
    assert not report.ok
    assert any("op_g" in e and "global" in e for e in report.errors)


# --- rule 3 (positive): a justified global op passes -------------------------
def test_global_op_with_statement_passes():
    look = _valid_look()
    look.intent.transfer.append(TransferCause(cause="atmospheric_haze", effect="lifted blacks"))
    look.operations.append(
        Operation(
            op_id="op_g",
            target=Target(semantic_class=SemanticClass.glob),
            justification=Justification(
                cause_ref="atmospheric_haze",
                statement="Atmospheric haze scatters light across the whole frame, so it applies globally.",
            ),
        )
    )
    report = validate_look(look)
    assert report.ok, report.summary()


# --- rule 6: an unknown major schema version is rejected ---------------------
def test_unknown_schema_major_rejected():
    look = _valid_look()
    look.schema_version = "9.0"
    report = validate_look(look)
    assert not report.ok
    assert any("major" in e for e in report.errors)


# --- rule 5: unknown fields are preserved and reported as warnings ----------
def test_unknown_fields_warn_not_fail():
    look = Look.model_validate({
        "name": "future look",
        "intent": {"transfer": [{"cause": "low_warm_sunlight", "effect": "x"}]},
        "operations": [{
            "op_id": "op_001",
            "target": {"semantic_class": "skin"},
            "justification": {"cause_ref": "low_warm_sunlight", "statement": "ok"},
        }],
        "some_future_field": {"nested": 1},   # unknown top-level field
    })
    report = validate_look(look)
    assert report.ok, report.summary()
    assert any("some_future_field" in w for w in report.warnings)


# --- default_protections carries the spec's hard clamp values ---------------
def test_default_protections_values():
    p = default_protections()
    assert p.skin.max_hue_shift_deg == 8.0
    assert p.skin.max_lum_shift == 0.10
    assert p.eyes.forbid_hue_shift is True
    assert p.identity.pixel_resynthesis == "forbidden"
    assert "texture" in p.face_region.forbid_ops
