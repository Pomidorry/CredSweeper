import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import AnyStr, Tuple
from unittest import TestCase

import deepdiff
import numpy as np
import pandas as pd
import pytest

from credsweeper.app import APP_PATH
from credsweeper.utils.util import Util
from tests import AZ_STRING, SAMPLES_POST_CRED_COUNT, SAMPLES_IN_DEEP_3, SAMPLES_PATH, \
    TESTS_PATH, SAMPLES_FILTERED_COUNT, SAMPLES_IN_DOC, NEGLIGIBLE_ML_THRESHOLD, SAMPLE_ZIP


class TestApp(TestCase):

    def setUp(self):
        self.maxDiff = None

    @staticmethod
    def _m_credsweeper(args) -> Tuple[str, str]:
        with subprocess.Popen(
                args=[sys.executable, "-m", "credsweeper", *args],  #
                cwd=APP_PATH.parent,  #
                stdout=subprocess.PIPE,  #
                stderr=subprocess.PIPE) as proc:
            _stdout, _stderr = proc.communicate()

        def transform(x: AnyStr) -> str:
            if isinstance(x, bytes):
                return x.decode(errors='replace')
            elif isinstance(x, str):
                return x
            else:
                raise ValueError(f"Unknown type: {type(x)}")

        return transform(_stdout), transform(_stderr)

    def test_it_works_p(self) -> None:
        target_path = str(SAMPLES_PATH / "uuid")
        _stdout, _stderr = self._m_credsweeper(["--path", target_path, "--log", "silence"])
        output = " ".join(_stdout.split()[:-1])

        expected = f"""
                    rule: UUID
                    | severity: info
                    | confidence: strong
                    | ml_probability: None
                    | line_data_list:
                        [path: {target_path}
                        | line_num: 1
                        | value: 'bace4d19-fa7e-beef-cafe-9129474bcd81'
                        | line: 'bace4d19-fa7e-beef-cafe-9129474bcd81 # tp']
                    Detected Credentials: 1
                    Time Elapsed:
                    """
        expected = " ".join(expected.split())
        self.assertEqual(expected, output)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_huge_diff_p(self) -> None:
        # verifies issue when huge patch is parsed very slow
        # https://github.com/Samsung/CredSweeper/issues/242
        text = """diff --git a/huge.file b/huge.file
                index 0000000..1111111 100644
                --- a/huge.file
                +++ a/huge.file
                @@ -3,13 +3,1000007 @@
                 00000000
                 11111111
                 22222222
                -33333333
                -44444444
                +55555555
                +66666666
                """
        for n in range(0, 1000000):
            text += "+" + hex(n) + "\n"
        with tempfile.TemporaryDirectory() as tmp_dir:
            target_path = os.path.join(tmp_dir, f"{__name__}.diff")
            start_time = time.time()
            _stdout, _stderr = self._m_credsweeper(["--path", target_path, "--ml_threshold", "0", "--log", "silence"])
            self.assertGreater(100, time.time() - start_time)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_it_works_with_patch_p(self) -> None:
        target_path = str(SAMPLES_PATH / "uuid-update.patch")
        _stdout, _stderr = self._m_credsweeper(["--diff", target_path, "--log", "silence"])
        output = " ".join(_stdout.split()[:-1])

        expected = """
                    rule: UUID
                    | severity: info
                    | confidence: strong
                    | ml_probability: None
                    | line_data_list:
                    [path: uuid
                        | line_num: 1
                        | value: 'bace4d19-fa7e-dead-beef-9129474bcd81'
                        | line: 'bace4d19-fa7e-dead-beef-9129474bcd81']
                    rule: UUID
                    | severity: info
                    | confidence: strong
                    | ml_probability: None
                    | line_data_list:
                    [path: uuid
                        | line_num: 1
                        | value: 'bace4d19-fa7e-beef-cafe-9129474bcd81'
                        | line: 'bace4d19-fa7e-beef-cafe-9129474bcd81']
                    Added File Credentials: 1
                    Deleted File Credentials: 1
                    Time Elapsed:
                    """
        expected = " ".join(expected.split())
        self.assertEqual(expected, output)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_it_works_with_multiline_in_patch_p(self) -> None:
        target_path = str(SAMPLES_PATH / "multiline.patch")
        _stdout, _stderr = self._m_credsweeper(["--diff_path", target_path, "--log", "silence"])
        output = " ".join(_stdout.split()[:-1])

        expected = """
                    rule: AWS Client ID
                        | severity: high
                        | confidence: moderate
                        | ml_probability: None
                        | line_data_list:
                            [path: creds.py
                            | line_num: 4
                            | value: 'AKIAQWADE5R42RDZ4JEM'
                            | line: ' clid = "AKIAQWADE5R42RDZ4JEM"']
                    rule: AWS Multi
                        | severity: high
                        | confidence: moderate
                        | ml_probability: None
                        | line_data_list:
                            [path: creds.py
                            | line_num: 4
                            | value: 'AKIAQWADE5R42RDZ4JEM'
                            | line: ' clid = "AKIAQWADE5R42RDZ4JEM"',
                            path: creds.py
                            | line_num: 5
                            | value: 'V84C7sDU001tFFodKU95USNy97TkqXymnvsFmYhQ'
                            | line: ' token = "V84C7sDU001tFFodKU95USNy97TkqXymnvsFmYhQ"']
                    rule: Token
                        | severity: high
                        | confidence: moderate
                        | ml_probability: 0.9988373517990112
                        | line_data_list:
                            [path: creds.py
                            | line_num: 5
                            | value: 'V84C7sDU001tFFodKU95USNy97TkqXymnvsFmYhQ'
                            | line: ' token = "V84C7sDU001tFFodKU95USNy97TkqXymnvsFmYhQ"']
                    Added File Credentials: 3
                    Deleted File Credentials: 0
                    Time Elapsed:
                    """
        expected = " ".join(expected.split())
        self.assertEqual(expected, output)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_it_works_with_patch_color_p(self) -> None:
        target_path = str(SAMPLES_PATH / "uuid-update.patch")
        _stdout, _stderr = self._m_credsweeper(
            ["--diff_path", target_path, "--log", "silence", "--color", "--no-stdout"])
        output = " ".join(_stdout.split()[:-1])
        expected = """
                   \x1b[1mUUID uuid:added:1\x1b[0m
                   \x1b[93mbace4d19-fa7e-dead-beef-9129474bcd81\x1b[0m
                   \x1b[1mUUID uuid:deleted:1\x1b[0m
                   \x1b[93mbace4d19-fa7e-beef-cafe-9129474bcd81\x1b[0m
                   Added File Credentials: 1 Deleted File Credentials: 1 Time Elapsed:
                   """
        expected = " ".join(expected.split())
        self.assertEqual(expected, output)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_it_works_n(self) -> None:
        _stdout, _stderr = self._m_credsweeper([])

        # Merge more than two whitespaces into one because _stdout and _stderr are changed based on the terminal size
        output = " ".join(_stderr.split())

        expected = "usage: python -m credsweeper [-h]" \
                   " (--path PATH [PATH ...]" \
                   " | --diff_path PATH [PATH ...]" \
                   " | --export_config [PATH]" \
                   " | --export_log_config [PATH]" \
                   " | --git PATH" \
                   ")" \
                   " [--ref REF]" \
                   " [--rules PATH]" \
                   " [--severity SEVERITY]" \
                   " [--config PATH]" \
                   " [--log_config PATH]" \
                   " [--denylist PATH]" \
                   " [--find-by-ext]" \
                   " [--depth POSITIVE_INT]" \
                   " [--no-filters]" \
                   " [--doc]" \
                   " [--ml_threshold FLOAT_OR_STR]" \
                   " [--ml_batch_size POSITIVE_INT]" \
                   " [--ml_config PATH]" \
                   " [--ml_model PATH]" \
                   " [--ml_providers STR] " \
                   " [--jobs POSITIVE_INT]" \
                   " [--thrifty | --no-thrifty]" \
                   " [--skip_ignored]" \
                   " [--error | --no-error]" \
                   " [--save-json [PATH]]" \
                   " [--save-xlsx [PATH]]" \
                   " [--stdout | --no-stdout]" \
                   " [--color | --no-color]" \
                   " [--hashed | --no-hashed]" \
                   " [--subtext | --no-subtext]" \
                   " [--sort | --no-sort]" \
                   " [--log LOG_LEVEL]" \
                   " [--size_limit SIZE_LIMIT]" \
                   " [--banner] " \
                   " [--version] " \
                   "python -m credsweeper: error: one of the arguments" \
                   " --path" \
                   " --diff_path" \
                   " --export_config" \
                   " --export_log_config" \
                   " --git" \
                   " is required "
        expected = " ".join(expected.split())
        self.assertEqual(expected, output)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_log_p(self) -> None:
        _stdout, _stderr = self._m_credsweeper(
            ["--log", "Debug", "--depth", "7", "--ml_threshold", "0", "--path",
             str(SAMPLE_ZIP), "not_existed_path"])
        self.assertEqual(0, len(_stderr))

        self.assertIn("DEBUG", _stdout)
        self.assertIn("INFO", _stdout)
        self.assertIn("WARNING", _stdout)
        self.assertIn("ERROR", _stdout)
        self.assertNotIn("CRITICAL", _stdout)

        for line in _stdout.splitlines():
            if 5 <= len(line) and "rule:" == line[0:5]:
                self.assertRegex(line, r"rule: \.*")
            elif 21 <= len(line) and "Detected Credentials:" == line[0:21]:
                self.assertRegex(line, r"Detected Credentials: \d+")
            elif 13 <= len(line) and "Time Elapsed:" == line[0:13]:
                self.assertRegex(line, r"Time Elapsed: \d+\.\d+")
            else:
                self.assertRegex(
                    line,
                    r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+ \| (DEBUG|INFO|WARNING|ERROR) \| \w+:\d+ \| .*",
                )

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_log_n(self) -> None:
        _stdout, _stderr = self._m_credsweeper(["--log", "CriTicaL", "--rule", "NOT_EXISTED_PATH", "--path", "."])
        self.assertEqual(0, len(_stderr))

        self.assertNotIn("DEBUG", _stdout)
        self.assertNotIn("INFO", _stdout)
        self.assertNotIn("WARNING", _stdout)
        self.assertNotIn("ERROR", _stdout)
        self.assertIn("CRITICAL", _stdout)

        self.assertTrue(
            any(
                re.match(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+ \| (CRITICAL) \| \w+:\d+ \| .*", line)
                for line in _stdout.splitlines()), _stdout)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    @pytest.mark.skipif(10 < sys.version_info.minor, reason="argparse default was changed in 3.11")
    def test_help_p(self) -> None:
        _stdout, _stderr = self._m_credsweeper(["--help"])
        output = " ".join(_stdout.split())
        if 10 > sys.version_info.minor and output.find("options:"):
            # Legacy support python3.9 to display "optional arguments:" like in python 3.10
            output = output.replace("options:", "optional arguments:")
        help_path = os.path.join(TESTS_PATH, "..", "docs", "source", "guide.rst")
        with open(help_path, "r") as f:
            text = ""
            started = False
            for line in f.read().splitlines():
                if ".. note::" == line:
                    break
                if ".. code-block:: text" == line:
                    started = True
                    continue
                if started:
                    if 10 > sys.version_info.minor and line.strip() == "options:":
                        # Legacy support python3.9 to display "optional arguments:"
                        text = ' '.join([text, line.replace("options:", "optional arguments:")])
                    else:
                        text = ' '.join([text, line])
            expected = " ".join(text.split())
            self.assertEqual(expected, output)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_version_p(self) -> None:
        _stdout, _stderr = self._m_credsweeper(["--version"])
        # Merge more than two whitespaces into one because _stdout and _stderr are changed based on the terminal size
        output = " ".join(_stdout.split())
        self.assertRegex(output, r"CredSweeper \d+\.\d+\.\d+")

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_banner_p(self) -> None:
        _stdout, _stderr = self._m_credsweeper(["--banner"])
        output = " ".join(_stdout.split())
        self.assertRegex(output, r"CredSweeper \d+\.\d+\.\d+ crc32:[0-9a-f]{8}", _stderr or _stdout)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_patch_save_json_p(self) -> None:
        target_path = str(SAMPLES_PATH / "password.patch")
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper(
                ["--diff_path", target_path, "--no-stdout", "--save-json", json_filename, "--log", "silence"])
            self.assertTrue(os.path.exists(os.path.join(tmp_dir, f"{__name__}.added.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp_dir, f"{__name__}.deleted.json")))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_patch_save_json_n(self) -> None:
        start_time = time.time()
        target_path = str(SAMPLES_PATH / "password.patch")
        _stdout, _stderr = self._m_credsweeper(["--diff_path", target_path, "--log", "silence"])
        for root, dirs, files in os.walk(APP_PATH.parent):
            self.assertIn("credsweeper", dirs)
            for file in files:
                # check whether the report was created AFTER test launch to avoid failures during development
                self.assertFalse(file.endswith(".json") and os.stat(os.path.join(root, file)).st_mtime > start_time)
            dirs.clear()

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_export_config_p(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper(["--export_config", json_filename, "--log", "silence"])
            self.assertTrue(os.path.exists(json_filename))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_import_config_p(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            custom_config = os.path.join(tmp_dir, f"{__name__}.json")
            shutil.copyfile(APP_PATH / "secret" / "config.json", custom_config)
            args = ["--config", custom_config, "--path", str(APP_PATH), "--find-by-ext", "--log", "CRITICAL"]
            _stdout, _stderr = self._m_credsweeper(args)
            self.assertEqual("", _stderr)
            self.assertNotIn("CRITICAL", _stdout)
            self.assertIn("Time Elapsed:", _stdout)
            self.assertIn("Detected Credentials: 0", _stdout)
            self.assertEqual(2, len(_stdout.splitlines()))
            # add .py to find by extension
            modified_config = Util.json_load(custom_config)
            self.assertIn("find_by_ext_list", modified_config.keys())
            self.assertIsInstance(modified_config["find_by_ext_list"], list)
            modified_config["find_by_ext_list"].append(".py")
            Util.json_dump(modified_config, custom_config)
            _stdout, _stderr = self._m_credsweeper(args)
            self.assertEqual("", _stderr)
            self.assertNotIn("CRITICAL", _stdout)
            self.assertIn("Time Elapsed:", _stdout)
            self.assertNotIn("Detected Credentials: 0", _stdout)
            self.assertLess(5, len(_stdout.splitlines()))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_import_config_n(self) -> None:
        # not existed file
        _stdout, _stderr = self._m_credsweeper(
            ["--config", "not_existed_file", "--path",
             str(APP_PATH), "--log", "CRITICAL"])
        self.assertEqual(0, len(_stderr))
        self.assertIn("CRITICAL", _stdout)
        # wrong config
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            with open(json_filename, "w") as f:
                f.write('{}')
            _stdout, _stderr = self._m_credsweeper(
                ["--config", json_filename, "--path",
                 str(APP_PATH), "--log", "CRITICAL"])
            self.assertEqual(0, len(_stderr))
            self.assertIn("CRITICAL", _stdout)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_export_log_config_p(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_filename = os.path.join(tmp_dir, f"{__name__}.yaml")
            _stdout, _stderr = self._m_credsweeper(["--export_log_config", test_filename, "--log", "silence"])
            self.assertTrue(os.path.exists(test_filename))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_import_log_config_p(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_filename = os.path.join(tmp_dir, f"{__name__}.yaml")
            _o, _e = self._m_credsweeper(["--export_log_config", test_filename, "--log", "silence"])
            self.assertFalse(os.path.exists(os.path.join(tmp_dir, "log")))
            with open(test_filename, 'r') as f:
                text = f.read().replace("filename: ./log", f"filename: {tmp_dir}/log")
            with open(test_filename, 'w') as f:
                f.write(text)
            _stdout, _stderr = self._m_credsweeper(["--log_config", test_filename, "--log", "silence", "--path", "X3"])
            self.assertTrue(os.path.exists(os.path.join(tmp_dir, "log")))
            self.assertTrue(os.path.exists(os.path.join(tmp_dir, "log", "error.log")))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_find_by_ext_p(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # .deR will be found also!
            for f in [".pem", ".cer", ".csr", ".deR"]:
                file_path = os.path.join(tmp_dir, f"dummy{f}")
                self.assertFalse(os.path.exists(file_path))
                open(file_path, "w").write(AZ_STRING)

            # not of all will be found due they are empty
            for f in [".jks", ".KeY"]:
                file_path = os.path.join(tmp_dir, f"dummy{f}")
                self.assertFalse(os.path.exists(file_path))
                open(file_path, "w").close()

            # the directory hides all files
            ignored_dir = os.path.join(tmp_dir, "target")
            os.mkdir(ignored_dir)
            for f in [".pfx", ".p12"]:
                file_path = os.path.join(ignored_dir, f"dummy{f}")
                self.assertFalse(os.path.exists(file_path))
                open(file_path, "w").write(AZ_STRING)

            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper(
                ["--path", tmp_dir, "--find-by-ext", "--no-stdout", "--save-json", json_filename, "--log", "silence"])
            self.assertTrue(os.path.exists(json_filename))
            with open(json_filename, "r") as json_file:
                report = json.load(json_file)
                self.assertEqual(4, len(report), report)
                for t in report:
                    self.assertEqual(0, t["line_data_list"][0]["line_num"])
                    self.assertIn(str(t["line_data_list"][0]["path"][-4:]), [".pem", ".cer", ".csr", ".deR"])

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_find_by_ext_n(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            for f in [".pem", ".cer", ".csr", ".der", ".pfx", ".p12", ".key", ".jks"]:
                file_path = os.path.join(tmp_dir, f"dummy{f}")
                self.assertFalse(os.path.exists(file_path))
                open(file_path, "w").write(AZ_STRING)
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper(
                ["--path", tmp_dir, "--no-stdout", "--save-json", json_filename, "--log", "silence"])
            self.assertTrue(os.path.exists(json_filename))
            with open(json_filename, "r") as json_file:
                report = json.load(json_file)
                self.assertEqual(0, len(report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_depth_p(self) -> None:
        normal_report = []
        sorted_report = []
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            # depth = 3
            _stdout, _stderr = self._m_credsweeper([
                "--log", "silence", "--path",
                str(SAMPLES_PATH), "--no-stdout", "--save-json", json_filename, "--depth", "3"
            ])
            self.assertTrue(os.path.exists(json_filename))
            with open(json_filename, "r") as json_file:
                normal_report.extend(json.load(json_file))
                self.assertEqual(SAMPLES_IN_DEEP_3, len(normal_report))
            sorted_json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper([
                "--log", "silence", "--path",
                str(SAMPLES_PATH), "--sort", "--no-stdout", "--save-json", sorted_json_filename, "--depth", "3"
            ])
            self.assertTrue(os.path.exists(sorted_json_filename))
            with open(sorted_json_filename, "r") as json_file:
                sorted_report.extend(json.load(json_file))
                self.assertEqual(SAMPLES_IN_DEEP_3, len(sorted_report))
        self.assertTrue(deepdiff.DeepDiff(sorted_report, normal_report))
        # exclude equal items of dict instead custom __lt__ realization
        for n in range(len(normal_report) - 1, -1, -1):
            for i in sorted_report:
                if i == normal_report[n]:
                    del normal_report[n]
                    break
        # 0 - means all items were matched
        self.assertEqual(0, len(normal_report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_depth_n(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            # depth is not set
            _stdout, _stderr = self._m_credsweeper(
                ["--log", "silence", "--path",
                 str(SAMPLES_PATH), "--no-stdout", "--save-json", json_filename])
            self.assertTrue(os.path.exists(json_filename))
            with open(json_filename, "r") as json_file:
                report = json.load(json_file)
                self.assertEqual(SAMPLES_POST_CRED_COUNT, len(report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_denylist_p(self) -> None:
        target_path = str(SAMPLES_PATH / "github_classic_token")
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            denylist_filename = os.path.join(tmp_dir, "list.txt")
            with open(denylist_filename, "w") as f:
                f.write('ghp_00000000000000000000000000000004WZ4EQ # classic')  # full line
            _stdout, _stderr = self._m_credsweeper([
                "--path", target_path, "--denylist", denylist_filename, "--no-stdout", "--save-json", json_filename,
                "--log", "silence"
            ])
            with open(json_filename, "r") as json_file:
                report = json.load(json_file)
                self.assertEqual(0, len(report))
            with open(denylist_filename, "w") as f:
                f.write('ghp_00000000000000000000000000000004WZ4EQ')  # value only
            _stdout, _stderr = self._m_credsweeper([
                "--path", target_path, "--denylist", denylist_filename, "--no-stdout", "--save-json", json_filename,
                "--log", "silence"
            ])
            with open(json_filename, "r") as json_file:
                report = json.load(json_file)
                self.assertEqual(0, len(report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_denylist_n(self) -> None:
        target_path = str(SAMPLES_PATH / "github_classic_token")
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            denylist_filename = os.path.join(tmp_dir, "list.txt")
            with open(denylist_filename, "w") as f:
                f.write('4WZ4EQ # classic')  # part of line - will not exclude
            _stdout, _stderr = self._m_credsweeper([
                "--path", target_path, "--denylist", denylist_filename, "--no-stdout", "--save-json", json_filename,
                "--log", "silence"
            ])
            with open(json_filename, "r") as json_file:
                report = json.load(json_file)
                self.assertEqual(1, len(report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_rules_ml_p(self) -> None:
        # checks whether all rules have positive test samples with almost the same arguments during benchmark
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper([
                "--path",
                str(SAMPLES_PATH),
                "--save-json",
                json_filename,
            ])
            self.assertEqual(0, len(_stderr))
            report = Util.json_load(json_filename)
            report_set = set([i["rule"] for i in report])
            rules = Util.yaml_load(APP_PATH / "rules" / "config.yaml")
            rules_set = set([i["name"] for i in rules if "code" in i["target"]])
            self.assertSetEqual(rules_set, report_set)
            self.assertEqual(SAMPLES_POST_CRED_COUNT, len(report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_rules_ml_n(self) -> None:
        # checks whether all rules have test samples which detected without ML
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper([
                "--path",
                str(SAMPLES_PATH),
                "--ml_threshold",
                "0",
                "--save-json",
                json_filename,
            ])
            self.assertEqual(0, len(_stderr))
            report = Util.json_load(json_filename)
            report_set = set([i["rule"] for i in report])
            rules = Util.yaml_load(APP_PATH / "rules" / "config.yaml")
            rules_set = set([i["name"] for i in rules if "code" in i["target"]])
            self.assertSetEqual(rules_set, report_set)
            self.assertEqual(SAMPLES_FILTERED_COUNT, len(report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_no_filters_p(self) -> None:
        # checks with disabled ML and filtering
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper([
                "--path",
                str(SAMPLES_PATH),
                "--ml_threshold",
                "0",
                "--no-filters",
                "--save-json",
                json_filename,
            ])
            self.assertEqual(0, len(_stderr))
            report = Util.json_load(json_filename)
            # the number of reported items should increase
            self.assertLess(SAMPLES_FILTERED_COUNT, len(report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_severity_patch_xlsx_n(self) -> None:
        # uuid is info level - no report
        with tempfile.TemporaryDirectory() as tmp_dir:
            _stdout, _stderr = self._m_credsweeper([  #
                "--severity",
                "low",
                "--diff",
                str(SAMPLES_PATH / "uuid-update.patch"),
                "--save-xlsx",
                os.path.join(tmp_dir, f"{__name__}.xlsx"),
                "--save-json",
                os.path.join(tmp_dir, f"{__name__}.json"),
            ])
            # reports are created
            self.assertEqual(3, len(os.listdir(tmp_dir)))
            # but empty
            self.assertListEqual([], Util.json_load(os.path.join(tmp_dir, f"{__name__}.deleted.json")))
            self.assertListEqual([], Util.json_load(os.path.join(tmp_dir, f"{__name__}.added.json")))
            self.assertEqual(0, len(pd.read_excel(os.path.join(tmp_dir, f"{__name__}.xlsx"))))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_severity_patch_xlsx_p(self) -> None:
        # info level produces xlsx file with "added" and "deleted" sheets and two json files
        with tempfile.TemporaryDirectory() as tmp_dir:
            xlsx_filename = os.path.join(tmp_dir, f"{__name__}.xlsx")
            _stdout, _stderr = self._m_credsweeper([  #
                "--severity",
                "info",
                "--diff",
                str(SAMPLES_PATH / "uuid-update.patch"),
                "--save-xlsx",
                xlsx_filename,
                "--save-json",
                os.path.join(tmp_dir, f"{__name__}.json"),
            ])
            deleted_report_file = os.path.join(tmp_dir, f"{__name__}.deleted.json")
            deleted_report = Util.json_load(deleted_report_file)
            self.assertEqual("UUID", deleted_report[0]["rule"])
            added_report_file = os.path.join(tmp_dir, f"{__name__}.added.json")
            added_report = Util.json_load(added_report_file)
            self.assertEqual("UUID", added_report[0]["rule"])
            book = pd.read_excel(xlsx_filename, sheet_name=None, header=None)
            # two sheets should be created
            self.assertSetEqual({"deleted", "added"}, set(book.keys()))
            # values in xlsx are wrapped to double quotes
            deleted_value = f'"{deleted_report[0]["line_data_list"][0]["value"]}"'
            self.assertTrue(np.isin(deleted_value, book["deleted"].values))
            added_value = f'"{added_report[0]["line_data_list"][0]["value"]}"'
            self.assertTrue(np.isin(added_value, book["added"].values))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_doc_n(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            _stdout, _stderr = self._m_credsweeper([
                "--doc",
                "--path",
                str(SAMPLES_PATH),
                "--no-stdout",
                "--ml_threshold",
                str(NEGLIGIBLE_ML_THRESHOLD),
                "--save-json",
                json_filename,
            ])
            report = Util.json_load(json_filename)
            self.assertEqual(SAMPLES_IN_DOC, len(report))

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_external_ml_n(self) -> None:
        # not existed ml_config
        _stdout, _stderr = self._m_credsweeper(
            ["--ml_config", "not_existed_file", "--path",
             str(APP_PATH), "--log", "CRITICAL"])
        self.assertEqual(0, len(_stderr))
        self.assertIn("CRITICAL", _stdout)
        # not existed ml_model
        _stdout, _stderr = self._m_credsweeper(
            ["--ml_model", "not_existed_file", "--path",
             str(APP_PATH), "--log", "CRITICAL"])
        self.assertEqual(0, len(_stderr))
        self.assertIn("CRITICAL", _stdout)
        # wrong config
        with tempfile.TemporaryDirectory() as tmp_dir:
            json_filename = os.path.join(tmp_dir, f"{__name__}.json")
            with open(json_filename, "w") as f:
                f.write('{}')
            _stdout, _stderr = self._m_credsweeper(
                ["--ml_config", json_filename, "--path",
                 str(APP_PATH), "--log", "CRITICAL"])
            self.assertEqual(0, len(_stderr))
            self.assertIn("CRITICAL", _stdout)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

    def test_external_ml_p(self) -> None:
        log_pattern = re.compile(r".*Init ML validator with providers: \S+ ;"
                                 r" model:'.+' md5:([0-9a-f]{32}) ;"
                                 r" config:'.+' md5:([0-9a-f]{32}) ;"
                                 r" .*")
        _stdout, _stderr = self._m_credsweeper(["--path", str(APP_PATH), "--log", "INFO"])
        self.assertEqual(0, len(_stderr))
        self.assertNotIn("CRITICAL", _stdout)
        for i in _stdout.splitlines():
            if log_match := re.match(log_pattern, i):
                md5_config = log_match.group(1)
                md5_model = log_match.group(2)
                break
        else:
            self.fail(f"'Init ML validator' not found in {_stdout}")
        with tempfile.TemporaryDirectory() as tmp_dir:
            custom_ml_config = os.path.join(tmp_dir, f"{__name__}.json")
            shutil.copyfile(APP_PATH / "ml_model" / "ml_config.json", custom_ml_config)
            custom_ml_model = os.path.join(tmp_dir, f"{__name__}.onnx")
            shutil.copyfile(APP_PATH / "ml_model" / "ml_model.onnx", custom_ml_model)
            with open(custom_ml_config, "a") as f:
                f.write("\n\n\n")
            args = [
                "--ml_config", custom_ml_config, "--ml_model", custom_ml_model, "--path",
                str(APP_PATH), "--log", "INFO"
            ]
            _stdout, _stderr = self._m_credsweeper(args)
            self.assertEqual("", _stderr)
            self.assertNotIn("CRITICAL", _stdout)
            # model hash is the same
            self.assertIn(md5_model, _stdout)
            # hash of ml config will be different
            self.assertNotIn(md5_config, _stdout)

    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
