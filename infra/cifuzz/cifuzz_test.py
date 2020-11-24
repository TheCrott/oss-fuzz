# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests the functionality of the cifuzz module's functions:
1. Building fuzzers.
2. Running fuzzers.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import parameterized

# pylint: disable=wrong-import-position
INFRA_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(INFRA_DIR)

OSS_FUZZ_DIR = os.path.dirname(INFRA_DIR)

import cifuzz
import fuzz_target
import test_helpers

# NOTE: This integration test relies on
# https://github.com/google/oss-fuzz/tree/master/projects/example project.
EXAMPLE_PROJECT = 'example'

# Location of files used for testing.
TEST_FILES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'test_files')

# An example fuzzer that triggers an crash.
# Binary is a copy of the example project's do_stuff_fuzzer and can be
# generated by running "python3 infra/helper.py build_fuzzers example".
EXAMPLE_CRASH_FUZZER = 'example_crash_fuzzer'

# An example fuzzer that does not trigger a crash.
# Binary is a modified version of example project's do_stuff_fuzzer. It is
# created by removing the bug in my_api.cpp.
EXAMPLE_NOCRASH_FUZZER = 'example_nocrash_fuzzer'

# A fuzzer to be built in build_fuzzers integration tests.
EXAMPLE_BUILD_FUZZER = 'do_stuff_fuzzer'

MEMORY_FUZZER_DIR = os.path.join(TEST_FILES_PATH, 'memory')
MEMORY_FUZZER = 'curl_fuzzer_memory'

UNDEFINED_FUZZER_DIR = os.path.join(TEST_FILES_PATH, 'undefined')
UNDEFINED_FUZZER = 'curl_fuzzer_undefined'

# pylint: disable=no-self-use


class BuildFuzzersTest(unittest.TestCase):
  """Unit tests for build_fuzzers."""

  @mock.patch('build_specified_commit.detect_main_repo',
              return_value=('example.com', '/path'))
  @mock.patch('repo_manager.RepoManager', return_value=None)
  @mock.patch('cifuzz.checkout_specified_commit')
  @mock.patch('helper.docker_run')
  def test_cifuzz_env_var(self, mocked_docker_run, _, __, ___):
    """Tests that the CIFUZZ env var is set."""

    with tempfile.TemporaryDirectory() as tmp_dir:
      cifuzz.build_fuzzers(EXAMPLE_PROJECT,
                           EXAMPLE_PROJECT,
                           tmp_dir,
                           pr_ref='refs/pull/1757/merge')
    docker_run_command = mocked_docker_run.call_args_list[0][0][0]

    def command_has_env_var_arg(command, env_var_arg):
      for idx, element in enumerate(command):
        if idx == 0:
          continue

        if element == env_var_arg and command[idx - 1] == '-e':
          return True
      return False

    self.assertTrue(command_has_env_var_arg(docker_run_command, 'CIFUZZ=True'))


class BuildFuzzersIntegrationTest(unittest.TestCase):
  """Integration tests for build_fuzzers."""

  def setUp(self):
    test_helpers.patch_environ(self)

  def test_external_project(self):
    """Tests building fuzzers from an external project."""
    project_name = 'external-project'
    project_src_path = os.path.join(TEST_FILES_PATH, project_name)
    # with tempfile.TemporaryDirectory() as tmp_dir:
    # project_src_path = os.path.join(tmp_dir, project_name)
    # shutil.copytree(project_src_path_src, project_src_path)
    # project_src_path = project_src_path_dst
    build_integration_path = os.path.join(project_src_path, 'oss-fuzz')
    os.environ['PROJECT_SRC_PATH'] = project_src_path
    os.environ['BUILD_INTEGRATION_PATH'] = build_integration_path
    commit_sha = '0b95fe1039ed7c38fea1f97078316bfc1030c523'
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      self.assertTrue(
          cifuzz.build_fuzzers(project_name,
                               project_name,
                               tmp_dir,
                               commit_sha=commit_sha))
      self.assertTrue(
          os.path.exists(os.path.join(out_path, EXAMPLE_BUILD_FUZZER)))

  def test_valid_commit(self):
    """Tests building fuzzers with valid inputs."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      self.assertTrue(
          cifuzz.build_fuzzers(
              EXAMPLE_PROJECT,
              'oss-fuzz',
              tmp_dir,
              commit_sha='0b95fe1039ed7c38fea1f97078316bfc1030c523'))
      self.assertTrue(
          os.path.exists(os.path.join(out_path, EXAMPLE_BUILD_FUZZER)))

  def test_valid_pull_request(self):
    """Tests building fuzzers with valid pull request."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      self.assertTrue(
          cifuzz.build_fuzzers(EXAMPLE_PROJECT,
                               'oss-fuzz',
                               tmp_dir,
                               pr_ref='refs/pull/1757/merge'))
      self.assertTrue(
          os.path.exists(os.path.join(out_path, EXAMPLE_BUILD_FUZZER)))

  def test_invalid_pull_request(self):
    """Tests building fuzzers with invalid pull request."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      self.assertTrue(
          cifuzz.build_fuzzers(EXAMPLE_PROJECT,
                               'oss-fuzz',
                               tmp_dir,
                               pr_ref='ref-1/merge'))

  def test_invalid_project_name(self):
    """Tests building fuzzers with invalid project name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      self.assertFalse(
          cifuzz.build_fuzzers(
              'not_a_valid_project',
              'oss-fuzz',
              tmp_dir,
              commit_sha='0b95fe1039ed7c38fea1f97078316bfc1030c523'))

  def test_invalid_repo_name(self):
    """Tests building fuzzers with invalid repo name."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      self.assertFalse(
          cifuzz.build_fuzzers(
              EXAMPLE_PROJECT,
              'not-real-repo',
              tmp_dir,
              commit_sha='0b95fe1039ed7c38fea1f97078316bfc1030c523'))

  def test_invalid_commit_sha(self):
    """Tests building fuzzers with invalid commit SHA."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      with self.assertRaises(AssertionError):
        cifuzz.build_fuzzers(EXAMPLE_PROJECT,
                             'oss-fuzz',
                             tmp_dir,
                             commit_sha='')

  def test_invalid_workspace(self):
    """Tests building fuzzers with invalid workspace."""
    self.assertFalse(
        cifuzz.build_fuzzers(
            EXAMPLE_PROJECT,
            'oss-fuzz',
            'not/a/dir',
            commit_sha='0b95fe1039ed7c38fea1f97078316bfc1030c523',
        ))


def remove_test_files(out_parent_dir, allowlist):
  """Removes test files from |out_parent_dir| that are not in |allowlist|, a
  list of files with paths relative to the out directory."""
  out_dir = os.path.join(out_parent_dir, 'out')
  allowlist = set(allowlist)
  for rel_out_path in os.listdir(out_dir):
    if rel_out_path in allowlist:
      continue
    path_to_remove = os.path.join(out_dir, rel_out_path)
    if os.path.isdir(path_to_remove):
      shutil.rmtree(path_to_remove)
    else:
      os.remove(path_to_remove)


class RunFuzzerIntegrationTestMixin:  # pylint: disable=too-few-public-methods,invalid-name
  """Mixin for integration test classes that runbuild_fuzzers on builds of a
  specific sanitizer."""
  # These must be defined by children.
  FUZZER_DIR = None
  FUZZER = None

  def tearDown(self):
    """Removes any existing crashes and test files."""
    remove_test_files(self.FUZZER_DIR, self.FUZZER)

  def _test_run_with_sanitizer(self, fuzzer_dir, sanitizer):
    """Calls run_fuzzers on fuzzer_dir and |sanitizer| and asserts
    the run succeeded and that no bug was found."""
    run_success, bug_found = cifuzz.run_fuzzers(10,
                                                fuzzer_dir,
                                                'curl',
                                                sanitizer=sanitizer)
    self.assertTrue(run_success)
    self.assertFalse(bug_found)


class RunMemoryFuzzerIntegrationTest(unittest.TestCase,
                                     RunFuzzerIntegrationTestMixin):
  """Integration test for build_fuzzers with an MSAN build."""
  FUZZER_DIR = MEMORY_FUZZER_DIR
  FUZZER = MEMORY_FUZZER

  def test_run_with_memory_sanitizer(self):
    """Tests run_fuzzers with a valid MSAN build."""
    self._test_run_with_sanitizer(self.FUZZER_DIR, 'memory')


class RunUndefinedFuzzerIntegrationTest(unittest.TestCase,
                                        RunFuzzerIntegrationTestMixin):
  """Integration test for build_fuzzers with an UBSAN build."""
  FUZZER_DIR = UNDEFINED_FUZZER_DIR
  FUZZER = UNDEFINED_FUZZER

  def test_run_with_undefined_sanitizer(self):
    """Tests run_fuzzers with a valid MSAN build."""
    self._test_run_with_sanitizer(self.FUZZER_DIR, 'undefined')


class RunAddressFuzzersIntegrationTest(unittest.TestCase):
  """Integration tests for build_fuzzers with an ASAN build."""

  def tearDown(self):
    """Removes any existing crashes and test files."""
    files_to_keep = [
        'undefined', 'memory', EXAMPLE_CRASH_FUZZER, EXAMPLE_NOCRASH_FUZZER
    ]
    remove_test_files(TEST_FILES_PATH, files_to_keep)

  def test_new_bug_found(self):
    """Tests run_fuzzers with a valid ASAN build."""
    # Set the first return value to True, then the second to False to
    # emulate a bug existing in the current PR but not on the downloaded
    # OSS-Fuzz build.
    with mock.patch.object(fuzz_target.FuzzTarget,
                           'is_reproducible',
                           side_effect=[True, False]):
      run_success, bug_found = cifuzz.run_fuzzers(10, TEST_FILES_PATH,
                                                  EXAMPLE_PROJECT)
      build_dir = os.path.join(TEST_FILES_PATH, 'out', 'oss_fuzz_latest')
      self.assertTrue(os.path.exists(build_dir))
      self.assertNotEqual(0, len(os.listdir(build_dir)))
      self.assertTrue(run_success)
      self.assertTrue(bug_found)

  def test_old_bug_found(self):
    """Tests run_fuzzers with a bug found in OSS-Fuzz before."""
    with mock.patch.object(fuzz_target.FuzzTarget,
                           'is_reproducible',
                           side_effect=[True, True]):
      run_success, bug_found = cifuzz.run_fuzzers(10, TEST_FILES_PATH,
                                                  EXAMPLE_PROJECT)
      build_dir = os.path.join(TEST_FILES_PATH, 'out', 'oss_fuzz_latest')
      self.assertTrue(os.path.exists(build_dir))
      self.assertNotEqual(0, len(os.listdir(build_dir)))
      self.assertTrue(run_success)
      self.assertFalse(bug_found)

  def test_invalid_build(self):
    """Tests run_fuzzers with an invalid ASAN build."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      run_success, bug_found = cifuzz.run_fuzzers(10, tmp_dir, EXAMPLE_PROJECT)
    self.assertFalse(run_success)
    self.assertFalse(bug_found)

  def test_invalid_fuzz_seconds(self):
    """Tests run_fuzzers with an invalid fuzz seconds."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      out_path = os.path.join(tmp_dir, 'out')
      os.mkdir(out_path)
      run_success, bug_found = cifuzz.run_fuzzers(0, tmp_dir, EXAMPLE_PROJECT)
    self.assertFalse(run_success)
    self.assertFalse(bug_found)

  def test_invalid_out_dir(self):
    """Tests run_fuzzers with an invalid out directory."""
    run_success, bug_found = cifuzz.run_fuzzers(10, 'not/a/valid/path',
                                                EXAMPLE_PROJECT)
    self.assertFalse(run_success)
    self.assertFalse(bug_found)


class ParseOutputTest(unittest.TestCase):
  """Tests parse_fuzzer_output."""

  def test_parse_valid_output(self):
    """Checks that the parse fuzzer output can correctly parse output."""
    test_output_path = os.path.join(TEST_FILES_PATH,
                                    'example_crash_fuzzer_output.txt')
    test_summary_path = os.path.join(TEST_FILES_PATH, 'bug_summary_example.txt')
    with tempfile.TemporaryDirectory() as tmp_dir:
      with open(test_output_path, 'rb') as test_fuzz_output:
        cifuzz.parse_fuzzer_output(test_fuzz_output.read(), tmp_dir)
      result_files = ['bug_summary.txt']
      self.assertCountEqual(os.listdir(tmp_dir), result_files)

      # Compare the bug summaries.
      with open(os.path.join(tmp_dir, 'bug_summary.txt')) as bug_summary:
        detected_summary = bug_summary.read()
      with open(test_summary_path) as bug_summary:
        real_summary = bug_summary.read()
      self.assertEqual(detected_summary, real_summary)

  def test_parse_invalid_output(self):
    """Checks that no files are created when an invalid input was given."""
    with tempfile.TemporaryDirectory() as tmp_dir:
      cifuzz.parse_fuzzer_output(b'not a valid output_string', tmp_dir)
      self.assertEqual(len(os.listdir(tmp_dir)), 0)


class CheckFuzzerBuildTest(unittest.TestCase):
  """Tests the check_fuzzer_build function in the cifuzz module."""

  def test_correct_fuzzer_build(self):
    """Checks check_fuzzer_build function returns True for valid fuzzers."""
    test_fuzzer_dir = os.path.join(TEST_FILES_PATH, 'out')
    self.assertTrue(cifuzz.check_fuzzer_build(test_fuzzer_dir))

  def test_not_a_valid_fuzz_path(self):
    """Tests that False is returned when a bad path is given."""
    self.assertFalse(cifuzz.check_fuzzer_build('not/a/valid/path'))

  def test_not_a_valid_fuzzer(self):
    """Checks a directory that exists but does not have fuzzers is False."""
    self.assertFalse(cifuzz.check_fuzzer_build(TEST_FILES_PATH))

  @mock.patch.dict(os.environ, {'ALLOWED_BROKEN_TARGETS_PERCENTAGE': '0'})
  @mock.patch('helper.docker_run')
  def test_allow_broken_fuzz_targets_percentage(self, mocked_docker_run):
    """Tests that ALLOWED_BROKEN_TARGETS_PERCENTAGE is set when running
    docker if it is set in the environment."""
    mocked_docker_run.return_value = 0
    test_fuzzer_dir = os.path.join(TEST_FILES_PATH, 'out')
    cifuzz.check_fuzzer_build(test_fuzzer_dir)
    self.assertIn('-e ALLOWED_BROKEN_TARGETS_PERCENTAGE=0',
                  ' '.join(mocked_docker_run.call_args[0][0]))


class GetFilesCoveredByTargetTest(unittest.TestCase):
  """Tests get_files_covered_by_target."""

  example_cov_json = 'example_curl_cov.json'
  example_fuzzer_cov_json = 'example_curl_fuzzer_cov.json'
  example_fuzzer = 'curl_fuzzer'

  def setUp(self):
    with open(os.path.join(TEST_FILES_PATH,
                           self.example_cov_json)) as file_handle:
      self.proj_cov_report_example = json.loads(file_handle.read())
    with open(os.path.join(TEST_FILES_PATH,
                           self.example_fuzzer_cov_json)) as file_handle:
      self.fuzzer_cov_report_example = json.loads(file_handle.read())

  def test_valid_target(self):
    """Tests that covered files can be retrieved from a coverage report."""

    with mock.patch.object(cifuzz,
                           'get_target_coverage_report',
                           return_value=self.fuzzer_cov_report_example):
      file_list = cifuzz.get_files_covered_by_target(
          self.proj_cov_report_example, self.example_fuzzer, '/src/curl')

    curl_files_list_path = os.path.join(TEST_FILES_PATH,
                                        'example_curl_file_list.json')
    with open(curl_files_list_path) as file_handle:
      true_files_list = json.load(file_handle)
    self.assertCountEqual(file_list, true_files_list)

  def test_invalid_target(self):
    """Tests passing invalid fuzz target returns None."""
    self.assertIsNone(
        cifuzz.get_files_covered_by_target(self.proj_cov_report_example,
                                           'not-a-fuzzer', '/src/curl'))
    self.assertIsNone(
        cifuzz.get_files_covered_by_target(self.proj_cov_report_example, '',
                                           '/src/curl'))

  def test_invalid_project_build_dir(self):
    """Tests passing an invalid build directory returns None."""
    self.assertIsNone(
        cifuzz.get_files_covered_by_target(self.proj_cov_report_example,
                                           self.example_fuzzer, '/no/pe'))
    self.assertIsNone(
        cifuzz.get_files_covered_by_target(self.proj_cov_report_example,
                                           self.example_fuzzer, ''))


class GetTargetCoverageReportTest(unittest.TestCase):
  """Tests get_target_coverage_report."""

  example_cov_json = 'example_curl_cov.json'
  example_fuzzer = 'curl_fuzzer'

  def setUp(self):
    with open(os.path.join(TEST_FILES_PATH, self.example_cov_json),
              'r') as file_handle:
      self.example_cov = json.loads(file_handle.read())

  def test_valid_target(self):
    """Tests that a target's coverage report can be downloaded and parsed."""
    with mock.patch.object(cifuzz, 'get_json_from_url',
                           return_value='{}') as mock_get_json:
      cifuzz.get_target_coverage_report(self.example_cov, self.example_fuzzer)
      (url,), _ = mock_get_json.call_args
      self.assertEqual(
          'https://storage.googleapis.com/oss-fuzz-coverage/'
          'curl/fuzzer_stats/20200226/curl_fuzzer.json', url)

  def test_invalid_target(self):
    """Tests that passing an invalid target coverage report returns None."""
    self.assertIsNone(
        cifuzz.get_target_coverage_report(self.example_cov, 'not-valid-target'))
    self.assertIsNone(cifuzz.get_target_coverage_report(self.example_cov, ''))

  def test_invalid_project_json(self):
    """Tests that passing an invalid project json coverage report returns
    None."""
    self.assertIsNone(
        cifuzz.get_target_coverage_report('not-a-proj', self.example_fuzzer))
    self.assertIsNone(cifuzz.get_target_coverage_report('',
                                                        self.example_fuzzer))


class GetLatestCoverageReportTest(unittest.TestCase):
  """Tests get_latest_cov_report_info."""

  test_project = 'curl'

  def test_get_valid_project(self):
    """Tests that a project's coverage report can be downloaded and parsed.

    NOTE: This test relies on the test_project repo's coverage report.
    The "example" project was not used because it has no coverage reports.
    """
    with mock.patch.object(cifuzz, 'get_json_from_url',
                           return_value='{}') as mock_fun:

      cifuzz.get_latest_cov_report_info(self.test_project)
      (url,), _ = mock_fun.call_args
      self.assertEqual(
          'https://storage.googleapis.com/oss-fuzz-coverage/'
          'latest_report_info/curl.json', url)

  def test_get_invalid_project(self):
    """Tests that passing a bad project returns None."""
    self.assertIsNone(cifuzz.get_latest_cov_report_info('not-a-proj'))
    self.assertIsNone(cifuzz.get_latest_cov_report_info(''))


EXAMPLE_FILE_CHANGED = 'test.txt'


class RemoveUnaffectedFuzzersTest(unittest.TestCase):
  """Tests remove_unaffected_fuzzers."""

  TEST_FUZZER_1 = os.path.join(TEST_FILES_PATH, 'out', 'example_crash_fuzzer')
  TEST_FUZZER_2 = os.path.join(TEST_FILES_PATH, 'out', 'example_nocrash_fuzzer')

  # yapf: disable
  @parameterized.parameterized.expand([
      # Tests a specific affected fuzzers is kept.
      ([[EXAMPLE_FILE_CHANGED], None], 2,),

      # Tests specific affected fuzzer is kept.
      ([[EXAMPLE_FILE_CHANGED], ['not/a/real/file']], 1),

      # Tests all fuzzers are kept if none are deemed affected.
      ([None, None], 2),

      # Tests that multiple fuzzers are kept if multiple fuzzers are affected.
      ([[EXAMPLE_FILE_CHANGED], [EXAMPLE_FILE_CHANGED]], 2),
      ])
  # yapf: enable
  def test_remove_unaffected_fuzzers(self, side_effect, expected_dir_len):
    """Tests that remove_unaffected_fuzzers has the intended effect."""
    with tempfile.TemporaryDirectory() as tmp_dir, mock.patch(
        'cifuzz.get_latest_cov_report_info', return_value=1):
      with mock.patch.object(cifuzz,
                             'get_files_covered_by_target') as mocked_get_files:
        mocked_get_files.side_effect = side_effect
        shutil.copy(self.TEST_FUZZER_1, tmp_dir)
        shutil.copy(self.TEST_FUZZER_2, tmp_dir)
        cifuzz.remove_unaffected_fuzzers(EXAMPLE_PROJECT, tmp_dir,
                                         [EXAMPLE_FILE_CHANGED], '')
        self.assertEqual(expected_dir_len, len(os.listdir(tmp_dir)))


@unittest.skip('Test is too long to be run with presubmit.')
class BuildSantizerIntegrationTest(unittest.TestCase):
  """Integration tests for the build_fuzzers.
    Note: This test relies on "curl" being an OSS-Fuzz project."""

  def test_valid_project_curl_memory(self):
    """Tests that MSAN can be detected from project.yaml"""
    with tempfile.TemporaryDirectory() as tmp_dir:
      self.assertTrue(
          cifuzz.build_fuzzers('curl',
                               'curl',
                               tmp_dir,
                               pr_ref='fake_pr',
                               sanitizer='memory'))

  def test_valid_project_curl_undefined(self):
    """Test that UBSAN can be detected from project.yaml"""
    with tempfile.TemporaryDirectory() as tmp_dir:
      self.assertTrue(
          cifuzz.build_fuzzers('curl',
                               'curl',
                               tmp_dir,
                               pr_ref='fake_pr',
                               sanitizer='undefined'))


if __name__ == '__main__':
  unittest.main()
