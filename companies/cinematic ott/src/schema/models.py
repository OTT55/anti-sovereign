"""Look Schema v0.1 — Pydantic v2 models.

Faithful implementation of files/look-schema-v0.1.md. This module is *only* the data
shapes plus `default_protections()`. The validation RULES live in `validator.py` so the
"what a Look is" and "what makes a Look legal" concerns stay separate.

Design note (D1.2): every model sets `extra="allow"`, so unknown fields from a future
schema version are preserved rather than rejected — forward compatibility (spec rule 5).
The validator surfaces those unknown fields as *warnings*.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
#  Base: all schema models allow (and preserve) unknown fields                #
# --------------------------------------------------------------------------- #
class SchemaModel(BaseModel):
    model_config = ConfigDict(extra="allow")


# --------------------------------------------------------------------------- #
#  Controlled vocabularies (closed sets from the spec)                        #
# --------------------------------------------------------------------------- #
class SemanticClass(str, Enum):
    skin = "skin"
    face = "face"
    eyes = "eyes"
    hair = "hair"
    clothing = "clothing"
    sky = "sky"
    foliage = "foliage"
    ground = "ground"
    water = "water"
    glass = "glass"
    metal = "metal"
    building = "building"
    vehicle = "vehicle"
    background_other = "background_other"
    glob = "global"  # 'global' is a Python keyword-ish reserved word; value stays "global"


PrimarySource = Literal[
    "sun", "sky", "artificial_tungsten", "artificial_fluorescent",
    "artificial_led", "mixed", "unknown",
]
LightDirection = Literal["front", "back", "side_left", "side_right", "top", "ambient"]
LightQuality = Literal["hard", "soft", "diffused"]
Setting = Literal["indoor", "outdoor", "vehicle", "studio", "unknown"]
TimeOfDay = Literal[
    "golden_hour", "midday", "blue_hour", "night", "overcast_day", "unknown",
]
Contrast = Literal["low", "medium", "high"]
DynamicRange = Literal["compressed", "normal", "wide"]
SourceType = Literal["screenshot", "image", "text_prompt", "manual"]


# --------------------------------------------------------------------------- #
#  2. provenance                                                              #
# --------------------------------------------------------------------------- #
class Provenance(SchemaModel):
    source_type: SourceType = "screenshot"
    reference_hash: str = ""            # sha256 of reference image — never the image itself
    created_by: str = ""               # user_id or model_id
    pipeline_version: str = ""
    created_at: str = ""               # ISO-8601


# --------------------------------------------------------------------------- #
#  3. scene_analysis (descriptive only — no edits)                            #
# --------------------------------------------------------------------------- #
class SecondarySource(SchemaModel):
    type: str
    influence_regions: list[str] = Field(default_factory=list)
    hue_deg: Optional[float] = None


class Lighting(SchemaModel):
    primary_source: PrimarySource = "unknown"
    direction: LightDirection = "ambient"
    quality: LightQuality = "soft"
    estimated_color_temp_k: Optional[int] = None
    secondary_sources: list[SecondarySource] = Field(default_factory=list)


class WeatherAtmosphere(SchemaModel):
    haze_density: float = 0.0
    haze_tint_hue_deg: Optional[float] = None
    notes: str = ""


class Environment(SchemaModel):
    setting: Setting = "unknown"
    time_of_day: TimeOfDay = "unknown"
    weather_atmosphere: WeatherAtmosphere = Field(default_factory=WeatherAtmosphere)


class CameraCharacter(SchemaModel):
    apparent_contrast: Contrast = "medium"
    apparent_dynamic_range: DynamicRange = "normal"
    halation_or_bloom: bool = False
    grain_visible: bool = False


class ExistingGrade(SchemaModel):
    detected: bool = False
    characteristics: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class MaterialMapNote(SchemaModel):
    """A declared environmental colour source (the blue-glass defence).

    A note counts as a *warning* when `warning` is a non-empty string.
    """
    region: str = ""
    material: str = ""
    hue_deg: Optional[float] = None
    warning: str = ""


class SceneAnalysis(SchemaModel):
    lighting: Lighting = Field(default_factory=Lighting)
    environment: Environment = Field(default_factory=Environment)
    camera_character: CameraCharacter = Field(default_factory=CameraCharacter)
    existing_grade: ExistingGrade = Field(default_factory=ExistingGrade)
    mood_tags: list[str] = Field(default_factory=list)
    material_map_notes: list[MaterialMapNote] = Field(default_factory=list)

    def warnings(self) -> list[MaterialMapNote]:
        return [n for n in self.material_map_notes if n.warning.strip()]


# --------------------------------------------------------------------------- #
#  4. intent (causes to transfer)                                             #
# --------------------------------------------------------------------------- #
class TransferCause(SchemaModel):
    cause: str
    effect: str = ""


class DoNotTransfer(SchemaModel):
    cause: str
    reason: str = ""


class Intent(SchemaModel):
    transfer: list[TransferCause] = Field(default_factory=list)
    do_not_transfer: list[DoNotTransfer] = Field(default_factory=list)

    def causes(self) -> set[str]:
        return {t.cause for t in self.transfer}


# --------------------------------------------------------------------------- #
#  5. operations (the WHAT)                                                    #
# --------------------------------------------------------------------------- #
class Mask(SchemaModel):
    source: str = "segmentation"
    feather_px: int = 12
    opacity: float = 1.0


class DepthRange(SchemaModel):
    min: float = 0.0
    max: float = 1.0


class Target(SchemaModel):
    semantic_class: SemanticClass
    instance: str = "all"              # "all" | "subject_primary" | numeric index string
    mask: Mask = Field(default_factory=Mask)
    depth_range: Optional[DepthRange] = None


class Justification(SchemaModel):
    cause_ref: str                     # MUST match an intent.transfer cause (validator rule 1)
    statement: str = ""                # human-readable "why" — surfaced to the user


class Condition(SchemaModel):
    apply_only_if: str = ""
    fallback: Literal["skip", "apply_anyway"] = "skip"


class WhiteBalance(SchemaModel):
    temp_shift_mired: float = 0.0
    tint_shift: float = 0.0


class ToneCurve(SchemaModel):
    type: Literal["pivot", "points"] = "pivot"
    pivot: float = 0.5
    contrast_strength: float = 0.0
    highlight_rolloff: float = 0.0
    black_lift: float = 0.0


class HSLBand(SchemaModel):
    hue_center_deg: float
    hue_width_deg: float = 30.0
    hue_shift_deg: float = 0.0
    sat_scale: float = 1.0
    lum_shift: float = 0.0


class SplitToneStop(SchemaModel):
    hue_deg: Optional[float] = None
    sat: float = 0.0


class SplitTone(SchemaModel):
    shadows: SplitToneStop = Field(default_factory=SplitToneStop)
    highlights: SplitToneStop = Field(default_factory=SplitToneStop)


class Adjustments(SchemaModel):
    white_balance: WhiteBalance = Field(default_factory=WhiteBalance)
    exposure_ev: float = 0.0
    tone_curve: ToneCurve = Field(default_factory=ToneCurve)
    hsl: list[HSLBand] = Field(default_factory=list)
    split_tone: SplitTone = Field(default_factory=SplitTone)
    saturation_scale: float = 1.0


class Operation(SchemaModel):
    op_id: str
    target: Target
    justification: Justification
    condition: Optional[Condition] = None
    adjustments: Adjustments = Field(default_factory=Adjustments)

    def is_global(self) -> bool:
        return self.target.semantic_class == SemanticClass.glob


# --------------------------------------------------------------------------- #
#  6. protections (hard clamps the executor enforces post-plan)               #
# --------------------------------------------------------------------------- #
class SkinProtection(SchemaModel):
    max_hue_shift_deg: float = 8.0
    max_sat_scale_delta: float = 0.15
    max_lum_shift: float = 0.10
    forbid_split_tone_sat_above: float = 0.12


class FaceProtection(SchemaModel):
    inherit: str = "skin"
    forbid_ops: list[str] = Field(default_factory=lambda: ["texture", "clarity", "generative_any"])
    max_local_contrast_delta: float = 0.10


class EyesProtection(SchemaModel):
    forbid_hue_shift: bool = True


class IdentityProtection(SchemaModel):
    pixel_resynthesis: Literal["forbidden"] = "forbidden"
    note: str = "The executor may only remap color values. It may never generate pixels."


class Protections(SchemaModel):
    skin: SkinProtection = Field(default_factory=SkinProtection)
    face_region: FaceProtection = Field(default_factory=FaceProtection)
    eyes: EyesProtection = Field(default_factory=EyesProtection)
    identity: IdentityProtection = Field(default_factory=IdentityProtection)


def default_protections() -> Protections:
    """The hard clamp values from spec section 6 — 'faces are sacred' as data."""
    return Protections()


# --------------------------------------------------------------------------- #
#  7. coherence_rules                                                          #
# --------------------------------------------------------------------------- #
class SharedLightSource(SchemaModel):
    rule: str = (
        "All regions flagged region_lit_by == 'primary_source' must receive temp shifts "
        "within a 15-mired band of each other."
    )
    tolerance_mired: float = 15.0


class NamedRule(SchemaModel):
    rule: str = ""


class CoherenceRules(SchemaModel):
    shared_light_source: SharedLightSource = Field(default_factory=SharedLightSource)
    shadow_consistency: NamedRule = Field(
        default_factory=lambda: NamedRule(
            rule="Shadow tint across regions may not diverge more than 10 deg hue "
                 "unless a secondary source justifies it."
        )
    )
    no_orphan_color: NamedRule = Field(
        default_factory=lambda: NamedRule(
            rule="No hue may be introduced to a region unless it exists in the reference "
                 "OR is produced by a declared cause."
        )
    )


# --------------------------------------------------------------------------- #
#  8. critic                                                                   #
# --------------------------------------------------------------------------- #
class CriticDimension(SchemaModel):
    name: str
    weight: float
    min: float


def _default_critic_dimensions() -> list[CriticDimension]:
    return [
        CriticDimension(name="face_realism", weight=0.25, min=0.85),
        CriticDimension(name="lighting_physical_plausibility", weight=0.15, min=0.75),
        CriticDimension(name="mood_similarity_to_reference", weight=0.20, min=0.70),
        CriticDimension(name="subject_preservation", weight=0.20, min=0.90),
        CriticDimension(name="background_contamination_absence", weight=0.10, min=0.80),
        CriticDimension(name="overall_cinematic_coherence", weight=0.10, min=0.70),
    ]


class CriticConfig(SchemaModel):
    dimensions: list[CriticDimension] = Field(default_factory=_default_critic_dimensions)
    acceptance: str = "all_minimums_met AND weighted_score >= 0.80"
    max_iterations: int = 3
    on_failure: str = "return best_scoring_iteration with warnings"


# --------------------------------------------------------------------------- #
#  9. export                                                                   #
# --------------------------------------------------------------------------- #
class LutGlobalSubset(SchemaModel):
    available: bool = True
    includes: list[str] = Field(default_factory=lambda: ["global tone curve", "global WB", "global HSL"])
    excludes: list[str] = Field(default_factory=lambda: ["all masked regional operations"])
    format: list[str] = Field(default_factory=lambda: ["cube_33", "cube_65"])


class ExportCapability(SchemaModel):
    available: str | bool = True
    fidelity: str = ""


class ExportConfig(SchemaModel):
    lut_expressible: bool = False
    lut_global_subset: LutGlobalSubset = Field(default_factory=LutGlobalSubset)
    xmp_lightroom: ExportCapability = Field(
        default_factory=lambda: ExportCapability(
            available=True, fidelity="high — LR supports masked local adjustments"
        )
    )
    resolve_powergrade: ExportCapability = Field(
        default_factory=lambda: ExportCapability(available="roadmap", fidelity="high")
    )
    full_fidelity: str = "app_only"


# --------------------------------------------------------------------------- #
#  1. top-level Look                                                           #
# --------------------------------------------------------------------------- #
class Look(SchemaModel):
    schema_version: str = "0.1"
    look_id: str = ""
    name: str = ""
    provenance: Provenance = Field(default_factory=Provenance)
    scene_analysis: SceneAnalysis = Field(default_factory=SceneAnalysis)
    intent: Intent = Field(default_factory=Intent)
    operations: list[Operation] = Field(default_factory=list)
    protections: Protections = Field(default_factory=default_protections)
    coherence_rules: CoherenceRules = Field(default_factory=CoherenceRules)
    critic: CriticConfig = Field(default_factory=CriticConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
