"""Validate tested release artifacts and stage an immutable GitHub release.

This standard-library helper never uploads distributions. The publishing action
receives only files absent from PyPI after a validated retry.
"""

import argparse
import ast
from dataclasses import dataclass
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile


VERSION_PATTERN = re.compile(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z')
SHA_PATTERN = re.compile(r'[0-9a-f]{40}\Z')
ARTIFACT_PATTERN = re.compile(r'python-distributions-([1-9]\d*)\Z')


class ReleaseError(RuntimeError):
    """A release prerequisite could not be established."""


def require(condition, message):
    if not condition:
        raise ReleaseError(message)


def version_tuple(value):
    require(isinstance(value, str) and VERSION_PATTERN.fullmatch(value), 'Version must be a final X.Y.Z release')
    return tuple(map(int, value.split('.')))


class Client:
    def __init__(self, token):
        self.token = token

    def _request(self, url, method='GET', data=None, github=False):
        headers = {'User-Agent': 'cereja-calango-release', 'Accept': 'application/json'}
        if github:
            headers.update({'Authorization': f'Bearer {self.token}',
                            'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2026-03-10'})
        encoded = None if data is None else json.dumps(data).encode('utf-8')
        if encoded is not None:
            headers['Content-Type'] = 'application/json'
        request = Request(url, data=encoded, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                result = json.load(response)
        except HTTPError as error:
            error.close()
            if method == 'GET' and error.code == 404:
                return None
            raise ReleaseError(f'{method} {url} returned HTTP {error.code}') from error
        except (URLError, TimeoutError, OSError, ValueError) as error:
            raise ReleaseError(f'{method} {url} failed: {type(error).__name__}') from error
        require(isinstance(result, dict), f'{url} did not return a JSON object')
        return result

    def github(self, path, *, method='GET', data=None):
        return self._request('https://api.github.com' + path, method, data, github=True)

    def pypi(self, project, version=None):
        suffix = f'/{version}' if version is not None else ''
        return self._request(f'https://pypi.org/pypi/{project}{suffix}/json')


def validate_run(event, repository, branch, root):
    require(re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository), 'Invalid GitHub repository')
    require(isinstance(event, dict), 'Missing workflow_run event object')
    run = event.get('workflow_run', {})
    required = {'name': 'Python package', 'event': 'push', 'head_branch': branch,
                'conclusion': 'success', 'status': 'completed'}
    require(isinstance(run, dict), 'Missing workflow_run object')
    for field, expected in required.items():
        require(run.get(field) == expected, f'workflow_run.{field} must be {expected!r}')
    head_repository = run.get('head_repository')
    require(isinstance(head_repository, dict) and head_repository.get('full_name') == repository,
            'The tested run came from another repository')
    sha = run.get('head_sha')
    require(isinstance(sha, str) and SHA_PATTERN.fullmatch(sha), 'Invalid tested commit SHA')
    head = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root, text=True, capture_output=True, timeout=30)
    require(head.returncode == 0 and head.stdout.strip() == sha, 'Checkout HEAD differs from the tested commit')
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', sha, f'origin/{branch}'],
                              cwd=root, text=True, capture_output=True, timeout=30)
    require(ancestor.returncode == 0, f'The tested commit is not on origin/{branch}')
    return sha


def select_artifact(branch, event, repository, root, client):
    """Select the latest artifact produced by this run up to its successful attempt."""
    sha = validate_run(event, repository, branch, root)
    run = event['workflow_run']
    run_id, attempt = run.get('id'), run.get('run_attempt')
    require(type(run_id) is int and run_id > 0 and type(attempt) is int and attempt > 0,
            'workflow_run.id and run_attempt must be positive integers')
    listing = client.github(f'/repos/{repository}/actions/runs/{run_id}/artifacts?per_page=100')
    require(isinstance(listing, dict), 'Tested workflow artifacts are unavailable')
    count, artifacts = listing.get('total_count'), listing.get('artifacts')
    require(type(count) is int and count >= 0 and isinstance(artifacts, list), 'Invalid workflow artifact listing')
    require(count <= 100, 'More than 100 workflow artifacts exist; automatic selection requires a bounded listing')
    require(len(artifacts) == count, 'Workflow artifact listing is incomplete')
    candidates = []
    for artifact in artifacts:
        require(isinstance(artifact, dict), 'Invalid workflow artifact metadata')
        name = artifact.get('name')
        match = ARTIFACT_PATTERN.fullmatch(name) if isinstance(name, str) else None
        if match and int(match.group(1)) <= attempt:
            candidates.append((int(match.group(1)), artifact))
    require(bool(candidates), 'No distribution artifact exists for this tested workflow attempt')
    latest = max(number for number, _ in candidates)
    selected = [artifact for number, artifact in candidates if number == latest]
    require(len(selected) == 1, 'Multiple distribution artifacts have the same attempt number')
    artifact = selected[0]
    require(artifact.get('expired') is False, 'The latest distribution artifact has expired; do not reuse an older build')
    artifact_run = artifact.get('workflow_run')
    if artifact_run is not None:
        require(isinstance(artifact_run, dict), 'Invalid artifact workflow metadata')
        if 'head_sha' in artifact_run:
            require(artifact_run['head_sha'] == sha, 'Distribution artifact belongs to another commit')
    return {'artifact_name': artifact['name']}


def read_version(root, project):
    tree = ast.parse((root / project / '_version.py').read_text(encoding='utf-8'))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('VERSION', '__version__'):
                    require(target.id not in values, f'Duplicate version assignment: {target.id}')
                    try:
                        values[target.id] = ast.literal_eval(node.value)
                    except (TypeError, ValueError) as error:
                        raise ReleaseError('Release versions must be literal strings') from error
    version = values.get('__version__')
    version_tuple(version)
    require(values.get('VERSION') == version + '.final.0', 'VERSION and __version__ disagree')
    return version


@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str


def metadata_matches(data, project, version):
    metadata = BytesParser().parsebytes(data)
    names, versions = metadata.get_all('Name', []), metadata.get_all('Version', [])
    require(len(names) == len(versions) == 1, 'Distribution metadata must contain one Name and Version')
    name = re.sub(r'[-_.]+', '-', names[0]).lower()
    require(name == project and versions[0] == version, 'Distribution Name/Version differs from source metadata')


def read_artifacts(dist, project, version):
    directory = Path(os.path.abspath(dist))
    require(directory.is_dir() and directory.resolve() == directory and directory.parent != directory,
            'Distribution directory must be an existing owned directory without symlinks')
    paths = sorted(directory.iterdir())
    require(len(paths) == 2 and all(path.is_file() and not path.is_symlink() for path in paths),
            'Distribution directory must contain exactly one wheel and one source archive')
    wheels = [path for path in paths if path.name.endswith('.whl')]
    sources = [path for path in paths if path.name.endswith('.tar.gz')]
    require(len(wheels) == len(sources) == 1, 'Expected exactly one .whl and one .tar.gz')
    with zipfile.ZipFile(wheels[0]) as archive:
        names = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
        require(len(names) == 1, 'Wheel must contain exactly one METADATA file')
        metadata_matches(archive.read(names[0]), project, version)
    with tarfile.open(sources[0], 'r:gz') as archive:
        members = [item for item in archive.getmembers() if item.name.count('/') == 1 and item.name.endswith('/PKG-INFO')]
        require(len(members) == 1 and members[0].isfile(), 'Source archive must contain one top-level PKG-INFO')
        metadata_matches(archive.extractfile(members[0]).read(), project, version)
    return {path.name: Artifact(path, hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths}


def tag_commit(client, repository, tag):
    reference = client.github(f'/repos/{repository}/git/ref/tags/{tag}')
    if reference is None:
        return None
    require(reference.get('ref') == f'refs/tags/{tag}', 'GitHub returned a different tag reference')
    obj = reference.get('object', {})
    for _ in range(10):
        require(isinstance(obj, dict), 'Tag object metadata is invalid')
        sha = obj.get('sha')
        require(isinstance(sha, str) and SHA_PATTERN.fullmatch(sha), 'Tag object has an invalid SHA')
        if obj.get('type') == 'commit':
            return sha
        require(obj.get('type') == 'tag', 'Release tag does not resolve to a commit')
        annotation = client.github(f'/repos/{repository}/git/tags/{sha}')
        require(annotation is not None, 'Annotated tag object is missing')
        obj = annotation.get('object', {})
    raise ReleaseError('Annotated tag nesting is invalid')


def published_files(record, project, version):
    if record is None:
        return {}
    info = record.get('info', {})
    require(isinstance(info, dict) and info.get('name', '').lower() == project and info.get('version') == version,
            'PyPI returned different project/version metadata')
    urls = record.get('urls')
    require(isinstance(urls, list), 'PyPI release file list is missing')
    result = {}
    for item in urls:
        require(isinstance(item, dict) and isinstance(item.get('digests'), dict), 'Invalid PyPI artifact metadata')
        name, digest = item.get('filename'), item['digests'].get('sha256')
        require(isinstance(name, str) and name not in result and isinstance(digest, str)
                and re.fullmatch(r'[0-9a-f]{64}', digest), 'PyPI returned invalid or duplicate artifact metadata')
        result[name] = digest
    return result


@dataclass(frozen=True)
class Plan:
    should_publish: bool
    version: str
    source_sha: str
    reason: str
    tag_sha: str | None
    artifacts: dict
    uploaded: tuple

    def outputs(self):
        return {'should_publish': str(self.should_publish).lower(), 'version': self.version,
                'tag': self.version, 'source_sha': self.source_sha}


def plan_release(project, branch, dist, event, repository, root, client):
    sha = validate_run(event, repository, branch, root)
    version = read_version(root, project)
    artifacts = read_artifacts(dist, project, version)
    tag_sha = tag_commit(client, repository, version)
    record = client.pypi(project, version)
    uploaded = published_files(record, project, version)
    latest_record = client.pypi(project)
    latest = None
    if latest_record is not None:
        info = latest_record.get('info')
        require(isinstance(info, dict) and info.get('name', '').lower() == project,
                'PyPI returned different project metadata')
        latest = info.get('version')
        version_tuple(latest)
    complete_existing = any(name.endswith('.whl') for name in uploaded) and any(name.endswith('.tar.gz') for name in uploaded)
    if record is not None and tag_sha != sha:
        require(tag_sha is None or complete_existing,
                'A partial PyPI release belongs to a different commit; retry its original tested run')
        return Plan(False, version, sha, 'Version already exists on PyPI without a matching tested tag',
                    tag_sha, artifacts, ())
    require(tag_sha in (None, sha), 'Release tag belongs to another commit; retry its original tested run')
    for name, digest in uploaded.items():
        require(name in artifacts and artifacts[name].sha256 == digest,
                'Existing PyPI artifact differs from this tested run; retry with its original artifacts')
    if len(uploaded) == len(artifacts):
        return Plan(False, version, sha, 'All tested artifacts are already published', tag_sha, artifacts, tuple(uploaded))
    if latest is not None:
        comparison = version_tuple(version), version_tuple(latest)
        proven_retry = tag_sha == sha and bool(uploaded)
        require(comparison[0] > comparison[1] or proven_retry,
                'Source version must be newer than the latest PyPI version')
    return Plan(True, version, sha, 'Tested release has unpublished artifacts', tag_sha, artifacts, tuple(uploaded))


def stage_release(project, branch, dist, event, repository, root, client):
    plan = plan_release(project, branch, dist, event, repository, root, client)
    if not plan.should_publish:
        return plan
    if plan.tag_sha is None:
        client.github(f'/repos/{repository}/git/refs', method='POST',
                      data={'ref': f'refs/tags/{plan.version}', 'sha': plan.source_sha})
    # Check the exact tag again before creating a release or deleting retry files.
    require(tag_commit(client, repository, plan.version) == plan.source_sha, 'Release tag changed during staging')
    existing = client.github(f'/repos/{repository}/releases/tags/{plan.version}')
    if existing is None:
        client.github(f'/repos/{repository}/releases', method='POST', data={
            'tag_name': plan.version, 'target_commitish': plan.source_sha,
            'name': plan.version, 'generate_release_notes': True, 'draft': False, 'prerelease': False,
            'make_latest': 'legacy',
        })
    else:
        require(existing.get('tag_name') == plan.version, 'GitHub returned an unexpected release')
    for name in plan.uploaded:
        artifact = plan.artifacts[name]
        require(not artifact.path.is_symlink() and hashlib.sha256(artifact.path.read_bytes()).hexdigest() == artifact.sha256,
                'Local artifact changed during staging')
        artifact.path.unlink()
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('artifact', 'plan', 'stage'))
    parser.add_argument('--project', choices=('cereja', 'calango'), required=True)
    parser.add_argument('--branch', choices=('master', 'main'), required=True)
    parser.add_argument('--dist', type=Path)
    args = parser.parse_args(argv)
    if args.mode != 'artifact' and args.dist is None:
        parser.error('--dist is required for plan and stage')
    try:
        repository = os.environ['GITHUB_REPOSITORY']
        token = os.environ['GITHUB_TOKEN']
        require(bool(token), 'GITHUB_TOKEN is empty')
        event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'))
        client = Client(token)
        if args.mode == 'artifact':
            outputs = select_artifact(args.branch, event, repository, Path.cwd(), client)
            description = 'Selected immutable distributions from the tested workflow run'
        else:
            operation = stage_release if args.mode == 'stage' else plan_release
            plan = operation(args.project, args.branch, args.dist, event, repository, Path.cwd(), client)
            outputs = plan.outputs()
            description = plan.reason
        if output_path := os.environ.get('GITHUB_OUTPUT'):
            with open(output_path, 'a', encoding='utf-8') as stream:
                stream.writelines(f'{key}={value}\n' for key, value in outputs.items())
        print(json.dumps(dict(outputs, reason=description)))
        return 0
    except (ReleaseError, KeyError, OSError, ValueError, tarfile.TarError, zipfile.BadZipFile,
            subprocess.SubprocessError) as error:
        print(f'Release validation failed: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
