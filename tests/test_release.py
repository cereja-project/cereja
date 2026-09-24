"""Release gating and retries with local archives and fake HTTP/Git calls."""

import copy
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
import zipfile

from tools import release


SHA = 'a' * 40
OTHER_SHA = 'b' * 40
REPOSITORY = 'cereja-project/cereja'


class FakeClient:
    def __init__(self):
        self.tag = None
        self.annotations = {}
        self.version_record = None
        self.latest = {'info': {'name': 'cereja', 'version': '1.0.0'}}
        self.release = None
        self.artifact_listing = {'total_count': 0, 'artifacts': []}
        self.calls = []

    def github(self, path, *, method='GET', data=None):
        self.calls.append((method, path, data))
        if method == 'POST' and path.endswith('/git/refs'):
            self.tag = {'ref': data['ref'], 'object': {'type': 'commit', 'sha': data['sha']}}
            return self.tag
        if method == 'POST' and path.endswith('/releases'):
            self.release = dict(data, id=12)
            return self.release
        if '/git/ref/tags/' in path:
            return self.tag
        if '/git/tags/' in path:
            return self.annotations[path.rsplit('/', 1)[-1]]
        if '/releases/tags/' in path:
            return self.release
        if '/actions/runs/' in path:
            return self.artifact_listing
        raise AssertionError('Unexpected request: ' + path)

    def pypi(self, project, version=None):
        self.calls.append(('GET', f'pypi/{project}/{version}', None))
        return self.version_record if version is not None else self.latest


class TestRelease(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.folder = Path(directory.name)
        self.root = self.folder / 'checkout'
        self.root.mkdir()
        self.dist = self.folder / 'artifacts'
        self.dist.mkdir()
        self.project = 'cereja'
        self.branch = 'master'
        self.version = '1.1.0'
        self.event = {'workflow_run': {
            'name': 'Python package', 'event': 'push', 'head_branch': 'master',
            'conclusion': 'success', 'status': 'completed', 'head_sha': SHA,
            'head_repository': {'full_name': REPOSITORY},
            'id': 42, 'run_attempt': 1,
        }}
        self.client = FakeClient()
        self.write_source()
        self.write_archives()
        self.git = patch.object(release.subprocess, 'run', side_effect=self.git_command).start()
        self.addCleanup(patch.stopall)

    def git_command(self, command, **kwargs):
        self.assertEqual(kwargs['cwd'], self.root)
        self.assertEqual(kwargs['timeout'], 30)
        if command == ['git', 'rev-parse', 'HEAD']:
            return subprocess.CompletedProcess(command, 0, SHA + '\n', '')
        self.assertEqual(command, ['git', 'merge-base', '--is-ancestor', SHA, f'origin/{self.branch}'])
        return subprocess.CompletedProcess(command, 0, '', '')

    def write_source(self):
        package = self.root / self.project
        package.mkdir(exist_ok=True)
        (package / '_version.py').write_text(
            f'VERSION = "{self.version}.final.0"\n__version__ = "{self.version}"\n', encoding='utf-8')

    def write_archives(self, wheel_name=None, wheel_version=None, source_version=None):
        for path in self.dist.iterdir():
            path.unlink()
        wheel = self.dist / f'{self.project}-{self.version}-py3-none-any.whl'
        with zipfile.ZipFile(wheel, 'w') as archive:
            metadata = f'Metadata-Version: 2.4\nName: {wheel_name or self.project}\nVersion: {wheel_version or self.version}\n'
            archive.writestr(f'{self.project}-{self.version}.dist-info/METADATA', metadata)
        source = self.dist / f'{self.project}-{self.version}.tar.gz'
        with tarfile.open(source, 'w:gz') as archive:
            metadata = f'Metadata-Version: 2.4\nName: {self.project}\nVersion: {source_version or self.version}\n'.encode()
            info = tarfile.TarInfo(f'{self.project}-{self.version}/PKG-INFO')
            info.size = len(metadata)
            archive.addfile(info, io.BytesIO(metadata))

    def set_tag(self, sha=SHA):
        self.client.tag = {'ref': f'refs/tags/{self.version}', 'object': {'type': 'commit', 'sha': sha}}

    def set_uploaded(self, count=2):
        artifacts = release.read_artifacts(self.dist, self.project, self.version)
        self.client.version_record = {
            'info': {'name': self.project, 'version': self.version},
            'urls': [{'filename': name, 'digests': {'sha256': artifact.sha256}}
                     for name, artifact in list(artifacts.items())[:count]],
        }
        return artifacts

    def plan(self):
        return release.plan_release(self.project, self.branch, self.dist, self.event, REPOSITORY, self.root, self.client)

    def stage(self):
        return release.stage_release(self.project, self.branch, self.dist, self.event, REPOSITORY, self.root, self.client)

    def select_artifact(self):
        return release.select_artifact(self.branch, self.event, REPOSITORY, self.root, self.client)

    def set_workflow_artifacts(self, attempts):
        self.client.artifact_listing = {
            'total_count': len(attempts),
            'artifacts': [{'name': f'python-distributions-{number}', 'expired': False,
                           'workflow_run': {'head_sha': SHA}} for number in attempts],
        }

    def test_new_release_plan_is_read_only_and_accepts_external_dist_directory(self):
        plan = self.plan()
        self.assertTrue(plan.should_publish)
        self.assertEqual(plan.outputs(), {'should_publish': 'true', 'version': '1.1.0', 'tag': '1.1.0', 'source_sha': SHA})
        self.assertTrue(all(method == 'GET' for method, _, _ in self.client.calls))
        self.assertEqual(len(list(self.dist.iterdir())), 2)

    def test_calango_main_uses_the_same_release_contract(self):
        self.project, self.branch = 'calango', 'main'
        self.event['workflow_run']['head_branch'] = self.branch
        self.client.latest['info']['name'] = self.project
        self.write_source()
        self.write_archives()
        self.assertTrue(self.plan().should_publish)
        self.assertIn(('GET', 'pypi/calango/1.1.0', None), self.client.calls)

    def test_invalid_runs_are_rejected_before_network_access(self):
        invalid = [('name', 'Publish'), ('event', 'pull_request'), ('head_branch', 'develop'),
                   ('conclusion', 'failure'), ('status', 'in_progress'), ('head_sha', 'invalid'),
                   ('head_repository', {'full_name': 'other/fork'}), ('head_repository', None)]
        original = copy.deepcopy(self.event)
        for field, value in invalid:
            with self.subTest(field=field):
                self.event = copy.deepcopy(original)
                self.event['workflow_run'][field] = value
                with self.assertRaises(release.ReleaseError):
                    self.plan()
                self.assertEqual(self.client.calls, [])

    def test_checkout_and_ancestry_must_match_the_tested_commit(self):
        self.git.side_effect = [subprocess.CompletedProcess([], 0, OTHER_SHA, '')]
        with self.assertRaisesRegex(release.ReleaseError, 'HEAD'):
            self.plan()
        self.git.side_effect = [subprocess.CompletedProcess([], 0, SHA, ''), subprocess.CompletedProcess([], 1, '', '')]
        with self.assertRaisesRegex(release.ReleaseError, 'origin/master'):
            self.plan()
        self.assertEqual(self.client.calls, [])

    def test_version_ast_is_not_executed_and_both_representations_must_match(self):
        path = self.root / self.project / '_version.py'
        path.write_text('raise RuntimeError("never execute")\nVERSION="1.1.0.final.0"\n__version__="1.1.0"\n')
        self.assertEqual(release.read_version(self.root, self.project), '1.1.0')
        for source in ('VERSION="1.0.0.final.0"\n__version__="1.1.0"',
                       'VERSION="1.1.0rc1.final.0"\n__version__="1.1.0rc1"',
                       'VERSION="1.1.0.final.0"\n__version__=str("1.1.0")'):
            with self.subTest(source=source), self.assertRaises(release.ReleaseError):
                path.write_text(source)
                release.read_version(self.root, self.project)

    def test_archive_metadata_must_match_project_and_source_version(self):
        for kwargs in ({'wheel_name': 'other'}, {'wheel_version': '1.0.0'}, {'source_version': '1.0.0'}):
            with self.subTest(kwargs=kwargs):
                self.write_archives(**kwargs)
                with self.assertRaisesRegex(release.ReleaseError, 'Name/Version'):
                    self.plan()
        self.assertEqual(self.client.calls, [])

    def test_distribution_directory_rejects_extra_files_without_deleting_them(self):
        extra = self.dist / 'unrelated.txt'
        extra.write_text('keep me')
        with self.assertRaises(release.ReleaseError):
            self.plan()
        self.assertEqual(extra.read_text(), 'keep me')

    def test_distribution_directory_rejects_symlinks(self):
        link = self.folder / 'linked-artifacts'
        try:
            link.symlink_to(self.dist, target_is_directory=True)
        except OSError:
            self.skipTest('Creating symlinks is unavailable on this host')
        with self.assertRaises(release.ReleaseError):
            release.read_artifacts(link, self.project, self.version)

    def test_artifact_selection_reuses_producer_on_failed_jobs_retry(self):
        self.event['workflow_run']['run_attempt'] = 2
        self.set_workflow_artifacts([1])
        self.assertEqual(self.select_artifact(), {'artifact_name': 'python-distributions-1'})
        self.set_workflow_artifacts([1, 2])
        self.assertEqual(self.select_artifact(), {'artifact_name': 'python-distributions-2'})
        self.event['workflow_run']['run_attempt'] = 1
        self.assertEqual(self.select_artifact(), {'artifact_name': 'python-distributions-1'})
        self.assertTrue(all(method == 'GET' for method, _, _ in self.client.calls))

    def test_artifact_selection_rejects_missing_expired_or_wrong_commit(self):
        with self.assertRaisesRegex(release.ReleaseError, 'No distribution'):
            self.select_artifact()
        self.event['workflow_run']['run_attempt'] = 2
        self.set_workflow_artifacts([1, 2])
        selected = self.client.artifact_listing['artifacts'][1]
        selected['expired'] = True
        with self.assertRaisesRegex(release.ReleaseError, 'expired'):
            self.select_artifact()
        selected['expired'] = False
        selected['workflow_run']['head_sha'] = OTHER_SHA
        with self.assertRaisesRegex(release.ReleaseError, 'another commit'):
            self.select_artifact()

    def test_artifact_selection_rejects_ambiguous_or_unbounded_listing_and_invalid_run_ids(self):
        self.set_workflow_artifacts([1, 1])
        with self.assertRaisesRegex(release.ReleaseError, 'same attempt'):
            self.select_artifact()
        self.client.artifact_listing['total_count'] = 101
        with self.assertRaisesRegex(release.ReleaseError, '100 workflow'):
            self.select_artifact()
        for field, value in [('id', -1), ('id', '42'), ('run_attempt', True), ('run_attempt', 0)]:
            with self.subTest(field=field, value=value):
                original = self.event['workflow_run'][field]
                self.event['workflow_run'][field] = value
                with self.assertRaisesRegex(release.ReleaseError, 'positive integers'):
                    self.select_artifact()
                self.event['workflow_run'][field] = original

    def test_artifact_cli_needs_no_distribution_directory(self):
        self.set_workflow_artifacts([1])
        event = self.folder / 'event.json'
        event.write_text(json.dumps(self.event))
        outputs = self.folder / 'github-output'
        with patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event), 'GITHUB_REPOSITORY': REPOSITORY,
                                     'GITHUB_TOKEN': 'test-token', 'GITHUB_OUTPUT': str(outputs)}), \
                patch.object(release.Path, 'cwd', return_value=self.root), \
                patch.object(release, 'Client', return_value=self.client), patch('sys.stdout', new_callable=io.StringIO):
            result = release.main(['artifact', '--project', 'cereja', '--branch', 'master'])
        self.assertEqual(result, 0)
        self.assertEqual(outputs.read_text().splitlines(), ['artifact_name=python-distributions-1'])

    def test_existing_pypi_version_without_matching_tag_is_a_no_op(self):
        self.set_uploaded()
        for tag in (None, OTHER_SHA):
            with self.subTest(tag=tag):
                self.client.calls.clear()
                if tag:
                    self.set_tag(tag)
                else:
                    self.client.tag = None
                plan = self.stage()
                self.assertFalse(plan.should_publish)
                self.assertTrue(all(method == 'GET' for method, _, _ in self.client.calls))
                self.assertEqual(len(list(self.dist.iterdir())), 2)

    def test_tag_collision_fails_for_missing_or_partial_version(self):
        self.set_tag(OTHER_SHA)
        with self.assertRaisesRegex(release.ReleaseError, 'another commit'):
            self.stage()
        self.set_uploaded(count=1)
        with self.assertRaisesRegex(release.ReleaseError, 'different commit'):
            self.stage()
        self.assertTrue(all(method == 'GET' for method, _, _ in self.client.calls))

    def test_older_or_unchanged_unpublished_version_is_rejected(self):
        for latest in ('1.1.0', '2.0.0'):
            with self.subTest(latest=latest):
                self.client.latest['info']['version'] = latest
                with self.assertRaisesRegex(release.ReleaseError, 'newer'):
                    self.plan()

    def test_version_comparison_is_numeric_and_first_release_is_allowed(self):
        self.version = '2.10.0'
        self.write_source()
        self.write_archives()
        self.client.latest['info']['version'] = '2.9.0'
        self.assertTrue(self.plan().should_publish)
        self.client.latest = None
        self.assertTrue(self.plan().should_publish)

    def test_matching_tag_and_complete_identical_uploads_are_a_no_op(self):
        self.set_tag()
        self.set_uploaded()
        self.assertFalse(self.stage().should_publish)
        self.assertTrue(all(method == 'GET' for method, _, _ in self.client.calls))
        self.assertEqual(len(list(self.dist.iterdir())), 2)

    def test_partial_retry_keeps_only_missing_file_and_reuses_tag_and_release(self):
        self.set_tag()
        artifacts = self.set_uploaded(count=1)
        uploaded_name = self.client.version_record['urls'][0]['filename']
        self.client.latest['info']['version'] = self.version
        self.client.release = {'tag_name': self.version, 'id': 99}
        plan = self.stage()
        self.assertTrue(plan.should_publish)
        self.assertEqual({path.name for path in self.dist.iterdir()}, set(artifacts) - {uploaded_name})
        self.assertTrue(all(method == 'GET' for method, _, _ in self.client.calls))

    def test_partial_retry_rejects_modified_or_unknown_pypi_artifact(self):
        self.set_tag()
        for mutation in ('digest', 'filename'):
            with self.subTest(mutation=mutation):
                self.set_uploaded(count=1)
                uploaded = self.client.version_record['urls'][0]
                if mutation == 'digest':
                    uploaded['digests']['sha256'] = 'f' * 64
                else:
                    uploaded['filename'] = 'unknown.whl'
                with self.assertRaisesRegex(release.ReleaseError, 'original artifacts'):
                    self.stage()
                self.assertEqual(len(list(self.dist.iterdir())), 2)

    def test_partial_retry_may_finish_after_a_newer_version_was_published(self):
        self.set_tag()
        self.client.latest['info']['version'] = '2.0.0'
        self.set_uploaded(count=0)
        with self.assertRaisesRegex(release.ReleaseError, 'newer'):
            self.stage()
        artifacts = self.set_uploaded(count=1)
        uploaded_name = self.client.version_record['urls'][0]['filename']
        self.assertTrue(self.stage().should_publish)
        self.assertEqual({path.name for path in self.dist.iterdir()}, set(artifacts) - {uploaded_name})

    def test_stage_creates_exact_tag_then_release_with_generated_notes(self):
        self.assertTrue(self.stage().should_publish)
        mutations = [(path, data) for method, path, data in self.client.calls if method == 'POST']
        self.assertEqual(mutations[0], (f'/repos/{REPOSITORY}/git/refs', {'ref': 'refs/tags/1.1.0', 'sha': SHA}))
        self.assertEqual(mutations[1][0], f'/repos/{REPOSITORY}/releases')
        self.assertTrue(mutations[1][1]['generate_release_notes'])
        self.assertEqual(mutations[1][1]['make_latest'], 'legacy')
        self.assertEqual(mutations[1][1]['target_commitish'], SHA)
        self.assertEqual(len(list(self.dist.iterdir())), 2)

    def test_annotated_tag_resolves_to_the_tested_commit(self):
        self.client.tag = {'ref': f'refs/tags/{self.version}', 'object': {'type': 'tag', 'sha': OTHER_SHA}}
        self.client.annotations[OTHER_SHA] = {'object': {'type': 'commit', 'sha': SHA}}
        self.assertTrue(self.plan().should_publish)
        self.assertIn(('GET', f'/repos/{REPOSITORY}/git/tags/{OTHER_SHA}', None), self.client.calls)

    def test_cli_writes_expected_outputs_without_native_imports_or_mutation(self):
        event = self.folder / 'event.json'
        event.write_text(json.dumps(self.event))
        outputs = self.folder / 'github-output'
        with patch.dict(os.environ, {'GITHUB_EVENT_PATH': str(event), 'GITHUB_REPOSITORY': REPOSITORY,
                                     'GITHUB_TOKEN': 'test-token', 'GITHUB_OUTPUT': str(outputs)}), \
                patch.object(release.Path, 'cwd', return_value=self.root), \
                patch.object(release, 'Client', return_value=self.client), patch('sys.stdout', new_callable=io.StringIO):
            result = release.main(['plan', '--project', 'cereja', '--branch', 'master', '--dist', str(self.dist)])
        self.assertEqual(result, 0)
        self.assertEqual(outputs.read_text().splitlines(), [
            'should_publish=true', 'version=1.1.0', 'tag=1.1.0', 'source_sha=' + SHA,
        ])


class TestReleaseHTTP(unittest.TestCase):
    def test_only_get_404_is_absence_and_other_failures_abort(self):
        client = release.Client('secret-test-token')
        for code in (401, 403, 409, 429, 500):
            error = HTTPError('https://test', code, '', {}, None)
            with self.subTest(code=code), patch.object(release, 'urlopen', side_effect=error):
                with self.assertRaises(release.ReleaseError):
                    client.pypi('cereja', '1.1.0')
        with patch.object(release, 'urlopen', side_effect=HTTPError('https://test', 404, '', {}, None)):
            self.assertIsNone(client.pypi('cereja', '1.1.0'))
            with self.assertRaises(release.ReleaseError):
                client.github('/repos/owner/repo/git/refs', method='POST', data={})
        with patch.object(release, 'urlopen', side_effect=URLError('connection lost')):
            with self.assertRaises(release.ReleaseError):
                client.pypi('cereja')

    def test_requests_have_timeout_and_github_token_is_not_sent_to_pypi(self):
        observed = []

        def response(request, timeout):
            observed.append((request, timeout))
            return io.BytesIO(b'{}')

        with patch.object(release, 'urlopen', side_effect=response):
            client = release.Client('secret-test-token')
            client.github('/repos/owner/repo/git/ref/tags/1.1.0')
            client.pypi('cereja', '1.1.0')
        self.assertEqual([timeout for _, timeout in observed], [30, 30])
        self.assertEqual(observed[0][0].get_header('Authorization'), 'Bearer secret-test-token')
        self.assertIsNone(observed[1][0].get_header('Authorization'))


if __name__ == '__main__':
    unittest.main()
