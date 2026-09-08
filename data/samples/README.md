# Sample captures

## `record_features.csv`

Raw MAX30102 stream captured over the ST-LINK VCP with
`scripts/gluc_edge_logger.py`.

| | |
|---|---|
| Rows | 4,000 |
| Duration | 40.0 s (0 – 39,990 ms) |
| Sample rate | 100 Hz |
| Columns | `t_ms, red, ir, stm_glucose, stm_status, stm_sqi` |
| IR range | 109,045 – 111,379 (~2% AC modulation) |

**This capture is unlabeled.** The `stm_glucose`, `stm_status` and `stm_sqi`
columns are empty for all 4,000 rows — it was recorded before the firmware
emitted JSON telemetry. Use it as a fixture for exercising the DSP chain, not
as validation data.
