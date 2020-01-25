from cereja.utils import install_if_not
import subprocess
import sys
import os
import logging
import shutil

choice_level_change = """
0 -> major
1 -> minor
2 -> micro

Choose the level of change:
"""
logger = logging.getLogger(__name__)

base_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_dir)
setup_file = os.path.join(base_dir, 'setup.py')
conf_file = os.path.join(base_dir, 'cereja', '__ini__.py')

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

        # Remove latest build, info and dist
        files_cereja_build = [
            os.path.join(base_dir, 'build'),
            os.path.join(base_dir, 'cereja.egg-info'),
            os.path.join(base_dir, 'dist')
        ]
        for p in files_cereja_build:
            shutil.rmtree(p)
