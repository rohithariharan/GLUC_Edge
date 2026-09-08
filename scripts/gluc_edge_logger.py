#!/usr/bin/env python3
# gluc_edge_logger.py - capture MAX30102 stream from the STM32F401RE ST-LINK VCP.
#
#   pip install pyserial
#   python gluc_edge_logger.py --port COM7 --seconds 60 --out capture.csv
#   python gluc_edge_logger.py --list
#
# Accepts either format on USART2 @ 115200 8N1:
#   RAW  : "<tick_ms>,<red>,<ir>\r\n"
#   JSON : {"glucose":106.4,"red":80878,"ir":119507,"status":"OK","sqi_score":0.92}
# Writes a unified CSV: t_ms,red,ir,stm_glucose,stm_status,stm_sqi

import argparse, csv, json, sys, time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial missing.  Run:  pip install pyserial")


def list_serial_ports():
    ports = list(list_ports.comports())
    if not ports:
        print("No serial ports found. Is the Nucleo plugged in?")
        return
    for p in ports:
        print("  %-12s %s" % (p.device, p.description))


def parse_line(line):
    line = line.strip()
    if not line:
        return None
    if line.startswith("{"):
        try:
            d = json.loads(line)
        except Exception:
            return None
        return {
            "t_ms": d.get("t_ms", ""),
            "red": d.get("red", ""),
            "ir": d.get("ir", ""),
            "stm_glucose": d.get("glucose", ""),
            "stm_status": d.get("status", ""),
            "stm_sqi": d.get("sqi_score", ""),
        }
    parts = line.split(",")
    if len(parts) >= 3:
        try:
            return {
                "t_ms": int(float(parts[0])),
                "red": int(float(parts[1])),
                "ir": int(float(parts[2])),
                "stm_glucose": "", "stm_status": "", "stm_sqi": "",
            }
        except ValueError:
            return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="e.g. COM7 or /dev/ttyACM0")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--out", default="capture.csv")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list or not args.port:
        list_serial_ports()
        if not args.port:
            sys.exit("\nRe-run with --port <device>")

    print("Opening %s @ %d ..." % (args.port, args.baud))
    ser = serial.Serial(args.port, args.baud, timeout=1.0)
    time.sleep(2.0)              # let the ST-LINK CDC settle
    ser.reset_input_buffer()

    fields = ["t_ms", "red", "ir", "stm_glucose", "stm_status", "stm_sqi"]
    n_raw = n_json = n_bad = 0
    t0 = time.time()

    with open(args.out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        print("Place your finger on the sensor. Capturing %.0f s ..." % args.seconds)
        while time.time() - t0 < args.seconds:
            try:
                raw = ser.readline().decode("utf-8", errors="ignore")
            except Exception as e:
                print("read error:", e)
                break
            rec = parse_line(raw)
            if rec is None:
                if raw.strip():
                    n_bad += 1
                continue
            if rec["stm_status"] != "":
                n_json += 1
            else:
                n_raw += 1
            w.writerow(rec)
            total = n_raw + n_json
            if total % 200 == 0:
                print("  %5d lines  (%.1f s)" % (total, time.time() - t0))

    ser.close()
    print("\nDone. raw=%d json=%d unparsed=%d" % (n_raw, n_json, n_bad))
    print("Wrote %s" % args.out)
    if n_raw == 0:
        print("\nNo raw sample lines captured. The notebook needs per-sample")
        print("red/ir values - enable the CSV debug mode in your firmware.")


if __name__ == "__main__":
    main()
