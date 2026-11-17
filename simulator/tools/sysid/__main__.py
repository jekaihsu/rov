"""Command line entry point for reproducible offline reports.

`python -m tools.sysid fit-x1 <folder>` writes a Markdown suggestion and does not
edit the vehicle catalogue. The older `python -m tools.sysid <dataset> --output`
path is unchanged.
"""
import argparse
import sys

from .core import analyze
from .fit_x1 import fit_x1

STRINGS = {
    'description': 'Fit calibrated motion and compare controller traces; output suggestions only.',
    'fit_x1': 'Reduce pool logs and suggest X1 parameters. Does not edit vehicles.py.',
}


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == 'fit-x1':
        parser = argparse.ArgumentParser(prog='python -m tools.sysid fit-x1', description=STRINGS['fit_x1'])
        parser.add_argument('dataset')
        parser.add_argument('--output', default=None)
        args = parser.parse_args(argv[1:])
        fit_x1(args.dataset, args.output)
        destination = args.output or str(args.dataset).rstrip('/') + '/fit-report'
        print(destination)
        return
    parser = argparse.ArgumentParser(description=STRINGS['description'])
    parser.add_argument('dataset')
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    analyze(args.dataset, args.output)


if __name__ == '__main__':
    main()
