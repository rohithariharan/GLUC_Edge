# Scripts

## `gluc_edge_logger.py`

Captures the MAX30102 stream from the STM32F401RE over the ST-LINK virtual COM
port and writes a unified CSV.

```bash
pip install pyserial
python gluc_edge_logger.py --list
python gluc_edge_logger.py --port COM7 --seconds 60 --out capture.csv
```

Accepts either format on USART2 @ 115200 8N1:

- Raw: `<tick_ms>,<red>,<ir>`
- JSON: `{"glucose":106.4,"red":80878,"ir":119507,"status":"OK","sqi_score":0.92}`

Output schema: `t_ms,red,ir,stm_glucose,stm_status,stm_sqi`
