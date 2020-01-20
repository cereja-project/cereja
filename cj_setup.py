from cereja.utils import install_if_not
import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)

base_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_dir)
setup_file = os.path.join(base_dir, 'setup.py')
conf_file = os.path.join(base_dir, 'cereja', 'conf.py')

tests_case_result = subprocess.run([f"{sys.executable}", "-m", "unittest", "tests.tests.UtilsTestCase"]).returncode

allow_update_version = False
if tests_case_result == 0:
    res = input("Tests OK! Update version? s/N: ") or 'n'
    if res.lower() in ['s', 'n']:
        if res.lower() == 's':
            allow_update_version = True
        else:
            logger.info("Ok Exiting...")
            print("Ok Exiting...")

if tests_case_result == 0 and allow_update_version:
    with open(conf_file, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if "VERSION = " in line:
                version_base, version_middle, version_end = [int(i) for i in
                                                             line.strip().split('=')[1].strip(' "').split('.')]
                if version_end < 10:
                    version_end = version_end + 1
                elif version_middle < 10:
                    version_end = 0
                    version_middle = version_middle + 1
                else:
                    version_middle = 0
                    version_base = version_base + 1

                version = f'{version_base}.{version_middle}.{version_end}'
                lines[i] = f'VERSION = "{version}"\n'

    with open(conf_file, 'w') as f:
        f.writelines(lines)

    required_libs = ["setuptools", "wheel", "twine"]

    for lib_name in required_libs:
        install_if_not(lib_name)

    dist = os.path.join(base_dir, "dist")

    res = input("Up version? s/N: ") or 'n'
    if res.lower() in ['s', 'n']:
        if res.lower() == 's':
            subprocess.run([f"{sys.executable}", f"{setup_file}", "sdist", "bdist_wheel"])
            subprocess.run([f"{sys.executable}", "-m", "twine", "upload", f"{dist}{os.path.sep}*"])
        else:
            print("Versão não foi enviada.")
