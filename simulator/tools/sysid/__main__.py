"""Command line entry point for reproducible offline reports."""
import argparse
from .core import analyze

STRINGS = {'description': 'Fit calibrated motion and compare controller traces; output suggestions only.'}


def main():
    parser = argparse.ArgumentParser(description=STRINGS['description'])
    parser.add_argument('dataset')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    analyze(args.dataset, args.output)


if __name__ == '__main__':
    main()
