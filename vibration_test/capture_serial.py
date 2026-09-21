"""
Capture ESP32 serial output directly to a CSV file.

Requires: pip install pyserial

Usage:
    python capture_serial.py COM3 running.csv 30
    python capture_serial.py COM3 stopped.csv 30

Arguments: <COM port> <output filename> <duration in seconds>
"""

import sys
import time
import serial

def main():
    if len(sys.argv) != 4:
        print("Usage: python capture_serial.py <COM_PORT> <output.csv> <duration_seconds>")
        sys.exit(1)

    port = sys.argv[1]
    outfile = sys.argv[2]
    duration = float(sys.argv[3])

    print(f"Connecting to {port} at 115200 baud (without resetting the board)...")
    # dsrdtr/rtscts=False, plus explicitly clearing DTR and RTS after opening,
    # prevents the CP2102's auto-reset circuit from rebooting the ESP32 when
    # this connection opens -- otherwise every capture would silently restart
    # the sketch and reset motorSpeed back to its default.
    ser = serial.Serial(port, 115200, timeout=1, dsrdtr=False, rtscts=False)
    ser.setDTR(False)
    ser.setRTS(False)
    time.sleep(0.5)

    print(f"Capturing for {duration} seconds... (make sure the motor is already in the state you want)")
    lines_written = 0
    start = time.time()

    with open(outfile, "w") as f:
        while time.time() - start < duration:
            raw = ser.readline()
            if not raw:
                continue
            line = raw.decode("utf-8", errors="ignore").strip()
            # only keep lines that look like real CSV data rows (start with a digit)
            if line and line[0].isdigit():
                f.write(line + "\n")
                lines_written += 1

    ser.close()
    print(f"Done. Wrote {lines_written} rows to {outfile}")

if __name__ == "__main__":
    main()
