#!/usr/bin/env python3
"""
Script to run XSat on SMT2 files listed in a CSV file and update results.
"""

import csv
import subprocess
import sys
import os
from pathlib import Path
import argparse
from datetime import datetime


def run_xsat(smt2_folder, smt2_filename):
    """
    Run make and xsat.py for a given SMT2 file.
    Returns (satisfiability, time) tuple.
    """
    # Run make command
    smt2_path = f"{smt2_folder}/{smt2_filename}"
    make_cmd = ['make', f'IN={smt2_path}']

    print(f"  Running: {' '.join(make_cmd)}", flush=True)
    try:
        result = subprocess.run(
            make_cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for compilation
        )
        if result.returncode != 0:
            print(f"  Make failed with return code {result.returncode}", file=sys.stderr)
            if result.stderr:
                print(f"  stderr: {result.stderr[:200]}", file=sys.stderr)
            return None, None
    except subprocess.TimeoutExpired:
        print(f"  Make timed out for {smt2_filename}", file=sys.stderr)
        return None, None
    except Exception as e:
        print(f"  Error running make for {smt2_filename}: {e}", file=sys.stderr)
        return None, None

    # Run xsat.py
    xsat_cmd = ['python', 'xsat.py', '--bench', '--cpuTime']
    print(f"  Running: {' '.join(xsat_cmd)}", flush=True)

    try:
        result = subprocess.run(
            xsat_cmd,
            capture_output=True,
            text=True,
            timeout=7200  # 2h timeout for solving
        )

        if result.returncode != 0:
            print(f"  xsat.py failed with return code {result.returncode}", file=sys.stderr)
            return None, None

        lines = result.stdout.strip().split('\n')

        # Expected format:
        # Line 1: "sat" or "unsat"
        # Line 2: time as float
        if len(lines) >= 2:
            satisfiability = lines[0].strip().lower()  # "sat" or "unsat"
            time_str = lines[1].strip()

            # Validate satisfiability
            if satisfiability not in ['sat', 'unsat']:
                print(f"  Unexpected satisfiability value: {satisfiability}", file=sys.stderr)
                satisfiability = None

            # Parse time
            try:
                time_value = float(time_str)
            except ValueError:
                print(f"  Error parsing time: {time_str}", file=sys.stderr)
                time_value = None

            return satisfiability, time_value
        else:
            print(f"  Unexpected output format. Got {len(lines)} lines:", file=sys.stderr)
            print(f"  Output: {result.stdout[:200]}", file=sys.stderr)
            return None, None

    except subprocess.TimeoutExpired:
        print(f"  xsat.py timed out for {smt2_filename}", file=sys.stderr)
        return "timeout", None
    except Exception as e:
        print(f"  Error running xsat.py for {smt2_filename}: {e}", file=sys.stderr)
        return None, None


def main():
    parser = argparse.ArgumentParser(
        description='Run XSat on SMT2 files listed in CSV and update results'
    )
    parser.add_argument('csv_file', help='Path to the CSV file')
    parser.add_argument('smt2_folder', help='Path to the folder containing SMT2 files')
    parser.add_argument(
        '--run-name',
        default=None,
        help='Name for this run column (default: Time(s) Run N with timestamp)'
    )
    parser.add_argument(
        '--start-from',
        type=int,
        default=0,
        help='Start from row N (0-indexed, default: 0)'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        default=None,
        help='Maximum number of files to process (default: all)'
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_file)
    smt2_folder = Path(args.smt2_folder)

    if not csv_path.exists():
        print(f"Error: CSV file {csv_path} not found", file=sys.stderr)
        sys.exit(1)

    if not smt2_folder.exists():
        print(f"Error: SMT2 folder {smt2_folder} not found", file=sys.stderr)
        sys.exit(1)

    # Read the CSV
    print(f"Reading CSV from {csv_path}...")
    rows = []
    with open(csv_path, 'r', newline='') as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = list(reader)

    print(f"Found {len(rows)} entries in CSV")

    # Determine the column name for this run
    if args.run_name:
        time_column_name = args.run_name
    else:
        # Count existing time columns (columns after the first 4)
        run_number = len(headers) - 4 + 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        time_column_name = f"Time(s) Run {run_number} [{timestamp}]"

    print(f"New time column: {time_column_name}")

    # Add new time column to headers
    headers.append(time_column_name)

    # Process each row
    start_idx = args.start_from
    end_idx = len(rows) if args.max_files is None else min(start_idx + args.max_files, len(rows))

    print(f"\nProcessing rows {start_idx} to {end_idx - 1}...")
    print("=" * 70)

    # Store results during processing
    results = []  # List of (row_index, satisfiability, time_value)

    for i in range(start_idx, end_idx):
        row = rows[i]
        smt2_filename = row[0]
        print(f"\n[{i + 1}/{len(rows)}] Processing: {smt2_filename}")

        satisfiability, time_value = run_xsat(smt2_folder, smt2_filename)

        if satisfiability:
            print(f"  ✓ Satisfiability: {satisfiability}")
        else:
            print(f"  ✗ Satisfiability: FAILED")

        if time_value is not None:
            print(f"  ✓ Time: {time_value:.8f}s")
        else:
            print(f"  ✗ Time: FAILED")

        # Store results
        results.append((i, satisfiability, time_value))

    print("\n" + "=" * 70)
    print("Processing complete. Updating CSV...")

    # Now update all rows at once
    for i in range(len(rows)):
        row = rows[i]

        # Ensure row has at least 4 columns
        while len(row) < 4:
            row.append('')

        # Pad with empty strings for previous time columns
        while len(row) < len(headers) - 1:
            row.append('')

        # Check if this row was processed
        result = next((r for r in results if r[0] == i), None)

        if result:
            _, satisfiability, time_value = result

            # Update satisfiability (column index 3)
            if satisfiability:
                row[3] = satisfiability

            # Add time to the new column
            if time_value is not None:
                row.append(f"{time_value:.8f}")
            else:
                row.append('')
        else:
            # Row not processed, add empty time column
            row.append('')

    # Save all results once
    with open(csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print(f"✓ All results saved to {csv_path}")

    # Print summary
    successful = sum(1 for row in rows[start_idx:end_idx] if row[-1] != '')
    total = end_idx - start_idx
    print(f"\nSummary:")
    print(f"  Total processed: {total}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {total - successful}")


if __name__ == "__main__":
    main()


 # python xsat2-test.py experiment/small.csv Benchmarks/griggio-benchmarks/small/