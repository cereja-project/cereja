import argparse
import sys
from cereja.utils import get_version_pep440_compliant
from cereja.files import crlf_to_lf

if __name__ == "__main__":
    sys.stdout.write("\U0001F352 Cereja Tools\n")
    sys.stdout.flush()
    parser = argparse.ArgumentParser(description='Cereja Tools.')
    parser.add_argument('--version', action='version', version=get_version_pep440_compliant())
    parser.add_argument('--crlf_to_lf')
    args = parser.parse_args()
    if args.crlf_to_lf:
        crlf_to_lf(args.crlf_to_lf)
