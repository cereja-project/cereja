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

import setuptools

import cereja

long_description = b''.join(cereja.file.FileIO.load('README.md').data).decode()

EXCLUDE_FROM_PACKAGES = ('cereja.tests',
                         'cereja.lab',
                         )

setuptools.setup(
    name="cereja",
    version=cereja.__version__,
    author="Joab Leite",
    author_email="jlsn1@ifal.edu.br",
    description="Cereja is a bundle of useful functions that I don't want to rewrite.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jlsneto/cereja",
    packages=setuptools.find_packages(exclude=EXCLUDE_FROM_PACKAGES),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
