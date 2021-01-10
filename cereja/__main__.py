"""

Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import argparse
import sys
from cereja import get_version_pep440_compliant, Path
from cereja.file.v1.core import crlf_to_lf, File
from cereja.config import BASE_DIR

if __name__ == "__main__":
    sys.stdout.write("\U0001F352 Cereja Tools\n")
    sys.stdout.flush()
    parser = argparse.ArgumentParser(description='Cereja Tools.')
    parser.add_argument('--version', action='version', version=get_version_pep440_compliant())
    parser.add_argument('--crlf_to_lf')
    parser.add_argument('--lf_to_crlf')
    parser.add_argument('--startmodule', type=str)
    args = parser.parse_args()
    if args.crlf_to_lf:
        crlf_to_lf(args.crlf_to_lf)

    if args.startmodule:
        base_dir = Path(BASE_DIR)
        license_ = '"""\n' + File.load(base_dir.parent.join('LICENSE')).string + '\n"""'
        new_module_path = base_dir.join(*args.startmodule.split('/'))
        if new_module_path.parent.exists and new_module_path.parent.is_dir:
            File(new_module_path, license_).save()
        else:
            print(f"{new_module_path} is not valid.")
