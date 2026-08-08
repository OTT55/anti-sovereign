# Look Schema — v0.1 (Draft)

The Look Schema is the core interchange format of the system. A "look" is not a set of colors —
it is a structured description of **photographic causes** plus the **regional operations** that
reproduce their effects, with hard protections the AI cannot override.

Format: JSON. Versioned. Every field shown here is normative for v0.1.

---

## 1. Top-level structure

```json
{
  "schema_version": "0.1",
  "look_id": "uuid",
  "name": "Dusty Golden Hour",
  "provenance": { ... },
  "scene_analysis": { ... },
  "intent": { ... },
  "operations": [ ... ],
  "protections": { ... },
  "coherence_rules": { ... },
  "critic": { ... },
  "export": { ... }
}
```

---

## 2. `provenance`

Where this look came from. Required for marketplace attribution and dataset building.

```json
"provenance": {
  "source_type": "screenshot | image | text_prompt | manual",
  "reference_hash": "sha256 of reference image (never the image itself)",
  "created_by": "user_id or model_id",
  "pipeline_version": "string",
  "created_at": "ISO-8601"
}
```

---

## 3. `scene_analysis` — the WHY (reference image)

Produced by the VLM in Stage 2/4. This block is *descriptive only* — it contains no edits.
Separating it from `operations` means the reasoning model and the execution engine can
evolve independently.

```json
"scene_analysis": {
  "lighting": {
    "primary_source": "sun | sky | artificial_tungsten | artificial_fluorescent | artificial_led | mixed | unknown",
    "direction": "front | back | side_left | side_right | top | ambient",
    "quality": "hard | soft | diffused",
    "estimated_color_temp_k": 3200,
    "secondary_sources": [
      { "type": "practical_neon", "influence_regions": ["background"], "hue_deg": 300 }
    ]
  },
  "environment": {
    "setting": "indoor | outdoor | vehicle | studio | unknown",
    "time_of_day": "golden_hour | midday | blue_hour | night | overcast_day | unknown",
    "weather_atmosphere": {
      "haze_density": 0.0,
      "haze_tint_hue_deg": null,
      "notes": "free text"
    }
  },
  "camera_character": {
    "apparent_contrast": "low | medium | high",
    "apparent_dynamic_range": "compressed | normal | wide",
    "halation_or_bloom": false,
    "grain_visible": false
  },
  "existing_grade": {
    "detected": true,
    "characteristics": ["lifted_blacks", "warm_midtones", "teal_shadows"],
    "confidence": 0.0
  },
  "mood_tags": ["nostalgic", "warm", "quiet"],
  "material_map_notes": [
    { "region": "background", "material": "tinted_glass", "hue_deg": 210,
      "warning": "environmental color — do not treat as lighting" }
  ]
}
```

**Design note — `material_map_notes` is the blue-glass defense.** The analysis stage must
label environmental color sources explicitly so the intent stage cannot mistake material
color for light color.

---

## 4. `intent` — causes to transfer

The bridge between analysis and operations. Every entry names a *cause*, not a color.

```json
"intent": {
  "transfer": [
    { "cause": "low_warm_sunlight", "effect": "warm skin highlights, long soft shadows" },
    { "cause": "atmospheric_dust", "effect": "lifted blacks, reduced background contrast" },
    { "cause": "film_like_tone_response", "effect": "soft highlight rolloff" }
  ],
  "do_not_transfer": [
    { "cause": "blue_tinted_glass_in_reference_background",
      "reason": "material color specific to reference environment; no equivalent surface in target" }
  ]
}
```

**Design note — `do_not_transfer` is mandatory when `material_map_notes` contains warnings.**
Forcing the model to explicitly disclaim non-transferable causes is a stronger safeguard than
hoping it silently ignores them.

---

## 5. `operations` — the WHAT

Ordered list. Each operation targets one semantic region, carries a mandatory justification
linked to an `intent.transfer` cause, and optionally a physical condition.

```json
"operations": [
  {
    "op_id": "op_001",
    "target": {
      "semantic_class": "skin",
      "instance": "all | subject_primary | index",
      "mask": { "source": "segmentation", "feather_px": 12, "opacity": 1.0 },
      "depth_range": null
    },
    "justification": {
      "cause_ref": "low_warm_sunlight",
      "statement": "Skin lit by low sun warms toward amber in highlights only."
    },
    "condition": {
      "apply_only_if": "region_lit_by == 'primary_source'",
      "fallback": "skip"
    },
    "adjustments": {
      "white_balance": { "temp_shift_mired": 12, "tint_shift": 0 },
      "exposure_ev": 0.0,
      "tone_curve": {
        "type": "pivot",
        "pivot": 0.45,
        "contrast_strength": -0.1,
        "highlight_rolloff": 0.3,
        "black_lift": 0.0
      },
      "hsl": [
        { "hue_center_deg": 25, "hue_width_deg": 40,
          "hue_shift_deg": 4, "sat_scale": 1.05, "lum_shift": 0.02 }
      ],
      "split_tone": {
        "shadows": { "hue_deg": null, "sat": 0 },
        "highlights": { "hue_deg": 40, "sat": 0.08 }
      },
      "saturation_scale": 1.0
    }
  }
]
```

### Allowed `semantic_class` values (v0.1)

`skin`, `face`, `eyes`, `hair`, `clothing`, `sky`, `foliage`, `ground`, `water`,
`glass`, `metal`, `building`, `vehicle`, `background_other`, `global`

`global` is legal but must carry a justification explaining why a scene-wide cause
(e.g., atmospheric haze, film tone response) applies to every region. Unjustified
global ops are rejected by the validator.

### Adjustment vocabulary (v0.1) — deliberately closed

White balance, exposure, tone curve (pivot or explicit points), HSL bands, split tone,
saturation. **Excluded on purpose:** texture/clarity (face-destructive), any generative
fill or resynthesis, geometric changes. The vocabulary can widen in v0.2+ only with a
protection rule accompanying each new op type.

---

## 6. `protections` — hard clamps the executor enforces

These are not requests to the model. They are limits applied *after* the edit plan,
regardless of what it says.

```json
"protections": {
  "skin": {
    "max_hue_shift_deg": 8,
    "max_sat_scale_delta": 0.15,
    "max_lum_shift": 0.10,
    "forbid_split_tone_sat_above": 0.12
  },
  "face_region": {
    "inherit": "skin",
    "forbid_ops": ["texture", "clarity", "generative_any"],
    "max_local_contrast_delta": 0.10
  },
  "eyes": { "forbid_hue_shift": true },
  "identity": {
    "pixel_resynthesis": "forbidden",
    "note": "The executor may only remap color values. It may never generate pixels."
  }
}
```

**Design note:** protection violations are clamped, logged, and reported to the critic —
a plan that constantly hits clamps is a badly reasoned plan and should score lower.

---

## 7. `coherence_rules` — Stage 8 as data

```json
"coherence_rules": {
  "shared_light_source": {
    "rule": "All regions flagged region_lit_by == 'primary_source' must receive temp shifts within a 15-mired band of each other.",
    "tolerance_mired": 15
  },
  "shadow_consistency": {
    "rule": "Shadow tint across regions may not diverge more than 10 deg hue unless a secondary source justifies it."
  },
  "no_orphan_color": {
    "rule": "No hue may be introduced to a region unless it exists in the reference OR is produced by a declared cause."
  }
}
```

---

## 8. `critic` — rubric and loop control

```json
"critic": {
  "dimensions": [
    { "name": "face_realism", "weight": 0.25, "min": 0.85 },
    { "name": "lighting_physical_plausibility", "weight": 0.15, "min": 0.75 },
    { "name": "mood_similarity_to_reference", "weight": 0.20, "min": 0.70 },
    { "name": "subject_preservation", "weight": 0.20, "min": 0.90 },
    { "name": "background_contamination_absence", "weight": 0.10, "min": 0.80 },
    { "name": "overall_cinematic_coherence", "weight": 0.10, "min": 0.70 }
  ],
  "acceptance": "all_minimums_met AND weighted_score >= 0.80",
  "max_iterations": 3,
  "on_failure": "return best_scoring_iteration with warnings"
}
```

**Design note — hard minimums, not just weighted average.** `subject_preservation: 0.90`
means a gorgeous grade that damages the face fails, full stop. This encodes "faces are
sacred" as arithmetic.

---

## 9. `export` — honest capability declaration

```json
"export": {
  "lut_expressible": false,
  "lut_global_subset": {
    "available": true,
    "includes": ["global tone curve", "global WB", "global HSL"],
    "excludes": ["all masked regional operations"],
    "format": ["cube_33", "cube_65"]
  },
  "xmp_lightroom": { "available": true, "fidelity": "high — LR supports masked local adjustments" },
  "resolve_powergrade": { "available": "roadmap", "fidelity": "high" },
  "full_fidelity": "app_only"
}
```

A screenshot-derived look with regional operations **cannot** be a LUT without lying.
Exporting the global subset keeps pros happy; full fidelity stays in the ecosystem.

---

## 10. Validation rules (executor-side, v0.1)

1. Every operation MUST reference a `cause_ref` that exists in `intent.transfer`. Else: reject op.
2. Every `material_map_notes` warning MUST have a matching `do_not_transfer` entry. Else: reject plan.
3. `global` operations without justification: reject op.
4. Protections are applied post-plan; clamp events are logged and passed to the critic.
5. Unknown fields: ignored with warning (forward compatibility).
6. Unknown `schema_version` major: reject.

---

## 11. Worked micro-example — the blue-glass test case

Reference: subject in front of blue-tinted glass, warm key light on face.
Target: two people outdoors in red clothing, neutral daylight.

- `scene_analysis.material_map_notes` → glass, hue 210, warning flag.
- `intent.do_not_transfer` → blue glass cause, reason: "no equivalent surface in target."
- `intent.transfer` → warm key light on skin; soft contrast.
- `operations` → skin: +warm WB, gentle highlight rolloff. clothing: untouched
  (red is subject-owned color; no cause justifies changing it). background: mild
  contrast reduction only.
- Result: target keeps red clothing and natural skin; inherits warmth and softness.
- A naive color-transfer output (blue everywhere) would violate rules 1 and 2 and
  fail `background_contamination_absence` — the format itself makes the failure illegal.

---

## Open questions for v0.2

1. Depth-conditioned operations (haze that scales with `depth_range`) — needs Depth Anything
   integration decisions.
2. Grain / halation as a separate, face-safe "texture layer" op class with its own protections.
3. Video: temporal coherence rules (per-shot vs per-frame analysis).
4. Marketplace licensing metadata (who may resell / remix a look).
5. Multi-reference looks (blend causes from several screenshots).
