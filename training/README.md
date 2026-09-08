# Training

Export the Colab notebooks here, with **all outputs cleared** before committing:

- `01_dataset_prep.ipynb` — PPG loading, filtering, windowing
- `02_train_model.ipynb` — architecture and training loop
- `03_quantize_export.ipynb` — INT8 post-training quantization, `.tflite` export,
  and generation of `glucedge_params.h` / `glucedge_golden.h`

The notebooks are the only place `glucedge_params.h` and `glucedge_golden.h`
should be produced. Both headers are auto-generated; hand-editing them breaks
host/device parity.
