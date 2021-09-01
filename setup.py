# This implements most of the recommendations contained in
# https://packaging.python.org/tutorials/packaging-projects/. The sources are
# placed under the src/ subdirectory just for compatibility with that article,
# although I think not using the src/ subdirectory is slightly easier.
#
# The 'pyproject.toml' config file is NOT used, because it seems to interfere
# with the `pip3 install --user -e .` command which installs the package as a
# link into this repository. Using a link makes development easier because we
# don't have to constantly reinstall the package.

import setuptools

# Slurp in the README.md. PyPI finally supports Markdown, so we no longer need
# to convert it to RST.
with open('README.md', encoding="utf-8") as f:
    long_description = f.read()

# Read the version string from bigquery_schema_generator/version.py.
# See https://packaging.python.org/guides/single-sourcing-package-version/
version = {}
with open("src/acetimetools/version.py") as fp:
    exec(fp.read(), version)
version_string = version['__version__']
if not version_string:
    raise Exception("Unable to read version.py")

setuptools.setup(
    name='acetimetools',
    version=version_string,
    description='AceTime Tools',
    long_description=long_description,
    long_description_content_type="text/markdown",
    url='https://github.com/bxparks/AceTimeTools',
    author='Brian T. Park',
    author_email='brian@xparks.net',
    license='MIT',
    package_dir={"": "src"},
    packages=setuptools.find_packages(where="src"),
    python_requires='>=3.7',
)
