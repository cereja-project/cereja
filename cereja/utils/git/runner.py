import subprocess
from .exceptions import GitCommandError
import logging

logger = logging.getLogger(__name__)


class GitCommandRunner:
    """Strategy para execução de comandos Git via subprocess."""

    def __init__(self,
                 repo_path=".",
                 verbose: bool = True):
        self.repo_path = repo_path

    def run(self,
            args: list[str]) -> str:
        try:
            import sys
            result = subprocess.run(
                    ["git"] + args,
                    cwd=self.repo_path,
                    # capture_output=True,
                    text=True,
                    check=True,
                    stdout=sys.stdout
            )
            return result.stdout


        except subprocess.CalledProcessError as e:
            raise GitCommandError(f"Erro ao executar git {' '.join(args)}: {e.stderr.strip()}")
