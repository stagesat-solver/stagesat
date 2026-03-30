#!/usr/bin/env python3
import csv, subprocess, sys, argparse
from pathlib import Path
from datetime import datetime


def run_xsat(folder, filename):
    """Run make and xsat.py, return (satisfiability, time)"""
    try:
        subprocess.run(['timeout', '300s', 'make', f'IN={folder}/{filename}'],
                       capture_output=True, text=True, check=True)
        result = subprocess.run(['timeout', '1200s', 'python', 'stagesat.py', '--bench', '--time'],
                                capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        return (lines[0].strip().lower() if lines[0].strip().lower() in ['sat', 'unsat'] else None,
                float(lines[1].strip()) if len(lines) > 1 else None)
    except subprocess.CalledProcessError as e:
        return ("timeout" if e.returncode == 124 else None, None)
    except:
        return (None, None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('csv_file')
    parser.add_argument('smt2_folder')
    parser.add_argument('--run-name', default=None)
    parser.add_argument('--start-from', type=int, default=0)
    parser.add_argument('--max-files', type=int, default=None)
    args = parser.parse_args()

    # Read CSV
    with open(args.csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # Create column names for this run
    if args.run_name:
        sat_col = f"Satisfiability {args.run_name}"
        time_col = f"Time(s) {args.run_name}"
    else:
        n = len([c for c in fieldnames if c.startswith('Time(s)')]) + 1
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        sat_col = f"Satisfiability Run {n} [{ts}]"
        time_col = f"Time(s) Run {n} [{ts}]"

    print(f"New columns: {sat_col}, {time_col}")
    fieldnames.extend([sat_col, time_col])

    # Process rows
    end = len(rows) if args.max_files is None else min(args.start_from + args.max_files, len(rows))

    for i in range(args.start_from, end):
        row = rows[i]
        filename = row['SMT2-LIB program']
        print(f"\n[{i + 1}/{len(rows)}] {filename}")

        sat, time = run_xsat(args.smt2_folder, filename)
        row[sat_col] = sat if sat else ''
        row[time_col] = f"{time:.8f}" if time else ''

        print(f"  Sat: {sat or 'FAILED'}, Time: {time:.3f}s" if time else f"  Sat: {sat or 'FAILED'}")

    # Ensure all rows have new columns
    for row in rows:
        row.setdefault(sat_col, '')
        row.setdefault(time_col, '')

    # Write results
    with open(args.csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✓ Results saved to {args.csv_file}")


if __name__ == "__main__":
    main()

# python stagesat-test.py experiment/small.csv Benchmarks/griggio-benchmarks/small/