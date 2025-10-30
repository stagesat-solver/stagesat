import csv
import subprocess
import re
import os
import argparse
import sys

def parse_time_string(time_str):
    """
    Parses a time string like 'real 32.82' into seconds as a float (32.82).
    """
    match = re.search(r"real\s+([\d.]+)", time_str)
    if match:
        return float(match.group(1))
    return None

def main():
    parser = argparse.ArgumentParser(description="Run a benchmark of SMT2 files using cvc5 with a time limit.")
    parser.add_argument("csv_file", help="Path to the input CSV file.")
    parser.add_argument("smt_folder", help="Path to the folder containing the .smt2 files.")
    parser.add_argument("-o", "--output", default=None, help="Path to the output CSV file. Defaults to <input_file>_results.csv.")
    parser.add_argument("-t", "--timeout", type=int, default=1200, help="Timeout for each run in seconds.")
    
    args = parser.parse_args()

    if not os.path.isfile(args.csv_file):
        print(f"Error: CSV file not found at '{args.csv_file}'")
        sys.exit(1)
    if not os.path.isdir(args.smt_folder):
        print(f"Error: SMT2 folder not found at '{args.smt_folder}'")
        sys.exit(1)

    if args.output:
        output_csv_path = args.output
    else:
        base, ext = os.path.splitext(args.csv_file)
        output_csv_path = f"{base}_results{ext}"

    print(f"Reading CSV from: {args.csv_file}")
    print(f"Reading SMT2 files from: {args.smt_folder}")
    print(f"Writing results to: {output_csv_path}")
    print(f"Timeout per file: {args.timeout} seconds")
    print("-" * 30)

    try:
        with open(args.csv_file, mode='r', newline='', encoding='utf-8') as infile, \
             open(output_csv_path, mode='w', newline='', encoding='utf-8') as outfile:
            
            reader = csv.DictReader(infile)
            fieldnames = reader.fieldnames
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            
            writer.writeheader()

            for row in reader:
                filename = row['SMT2-LIB program']
                filepath = os.path.join(args.smt_folder, filename)

                print(f"Processing {filename}...")

                # Check if file exists before running
                if not os.path.isfile(filepath):
                    print(f"  -> Warning: File '{filepath}' not found. Skipping.")
                    row['Satisfiability'] = 'file_not_found'
                    row['Time(s)'] = ''
                    writer.writerow(row)
                    continue

                command = f"timeout {args.timeout}s /usr/bin/time -f \"real %e\" cvc5 \"{filepath}\""
                
                satisfiability_result = ''
                time_result = ''

                try:
                    # Execute the command
                    result = subprocess.run(
                        command, 
                        shell=True, 
                        capture_output=True, 
                        text=True,
                        check=True
                    )

                    # Parse stdout for sat/unsat
                    stdout = result.stdout.strip()
                    if 'unsat' in stdout:
                        satisfiability_result = 'unsat'
                    elif 'sat' in stdout:
                        satisfiability_result = 'sat'
                    else:
                        satisfiability_result = 'unknown'
                        print(f"  -> Warning: Could not determine sat/unsat from stdout: '{stdout}'")

                    # Parse stderr for time
                    time_in_seconds = parse_time_string(result.stderr)
                    if time_in_seconds is not None:
                        time_result = f"{time_in_seconds:.3f}"
                    else:
                        print(f"  -> Warning: Could not parse time from stderr: '{result.stderr}'")

                except subprocess.CalledProcessError as e:
                    if e.returncode == 124:
                        print(f"  -> TIMEOUT after {args.timeout} seconds.")
                        satisfiability_result = 'timeout'
                    else:
                        print(f"  -> ERROR: Command failed with exit code {e.returncode}.")
                        print(f"    Stderr: {e.stderr}")
                        satisfiability_result = 'error'
                    time_result = ''

                except Exception as e:
                    print(f"  -> UNEXPECTED ERROR: {e}")
                    satisfiability_result = 'error'
                    time_result = ''

                # Update the row and write to the output file
                row['Satisfiability'] = satisfiability_result
                row['Time(s)'] = time_result
                writer.writerow(row)

    except IOError as e:
        print(f"Error: Could not read/write CSV file. {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

    print("-" * 30)
    print("Benchmark finished successfully.")

if __name__ == "__main__":
    main()