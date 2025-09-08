import fnmatch
from .runner import GitCommandRunner


class GitRepository:
    """Facade para operações comuns de Git com cache de branches."""

    def __init__(self, repo_path="."):
        self.runner = GitCommandRunner(repo_path)

        # 🔹 Cache inicial
        self.current_branch = self.get_current_branch()
        self.local_branches = self._fetch_local_branches()
        self.remote_branches = self._fetch_remote_branches()

    # ---------------------------
    # Métodos privados de cache
    # ---------------------------
    def _fetch_local_branches(self) -> list[str]:
        output = self.runner.run(["branch", "--list"])
        return [line.strip().replace("* ", "") for line in output.splitlines()]

    def _fetch_remote_branches(self) -> list[str]:
        output = self.runner.run(["branch", "-r"])
        return [line.strip() for line in output.splitlines()]

    # ---------------------------
    # Métodos públicos principais
    # ---------------------------
    def get_current_branch(self) -> str:
        return self.runner.run(["rev-parse", "--abbrev-ref", "HEAD"])

    def get_changed_files(self, base_branch: str, target_branch: str) -> list[str]:
        output = self.runner.run(["diff", "--name-only", f"{base_branch}..{target_branch}"])
        return output.splitlines() if output else []

    def get_diff(self, base_branch: str, target_branch: str) -> str:
        return self.runner.run(["diff", f"{base_branch}..{target_branch}"])

    def get_commit_messages(self, base_branch: str, target_branch: str) -> list[str]:
        output = self.runner.run(["log", f"{base_branch}..{target_branch}", "--pretty=format:%s"])
        return output.splitlines() if output else []

    def get_last_commit(self) -> str:
        return self.runner.run(["log", "-1", "--pretty=format:%h - %s"])

    # ---------------------------
    # Métodos de cache
    # ---------------------------
    def refresh_branches(self):
        """Atualiza cache das branches locais e remotas."""
        self.local_branches = self._fetch_local_branches()
        self.remote_branches = self._fetch_remote_branches()

    # ---------------------------
    # Métodos de filtragem
    # ---------------------------
    def filter_local_branches(self, pattern: str) -> list[str]:
        """Filtra branches locais por padrão (ex: 'feature/*')."""
        return fnmatch.filter(self.local_branches, pattern)

    def filter_remote_branches(self, pattern: str) -> list[str]:
        """Filtra branches remotas por padrão (ex: 'origin/feature/*')."""
        return fnmatch.filter(self.remote_branches, pattern)

    def find_branch(self, name: str) -> str | None:
        """Procura branch pelo nome (local ou remota)."""
        if name in self.local_branches:
            return name
        matches = [b for b in self.remote_branches if b.endswith(name)]
        return matches[0] if matches else None
