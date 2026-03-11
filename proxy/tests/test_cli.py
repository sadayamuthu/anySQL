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
    with patch("anysql_proxy.cli.Path") as MockPath:
        pid_file = MockPath.home.return_value / ".anysql" / "proxy.pid"
        pid_file.exists.return_value = False
        result = runner.invoke(main, ["stop"])
    assert result.exit_code == 0


def test_status_not_running():
    """status prints 'not running' when proxy is not up."""
    runner = CliRunner()
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "not running" in result.output
