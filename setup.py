import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="jlsneto-jlsneto",
    version="0.0.1",
    author="Joab Leite",
    author_email="jlsn1@ifal.edu.br;leitejoab@gmail.com",
    description="My Utils",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jlsneto/jlsneto",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)