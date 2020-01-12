import setuptools

VERSION = "0.2.6"

with open("README.md", "r") as fh:
    long_description = fh.read()

EXCLUDE_FROM_PACKAGES = ('cereja.tests'
                         )

setuptools.setup(
    name="cereja",
    version=VERSION,
    author="Joab Leite",
    author_email="jlsn1@ifal.edu.br",
    description="My Utils",
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
