import setuptools
import os

pkg_name = 'optoConfig96'
here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, pkg_name, "version.py"), "r") as f:
    for line in f.readlines():
        if line.startswith("__version__"):
            version = line.split("'")[1]
            break

with open('README_PyPI.md', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name=pkg_name,
    version=version,
    author='Oliver Thomas',
    author_email='oliver.thomas@sgbm.uni-freiburg.de',
    description='A GUI tool to configure optoPlate96 experiments',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/WeberSynBioLab/optoConfig-96',
    packages=setuptools.find_packages(),
    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Operating System :: OS Independent',
    ],
    keywords='biology optogenetics optoplate gui',
    install_requires=[
        'traits>=5.2.0',
        'traitsui>=6.1.3',
        'PyQt5>=5.14.0',
        'pygments>=2.5.2',
        'numpy>=1.17.4',
        'matplotlib>=3.1.1'
    ],
    python_requires='>=3.7',
    package_data={
        pkg_name: [
            'resources/appicon.png',
            'resources/arduino_template.cpp',
            'resources/docs/*',
            'resources/docs/*/*',
            'resources/docs/*/*/*',
            'resources/examples/*',
            'resources/LICENSE*'],
    }
)
