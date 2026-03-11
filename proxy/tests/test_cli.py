from click.testing import CliRunner
from anysql_proxy.cli import main


def test_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "stop" in result.output
    assert "setup" in result.output
    assert "keys" in result.output


def test_stop_no_pid_file(tmp_path):
    """stop with no PID file prints helpful message."""
    from unittest.mock import patch
    runner = CliRunner()
    # Redirect Path.home() to tmp_path — no proxy.pid will exist there
    with patch("anysql_proxy.cli.Path.home", return_value=tmp_path):
        result = runner.invoke(main, ["stop"])
    assert result.exit_code == 0
    assert "No PID file found" in result.output


def test_status_not_running():
    """status prints 'not running' when proxy is not up."""
    runner = CliRunner()
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "not running" in result.output
