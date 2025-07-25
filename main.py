"""
Entry point: main.py
Usage:
    python main.py <input_file>
"""
import sys
import json
from processor import CourtCaseProcessor


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python main.py <input_file> [output_file]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) == 3 else 'output.json'

    processor = CourtCaseProcessor(input_file)
    processor.read_and_extract()
    df = processor.parse_cases()

    # Save entire DataFrame to JSON file
    df.to_json(output_file, orient='records', force_ascii=False, indent=2)
    print(f"Output saved to {output_file}")
          
if __name__ == '__main__':
    main()