import json
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.dexter_bridge import run_dexter_once, DEXTER_RUNNER_TS


def _mock_proc(answer: str = "AAPL is bullish. $AAPL BUY", returncode: int = 0) -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = json.dumps({"answer": answer}) + "\n"
    m.stderr = ""
    return m


class TestRunnerFileLocation:
    def test_runner_written_to_tmp_not_dexter_dir(self, tmp_path):
        """ランナーファイルが dexter_dir ではなく /tmp に書かれる"""
        written_paths: list[str] = []

        original_run = __import__("subprocess").run

        def capture_run(cmd, **kwargs):
            written_paths.append(cmd[2])  # "bun run <path> <query>"
            return _mock_proc()

        with patch("shutil.which", return_value="/usr/bin/bun"), \
             patch("subprocess.run", side_effect=capture_run):
            run_dexter_once(tmp_path, "test query")

        assert written_paths, "subprocess.run was not called"
        runner_path = Path(written_paths[0])
        assert str(runner_path).startswith("/tmp"), (
            f"runner should be in /tmp, got: {runner_path}"
        )
        assert tmp_path not in runner_path.parents, (
            f"runner must not be inside dexter_dir: {runner_path}"
        )

    def test_runner_cleaned_up_after_execution(self, tmp_path):
        """実行後にランナーファイルが削除される"""
        written_paths: list[str] = []

        def capture_run(cmd, **kwargs):
            written_paths.append(cmd[2])
            return _mock_proc()

        with patch("shutil.which", return_value="/usr/bin/bun"), \
             patch("subprocess.run", side_effect=capture_run):
            run_dexter_once(tmp_path, "test query")

        assert not Path(written_paths[0]).exists(), "runner file was not cleaned up"

    def test_runner_cleaned_up_on_error(self, tmp_path):
        """エラー時もランナーファイルが削除される"""
        written_paths: list[str] = []

        def capture_run(cmd, **kwargs):
            written_paths.append(cmd[2])
            return _mock_proc(returncode=1)

        with patch("shutil.which", return_value="/usr/bin/bun"), \
             patch("subprocess.run", side_effect=capture_run):
            with pytest.raises(RuntimeError):
                run_dexter_once(tmp_path, "test query")

        assert not Path(written_paths[0]).exists(), "runner file was not cleaned up on error"

    def test_works_with_readonly_dexter_dir(self, tmp_path):
        """dexter_dir が read-only でも動く（:ro マウント想定）"""
        tmp_path.chmod(stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)
        try:
            with patch("shutil.which", return_value="/usr/bin/bun"), \
                 patch("subprocess.run", return_value=_mock_proc()):
                result = run_dexter_once(tmp_path, "test query")
            assert result == "AAPL is bullish. $AAPL BUY"
        finally:
            tmp_path.chmod(0o755)


class TestRunnerContent:
    def test_runner_contains_absolute_import(self, tmp_path):
        """生成されたランナーが dexter_dir の絶対パスで Agent を import する"""
        written_contents: list[str] = []

        def capture_run(cmd, **kwargs):
            written_contents.append(Path(cmd[2]).read_text())
            return _mock_proc()

        with patch("shutil.which", return_value="/usr/bin/bun"), \
             patch("subprocess.run", side_effect=capture_run):
            run_dexter_once(tmp_path, "test query")

        content = written_contents[0]
        assert str(tmp_path) in content, "absolute dexter_dir path not in runner"
        assert "./src/agent" not in content, "relative import must not remain in runner"
        assert "__DEXTER_DIR__" not in content, "placeholder was not replaced"
        assert "{{" not in content, "escaped braces leaked into TypeScript"

    def test_runner_passes_query_as_argv(self, tmp_path):
        """bun run に query が argv として渡される"""
        captured_cmd: list[list[str]] = []

        def capture_run(cmd, **kwargs):
            captured_cmd.append(list(cmd))
            return _mock_proc()

        with patch("shutil.which", return_value="/usr/bin/bun"), \
             patch("subprocess.run", side_effect=capture_run):
            run_dexter_once(tmp_path, "AAPLについて教えて")

        assert captured_cmd[0][-1] == "AAPLについて教えて"
