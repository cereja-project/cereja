from typing import List

from .._utils import DataIterator
from .runner import GitCommandRunner


class GitRepository:
    """Facade para operações comuns de Git com cache de branches."""

    def __init__(self,
                 repo_path="."):
        self.runner = GitCommandRunner(repo_path)
        self._branches = {}
        self._setup_cache()

    @property
    def local_branches(self) -> list[str]:
        if 'local' not in self._branches:
            self._branches['local'] = self._fetch_local_branches()
        return self._branches['local']

    @property
    def remote_branches(self) -> list[str]:
        if 'remote' not in self._branches:
            self._branches['remote'] = self._fetch_remote_branches()
        return self._branches['remote']

    @property
    def all_branches(self) -> list[str]:
        return list(set(self.local_branches + self.remote_branches))

    @property
    def branches_count(self) -> dict[str, int]:
        return {key: len(value) for key, value in self._branches.items()}

    @property
    def need_commit(self) -> bool:
        """Verifica se há mudanças não commitadas."""
        status = self.runner.run(["status", "--porcelain"])
        return bool(status.strip())

    @property
    def is_clean(self) -> bool:
        """Verifica se o repositório está limpo (sem mudanças não commitadas)."""
        return not self.need_commit

    @property
    def is_repo(self) -> bool:
        """Verifica se o diretório atual é um repositório Git."""
        try:
            self.runner.run(["rev-parse", "--is-inside-work-tree"])
            return True
        except Exception:
            return False

    @property
    def has_remote(self) -> bool:
        """Verifica se o repositório tem um remoto configurado."""
        remotes = self.runner.run(["remote"])
        return bool(remotes.strip())

    @property
    def remotes(self) -> list[str]:
        """Retorna lista de remotos configurados."""
        remotes = self.runner.run(["remote"])
        return remotes.splitlines() if remotes else []

    @property
    def current_branch(self) -> str:
        """Retorna a branch atual."""
        return self._current_branch

    # Métodos privados
    def _get_current_branch(self) -> str:
        return self.runner.run(["rev-parse", "--abbrev-ref", "HEAD"])

    def _setup_cache(self):
        self._current_branch = self._get_current_branch()
        self._branches['local'] = self._fetch_local_branches()
        self._branches['remote'] = self._fetch_remote_branches()

    # ---------------------------
    # Métodos privados de cache
    # ---------------------------
    def _parse_branch_names(self,
                            git_output: str) -> List[str]:
        return (DataIterator(git_output.splitlines())
                .str.replace('*', '').strip()
                .replace('origin/', '')
                .filter(lambda item: 'HEAD' not in item).take()
                )

    def _fetch_local_branches(self) -> list[str]:
        output = self.runner.run(["branch", "--list"])
        return self._parse_branch_names(output)

    def _fetch_remote_branches(self) -> list[str]:
        output = self.runner.run(["branch", "-r"])
        return self._parse_branch_names(output)

    # ---------------------------
    # Métodos públicos principais
    # ---------------------------
    def _diff(self,
             branch_a: str,
             branch_b: str,
             file_pattern: str = None) -> str:
        """
        Retorna o diff entre duas branches, opcionalmente filtrando por padrão de arquivo.
        Args:
            branch_a: Nome da primeira branch
            branch_b: Nome da segunda branch
            file_pattern: Padrão de arquivo para filtrar (ex: '*.py', 'docs/*')
        Returns:
            str: Saída do comando git diff
        Raises:
            ValueError: Se alguma das branches não existir
        """

        command = ["diff", branch_a, branch_b]
        if file_pattern:
            command.append("--")
            command.append(file_pattern)
        return self.runner.run(command)

    def diff(self,
                branch: str,
                file_pattern: str = None,
                check_origin: bool = True
             ) -> str:
        """
        Retorna o diff entre a branch atual e a branch especificada, opcionalmente filtrando por padrão de arquivo.
        Args:
            branch: Nome da branch para comparar com a atual
            file_pattern: Padrão de arquivo para filtrar (ex: '*.py', 'docs/*')
        Returns:
            str: Saída do comando git diff
        Raises:
            ValueError: Se a branch não existir
        """
        if check_origin and branch.replace('origin/', '') not in self.all_branches:
            raise ValueError(f"Branch '{branch}' não encontrada.")

        branch = branch if 'origin/' in branch else f'origin/{branch}'

        return self._diff(self.current_branch, branch, file_pattern)

    def last_commit(self,
                    branch: str = None) -> str:
        """Retorna o último commit da branch especificada ou da atual."""
        target_branch = branch if branch else self.current_branch
        if target_branch not in self.all_branches:
            raise ValueError(f"Branch '{target_branch}' não encontrada.")
        return self.runner.run(["log", "-1", "--pretty=format:%h - %s"])

    def log(self,
            branch: str = None,
            max_count: int = 10) -> str:
        """Retorna o log de commits da branch especificada ou da atual."""
        target_branch = branch if branch else self.current_branch
        if target_branch not in self.all_branches:
            raise ValueError(f"Branch '{target_branch}' não encontrada.")
        return self.runner.run(["log", target_branch, f"--max-count={max_count}", "--oneline"])

    def messages(self,
                 branch: str = None,
                 max_count: int = 10) -> list[str]:
        """Retorna uma lista de mensagens de commit da branch especificada ou da atual."""
        log_output = self.log(branch, max_count)
        return [line.split(' ', 1)[1] for line in log_output.splitlines() if ' ' in line]


    # ---------------------------
    # Métodos de cache
    # ---------------------------
    def refresh_branches(self):
        """Atualiza cache das branches locais e remotas."""
        self._setup_cache()

    # Metódos comuns # pull, push, checkout, merge

    def pull(self,
             remote: str = "origin",
             branch: str = None):
        """Puxa mudanças do remoto especificado, opcionalmente para uma branch específica."""
        if not self.has_remote or remote not in self.remotes:
            raise ValueError(f"Remoto '{remote}' não encontrado.")
        command = ["pull", remote]
        if branch and branch in self.remote_branches:
            command.append(branch)
        self.runner.run(command)
        self._setup_cache()

    def push(self,
             remote: str = "origin",
             branch: str = None,
             set_upstream: bool = False):
        """Empurra mudanças para o remoto especificado, opcionalmente para uma branch específica."""
        if not self.has_remote or remote not in self.remotes:
            raise ValueError(f"Remoto '{remote}' não encontrado.")
        command = ["push", remote]
        if branch and branch in self.local_branches:
            if set_upstream:
                command.append("-u")
            command.append(branch)
        self.runner.run(command)
        self._setup_cache()

    def checkout(self,
                 branch: str,
                 create_new: bool = False):
        """Troca para a branch especificada, opcionalmente criando uma nova."""
        if create_new:
            if branch in self.local_branches:
                raise ValueError(f"Branch '{branch}' já existe localmente.")
            # se branch existe remotamente, cria rastreamento
            if branch in self.remote_branches:
                self.runner.run(["checkout", "-b", branch, f"origin/{branch}"])
        else:
            if branch not in self.local_branches:
                raise ValueError(f"Branch '{branch}' não encontrada localmente.")
            self.runner.run(["checkout", branch])
        self._setup_cache()
