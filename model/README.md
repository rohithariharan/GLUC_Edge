# Model artifacts

| File | What it is |
|---|---|
| `glucedge_model.tflite` | Deployed INT8 model. This is what X-CUBE-AI converts to C. |
| `glucedge_model.keras` | Float32 pre-quantization baseline, kept to document the PTQ step. |

## Quantization

Read directly from the `.tflite`:

| | Tensor | Shape | Scale | Zero-point |
|---|---|---|---|---|
| Input | `serving_default_ppg_window:0` | `int8[1,100,1]` | `0.026640190` | `-13` |
| Output | `StatefulPartitionedCall_1:0` | `int8[1,1]` | `0.858824909` | `-128` |

Dequantized output range: **0.0 – 219.0 mg/dL**.
Training distribution: mean 123.88 mg/dL, std 38.03 mg/dL.

These constants are mirrored in
`../firmware/GLUC_EDGE/Core/Inc/glucedge_params.h`. If you retrain or
re-quantize, regenerate that header from the notebook — do not hand-edit it,
and do not let the two drift apart.

## Redeploying

See "Deploying the model" in the root README. The generated sources under
`firmware/GLUC_EDGE/X-CUBE-AI/App/` are currently from an older model and must
be regenerated before flashing.
