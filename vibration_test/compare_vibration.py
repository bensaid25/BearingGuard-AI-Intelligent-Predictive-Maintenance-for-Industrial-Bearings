"""
Quick vibration comparison: motor running vs motor stopped.

Matches the headerless CSV format written by capture_serial.py:
timestamp_ms, ax, ay, az, gx, gy, gz, temp_c

Run: python compare_vibration.py
"""

import pandas as pd

COLUMNS = ["timestamp_ms", "ax", "ay", "az", "gx", "gy", "gz", "temp_c"]

running = pd.read_csv("running.csv", header=None, names=COLUMNS)
stopped = pd.read_csv("stopped.csv", header=None, names=COLUMNS)

print(f"Running rows: {len(running)}   Stopped rows: {len(stopped)}\n")
print(f"{'Axis':<10}{'Std (running)':<18}{'Std (stopped)':<18}{'Ratio':<8}")
for axis in ["ax", "ay", "az"]:
    r_std = running[axis].std()
    s_std = stopped[axis].std()
    ratio = r_std / s_std if s_std > 0 else float("inf")
    print(f"{axis:<10}{r_std:<18.4f}{s_std:<18.4f}{ratio:<8.2f}")
