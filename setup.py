import setuptools

import cereja

with open("README.md", "r") as fh:
    long_description = fh.read()

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
