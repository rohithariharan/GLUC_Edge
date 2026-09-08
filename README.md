<div align="center">

# GLUCEDGE

**Non-invasive blood glucose estimation on a Cortex-M4 — no cloud, no lancet, no data leaving the device.**

A quantized INT8 convolutional network runs entirely on an STM32F401RE, inferring glucose concentration from a photoplethysmography (PPG) window captured by a MAX30102 optical sensor.

[![Platform](https://img.shields.io/badge/MCU-STM32F401RE-03234B)](https://www.st.com/en/microcontrollers-microprocessors/stm32f401re.html)
[![Toolchain](https://img.shields.io/badge/IDE-STM32CubeIDE-03234B)](https://www.st.com/en/development-tools/stm32cubeide.html)
[![Edge AI](https://img.shields.io/badge/X--CUBE--AI-10.2.1-FF6F00)](https://www.st.com/en/embedded-software/x-cube-ai.html)
[![Model](https://img.shields.io/badge/Model-INT8%20TFLite-425066)](model/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

</div>

---

> ⚠️ **Research prototype.** GLUCEDGE is an engineering demonstrator built for academic evaluation. It is **not** a medical device, has not been clinically validated, and must never be used to make treatment decisions.

---

## ⚠️ Action required before flashing

The C sources under `firmware/GLUC_EDGE/X-CUBE-AI/App/` were generated from an **earlier** version of the model. They do not match `model/glucedge_model.tflite` in this repository:

| | Currently compiled into firmware | `model/glucedge_model.tflite` |
|---|---|---|
| Input tensor | `serving_default_ppg_cycle0` | `serving_default_ppg_window:0` |
| Input scale / zero-point | `0.028633960` / `-13` | `0.026640190` / `-13` |
| Output scale / zero-point | `0.433431447` / `-128` | `0.858824909` / `-128` |
| Output range | 0 – 110.5 mg/dL | 0 – 219.0 mg/dL |
| Parameters | 1,537 | ~22,864 |

Flashing without regenerating produces readings wrong by roughly a factor of two, with no error raised. Follow [Deploying the model](#deploying-the-model) first.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Model Card](#model-card)
- [Hardware Requirements](#hardware-requirements)
- [Software Toolchain](#software-toolchain)
- [Repository Structure](#repository-structure)
- [Setup](#setup)
- [Deploying the model](#deploying-the-model)
- [Build](#build)
- [Flash & Run](#flash--run)
- [Verification](#verification)
- [Results](#results)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Team](#team)
- [License](#license)

---

## Overview

Conventional glucose monitoring is invasive and consumable-dependent. GLUCEDGE explores whether the morphology of a PPG waveform — the arterial pressure wave measured optically at the fingertip — carries enough signal to regress blood glucose concentration, and whether that inference fits inside a **microcontroller with no radio, no SD card and no internet connection**.

The design constraint drove every decision: DC removal, high-pass filtering, smoothing, peak detection, normalization, quantization, forward pass and dequantization must all complete on an 84 MHz Cortex-M4F with 96 KB of SRAM.

**Why on-device matters here:** biometric health data never leaves the sensor. There is no transmission surface to attack, no cloud dependency, and no latency spent on a network round trip.

---

## Architecture

GLUCEDGE is a **hardware/model co-design**: the network topology was chosen to fit the MCU, and the MCU peripherals were configured to feed the network.

```
                    ┌──────────────────────────────────────────────┐
                    │            STM32F401RE @ 84 MHz              │
                    │            512 KB Flash / 96 KB SRAM         │
   ┌──────────┐     │  ┌────────────────────────────────────────┐  │
   │ MAX30102 │ I2C1│  │ SENSE                                  │  │
   │  PPG /   ├─────┼─▶│  FIFO burst read, TIM3-paced           │  │
   │  SpO2    │     │  │  → 100 Hz IR stream, 250-sample ring   │  │
   └──────────┘     │  └───────────────┬────────────────────────┘  │
                    │                  ▼                           │
                    │  ┌────────────────────────────────────────┐  │
                    │  │ SIGNAL CONDITIONING                    │  │
                    │  │  Butterworth HPF, order 2, fc = 0.5 Hz │  │
                    │  │  Savitzky-Golay FIR, 11 taps, order 3  │  │
                    │  │  peak detect, min distance 40 samples  │  │
                    │  │  → 100-sample window → normalize       │  │
                    │  └───────────────┬────────────────────────┘  │
                    │                  ▼                           │
                    │  ┌────────────────────────────────────────┐  │
                    │  │ SIGNAL QUALITY INDEX                   │  │
                    │  │  0.6·min(1, p2p/1500)                  │  │
                    │  │    + 0.4·min(1, std/400)               │  │
                    │  │  reject window if score < 0.35         │  │
                    │  └───────────────┬────────────────────────┘  │
                    │                  ▼                           │
                    │  ┌────────────────────────────────────────┐  │
                    │  │ QUANTIZE                               │  │
                    │  │  q = clamp(round(v/0.02664019) - 13)   │  │
                    │  │  → int8[1][100][1]                     │  │
                    │  └───────────────┬────────────────────────┘  │
                    │                  ▼                           │
                    │  ┌────────────────────────────────────────┐  │
                    │  │ INFERENCE  (X-CUBE-AI 10.2.1 runtime)  │  │
                    │  │  INT8 CNN, ~22,864 parameters          │  │
                    │  └───────────────┬────────────────────────┘  │
                    │                  ▼                           │
                    │  ┌────────────────────────────────────────┐  │
                    │  │ DEQUANTIZE                             │  │
                    │  │  mg/dL = (q_out + 128) × 0.858824909   │  │
                    │  │  target denorm folded into the graph — │  │
                    │  │  apply no further scaling              │  │
                    │  └────┬──────────────────────┬────────────┘  │
                    └───────┼──────────────────────┼───────────────┘
                       I2C2 │                USART2 │ 115200 8N1
                            ▼                       ▼
                    ┌──────────────┐        ┌──────────────┐
                    │ SSD1306 OLED │        │ ST-LINK VCP  │
                    │  128×64      │        │ host logging │
                    └──────────────┘        └──────────────┘
```

Every DSP constant above is defined once in
[`firmware/GLUC_EDGE/Core/Inc/glucedge_params.h`](firmware/GLUC_EDGE/Core/Inc/glucedge_params.h),
auto-generated by the training notebook, so the Python and C signal chains
cannot silently drift apart.

### Peripheral map

| Peripheral | Role | Notes |
|---|---|---|
| `I2C1` | MAX30102 PPG sensor | 400 kHz fast mode, address 0x57 |
| `I2C2` | SSD1306 OLED display | 400 kHz fast mode, address 0x3C |
| `USART2` | Host telemetry / debug | 115200 8N1, routed to ST-LINK VCP |
| `TIM3` | Sampling cadence | 100 Hz acquisition trigger |
| `DMA` | Non-blocking transfers | Frees CPU during acquisition |

---

## Model Card

| Property | Value |
|---|---|
| Deployed model | `model/glucedge_model.tflite` (28,256 B) |
| Float baseline | `model/glucedge_model.keras` (254,442 B) |
| Runtime | X-CUBE-AI 10.2.1 (ST Edge AI Core 2.2.0) |
| Quantization | Full-integer INT8, post-training |
| Parameters | ~22,864 |
| Input | `serving_default_ppg_window:0`, `int8[1,100,1]` |
| Input quantization | scale `0.026640190`, zero-point `-13` |
| Output | `StatefulPartitionedCall_1:0`, `int8[1,1]` |
| Output quantization | scale `0.858824909`, zero-point `-128` |
| Output range | 0.0 – 219.0 mg/dL |
| Training distribution | mean 123.88 mg/dL, std 38.03 mg/dL |
| Sampling rate | 100 Hz |
| Window length | 100 samples |

**Quantization (C):**

```c
q_in = clamp(roundf(v_norm / AI_INPUT_SCALE) + AI_INPUT_ZERO_POINT, -128, 127);
gluc = ((float)q_out - AI_OUTPUT_ZERO_POINT) * AI_OUTPUT_SCALE;   /* mg/dL */
```

Target denormalization is folded into the network graph. Do **not** apply any
further scaling in firmware.

---

## Hardware Requirements

| Component | Part | Interface | Notes |
|---|---|---|---|
| MCU board | **NUCLEO-F401RE** (STM32F401RET6) | — | Cortex-M4F @ 84 MHz, 512 KB Flash, 96 KB SRAM, on-board ST-LINK/V2-1 |
| PPG sensor | **MAX30102** breakout | I2C1 @ 0x57 | Red + IR LEDs, integrated 18-bit ADC |
| Display | **SSD1306** 128×64 OLED | I2C2 @ 0x3C | Live waveform + reading |
| Cabling | 4× jumper per I2C device | — | 3V3, GND, SCL, SDA |
| Host link | USB-A ↔ USB Mini-B | — | Power, flashing and VCP on one cable |

Confirm pin assignments against `firmware/GLUC_EDGE/GLUC_EDGE.ioc` before wiring — the `.ioc` is authoritative.

---

## Software Toolchain

| Tool | Version | Purpose |
|---|---|---|
| STM32CubeIDE | 1.16.0 or newer | Build, flash, debug |
| STM32CubeMX | Bundled with CubeIDE | Pin/clock/peripheral configuration |
| X-CUBE-AI | **10.2.1** | Model → optimized C conversion |
| ST Edge AI Core | 2.2.0 | Underlying conversion engine |
| Arm GNU Toolchain | Bundled with CubeIDE | `arm-none-eabi-gcc` |
| Python | 3.10+ | Training, capture, validation |
| TensorFlow | 2.15+ | Training and INT8 export |
| pyserial | 3.5+ | `scripts/gluc_edge_logger.py` |

Install X-CUBE-AI inside CubeIDE via **Help → Manage Embedded Software Packages → STMicroelectronics → X-CUBE-AI → 10.2.1**. That version specifically — a different runtime will not match the committed `NetworkRuntime1020_CM4_GCC.a`.

---

## Repository Structure

```
GLUCEDGE/
├── firmware/
│   └── GLUC_EDGE/                      # STM32CubeIDE project — import this
│       ├── GLUC_EDGE.ioc               # CubeMX config — source of truth
│       ├── .project / .cproject        # Eclipse CDT metadata
│       ├── .mxproject                  # CubeMX generation state
│       ├── STM32F401RETX_FLASH.ld      # Flash linker script
│       ├── STM32F401RETX_RAM.ld        # RAM linker script
│       ├── Core/
│       │   ├── Inc/
│       │   │   ├── glucedge_params.h   # DSP + quantization constants
│       │   │   ├── glucedge_golden.h   # Parity test vector
│       │   │   └── main.h, i2c.h, tim.h, usart.h, dma.h, gpio.h
│       │   ├── Src/                    # main.c, peripheral init, IRQ handlers
│       │   └── Startup/                # startup_stm32f401retx.s
│       ├── Drivers/
│       │   ├── CMSIS/                  # Arm CMSIS core + device headers
│       │   └── STM32F4xx_HAL_Driver/   # ST HAL
│       ├── Middlewares/ST/AI/
│       │   ├── Inc/                    # ai_platform.h, ai_datatypes.h, ...
│       │   └── Lib/                    # NetworkRuntime1020_CM4_GCC.a  ← REQUIRED
│       ├── X-CUBE-AI/App/              # Generated network — REGENERATE, see above
│       └── LICENSE_X-CUBE-AI.txt
│
├── model/
│   ├── glucedge_model.tflite           # Deployed INT8 model
│   └── glucedge_model.keras            # Float32 pre-quantization baseline
│
├── scripts/
│   └── gluc_edge_logger.py             # USART2 capture → CSV
│
├── data/samples/
│   └── record_features.csv             # 40 s raw MAX30102 capture
│
├── training/                           # Export the Colab notebooks here
├── docs/
│   └── xcubeai_report_OLD_MODEL.txt    # Footprint report for the superseded model
│
├── .gitignore
├── LICENSE
└── README.md
```

---

## Setup

```bash
git clone https://github.com/<your-username>/GLUCEDGE.git
cd GLUCEDGE
```

Install X-CUBE-AI 10.2.1, then import the firmware:

STM32CubeIDE → **File → Import… → General → Existing Projects into Workspace** → *Select root directory* → browse to `GLUCEDGE/firmware/` → tick `GLUC_EDGE` → **Finish**.

> Leave **"Copy projects into workspace" unchecked** — copying detaches the project from Git and your commits silently stop tracking it.

---

## Deploying the model

Required before the first build, because the committed generated sources are stale.

1. Open `firmware/GLUC_EDGE/GLUC_EDGE.ioc` in STM32CubeMX.
2. **Middleware and Software Packs → X-CUBE-AI** → select the network → browse to `model/glucedge_model.tflite`.
3. Click **Analyze**. Record the reported Flash and RAM footprint — the activation buffer is the binding constraint on 96 KB of SRAM.
4. **Generate Code**.
5. Confirm the regenerated scales match `Core/Inc/glucedge_params.h`. If they differ, the header is stale — regenerate it from the training notebook rather than editing it by hand.
6. `Project → Clean…`, then rebuild.

---

## Build

**In the IDE:** right-click `GLUC_EDGE` → **Build Project** (`Ctrl+B`).

**If linking fails with undefined `ai_*` symbols**, the runtime library is missing from your clone:

```bash
git ls-files | grep NetworkRuntime
# expect: firmware/GLUC_EDGE/Middlewares/ST/AI/Lib/NetworkRuntime1020_CM4_GCC.a
```

---

## Flash & Run

**In the IDE:** connect the Nucleo over USB → **Run → Run As → STM32 C/C++ Application**.

**From the CLI:**

```bash
STM32_Programmer_CLI -c port=SWD -w firmware/GLUC_EDGE/Debug/GLUC_EDGE.elf -v -rst
```

**Capture telemetry:**

```bash
pip install pyserial
python scripts/gluc_edge_logger.py --list
python scripts/gluc_edge_logger.py --port /dev/ttyACM0 --seconds 60 --out capture.csv
```

The logger accepts either raw `<tick_ms>,<red>,<ir>` lines or JSON
(`{"glucose":..., "red":..., "ir":..., "status":..., "sqi_score":...}`) and
normalizes both into a single CSV schema.

---

## Verification

`firmware/GLUC_EDGE/Core/Inc/glucedge_golden.h` holds a known-good input window
with its expected quantized input, raw output and dequantized result. Run it
once at boot:

1. Feed `GLUC_GOLDEN_NORM` through `quantize_input()` — must equal `GLUC_GOLDEN_Q_IN` byte for byte.
2. Run the network on `GLUC_GOLDEN_Q_IN` — `q_out` must equal `GLUC_GOLDEN_Q_OUT` (`16`) exactly.
3. Dequantize — must equal `GLUC_GOLDEN_GLUCOSE` (`123.670787`) within 0.01 mg/dL.

This vector has been replayed against `model/glucedge_model.tflite` on host and
reproduces exactly. A failure at step 1 means the DSP chain diverged; at step 2,
the wrong model is compiled in; at step 3, the dequantization constants are stale.

---

## Results

<!-- Populate once on-device verification is complete -->

| Metric | Host (float32) | Host (INT8) | On-device |
|---|---|---|---|
| MAE (mg/dL) | `<TBD>` | `<TBD>` | `<TBD>` |
| RMSE (mg/dL) | `<TBD>` | `<TBD>` | `<TBD>` |
| R² | `<TBD>` | `<TBD>` | `<TBD>` |
| Clarke Error Grid, zone A+B | `<TBD>` | `<TBD>` | `<TBD>` |
| Inference latency @ 84 MHz | — | — | `<TBD>` ms |

---

## Known Limitations

Stated plainly, because a reviewer will find these anyway.

1. **No clinical validation.** No paired reference measurements from an approved glucometer. Error metrics are computed against dataset labels only.
2. **PPG-to-glucose is an open research question.** The physiological pathway linking pulse morphology to blood glucose is not established. Reported accuracy may reflect dataset-specific confounders rather than a transferable relationship.
3. **Output is bounded at 219.0 mg/dL.** INT8 output quantization cannot express values above this, so severe hyperglycemia saturates instead of reporting a true value.
4. **`data/samples/record_features.csv` is unlabeled.** A raw 40-second capture with empty `stm_glucose`, `stm_status` and `stm_sqi` columns, recorded before the firmware emitted JSON telemetry. It is a signal-chain fixture, not validation data.
5. **Fixed 100-sample window.** The window assumes a plausible heart rate; extreme bradycardia or tachycardia degrades the input representation.
6. **No motion-artifact rejection beyond the SQI gate.** The amplitude/variance score rejects poor contact, not movement within an otherwise clean window.

---

## Roadmap

- [x] Phase 1 — Dataset preparation
- [x] Phase 2 — Model training + INT8 TFLite export
- [x] Phase 3 — CubeMX peripheral config + X-CUBE-AI integration
- [ ] Phase 4 — Embedded DSP chain (HPF, Savitzky-Golay, peak detection, SQI)
- [ ] Phase 5 — MAX30102 and SSD1306 drivers
- [ ] Phase 6 — Main application loop + inference invocation
- [ ] Phase 7 — Golden-vector parity + latency profiling

---

## Team

| Name | Role |
|---|---|
| `<name>` | `<role>` |
| `<name>` | `<role>` |

---

## Acknowledgements

- STMicroelectronics — STM32Cube HAL, X-CUBE-AI, ST Edge AI Core
- `<dataset name and citation>`

---

## License

Firmware and training code released under the [MIT License](LICENSE).

The X-CUBE-AI runtime library and generated sources are covered separately by
[`firmware/GLUC_EDGE/LICENSE_X-CUBE-AI.txt`](firmware/GLUC_EDGE/LICENSE_X-CUBE-AI.txt)
(ST SLA0044, Ultimate Liberty). ST HAL and Arm CMSIS drivers retain their
original licenses.
