To release:

1. Update version in optoConfig96/version.py, including `post`
2. Rebuild docs and README `make README.md`
3. Update CHANGELOG.txt
4. Tag with vx.y.z or vx.y.zpostP
    * Tags without `post` will automatically be built and released
    * Tags with `post` will only be built and unploaded to PyPI
5. git push && git push --tags
