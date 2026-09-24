# Automatic releases

Merge release changes through `develop` into `master`. The `Python package`
workflow validates Python 3.11 through 3.14, imports, distribution contents,
and documentation. Only a successful **push** run on `master` can start
`Upload Python Package`; pull requests, forks, and failed runs cannot publish.

Update both values in `cereja/_version.py` before preparing a new stable release:

```python
VERSION = "2.3.1.final.0"
__version__ = "2.3.1"
```

The version is read without importing Cereja. Automatic releases accept final
`major.minor.patch` versions and never bump source files themselves. A version
already published from an earlier commit is a successful no-op. New versions
must be greater than the latest stable version on PyPI.

CI preserves its validated wheel and sdist for 30 days. Publication downloads
those files from the exact CI run, checks their metadata, and checks
out the commit recorded by that run. It creates a numeric tag such as `2.3.1`
and a GitHub Release at that same commit, then uploads the files through PyPI
Trusted Publishing. No package is rebuilt in the privileged publishing job.
`pythonpublish.yml` and the `pypi` environment retain their existing publisher
identity. The release created by this workflow is not used to trigger another
workflow; publication continues in the same run.

Artifact names include the producing job's attempt. The publisher selects the
latest artifact produced no later than the successful CI attempt. This also
supports re-running only failed CI jobs, where a successful build job retains
its earlier artifact. The selected artifact name is passed unchanged to deploy.

## Retry and publication state

If uploading fails, re-run the failed `Upload Python Package` workflow while
its CI artifacts remain available. Keep the original successful CI run and
attempt: rebuilding can change archive hashes. An existing tag is never moved.
For the same tagged commit, files already on PyPI must have matching SHA-256
digests; only missing files are uploaded. Unexpected network errors, conflicting
tags, mismatched metadata, or different file contents stop publication.

A GitHub Release can exist even when the PyPI upload failed. Confirm the deploy
job and the package's PyPI version before announcing availability. Creating a
GitHub Release manually no longer bypasses the CI gate. If artifacts have
expired or a conflicting version cannot be recovered, prepare a new version
and let the full pipeline validate it.

The first merge that installs this workflow can publish the version already
declared in `master` if that version is not yet on PyPI. Merging the workflow
therefore enables publishing; a pull request alone does not publish a package.
