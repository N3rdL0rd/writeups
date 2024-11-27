import argparse
import gzip
import json

def main():
    parser = argparse.ArgumentParser(description="Read Proxyman session file")
    parser.add_argument("session_file", help="Proxyman session file")
    args = parser.parse_args()

    with gzip.open(args.session_file, "rt") as f:
        session = json.load(f)

    with open("session.json", "w") as f:
        json.dump(session, f, indent=4)
        
if __name__ == "__main__":
    main()