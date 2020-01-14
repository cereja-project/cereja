from cereja.others import install_if_not
import subprocess
import sys
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(base_dir)
setup_file = os.path.join(base_dir, 'setup.py')
conf_file = os.path.join(base_dir, 'cereja', 'conf.py')

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

subprocess.run([f"{sys.executable}", {setup_file}, "sdist bdist_wheel"])
subprocess.run([f"{sys.executable}", "-m", "twine", "upload", f"{dist}{os.path.sep}*"])
