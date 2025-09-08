import subprocess
from .exceptions import GitCommandError


class GitCommandRunner:
    """Strategy para execução de comandos Git via subprocess."""

    def __init__(self,
                 repo_path="."):
        self.repo_path = repo_path

    def run(self,
            args: list[str]) -> str:
        try:
            result = subprocess.run(
                    ["git"] + args,
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True,
                    check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise GitCommandError(f"Erro ao executar git {' '.join(args)}: {e.stderr.strip()}")
