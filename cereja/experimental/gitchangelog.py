from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional

from cereja import FileIO


@dataclass
class CommitInfo:
    """Representa um commit coletado do git."""
    hash: str
    author: str
    date: str  # formato YYYY-MM-DD
    subject: str


@dataclass
class DiffFile:
    """Representa um arquivo alterado no diff."""
    status: str
    path: str
    extra: Optional[str] = None  # para renomes (antigo -> novo)


def run_git(args: List[str]) -> str:
    """Executa um comando git e retorna stdout como string.

    Args:
        args: Lista de argumentos para o git (ex: ['log', '--oneline']).

    Returns:
        Saída padrão do comando.

    Raises:
        RuntimeError: Se o comando retornar código diferente de zero.
    """
    result = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Erro ao executar git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout.strip()


def detect_base_branch(explicit: Optional[str]) -> str:
    """Detecta a branch base a ser usada.

    Ordem de detecção se não explícita: origin/develop, origin/main, origin/master.

    Args:
        explicit: Nome informado pelo usuário.

    Returns:
        Nome da branch base.

    Raises:
        RuntimeError: Se nenhuma branch base for encontrada.
    """
    if explicit:
        return explicit
    candidates = ["origin/develop", "origin/main", "origin/master"]
    refs = run_git(["branch", "-r"]).splitlines()
    refs = [r.strip() for r in refs]
    for c in candidates:
        if c in refs:
            return c
    raise RuntimeError("Nenhuma branch base encontrada (origin/develop, origin/main, origin/master)")


def get_current_branch() -> str:
    """Obtém nome da branch atual."""
    return run_git(["branch", "--show-current"]) or "HEAD"


def collect_commits(base: str) -> List[CommitInfo]:
    """Coleta commits exclusivos (base..HEAD).

    Args:
        base: Referência base.

    Returns:
        Lista de CommitInfo.
    """
    raw = run_git([
        "log",
        "--pretty=format:%h\t%an\t%ad\t%s",
        "--date=short",
        f"{base}..HEAD",
    ])
    if not raw:
        return []
    commits: List[CommitInfo] = []
    for line in raw.splitlines():
        parts = line.split("\t", 3)
        if len(parts) != 4:
            continue
        h, a, d, s = parts
        commits.append(CommitInfo(hash=h, author=a, date=d, subject=s))
    return commits


def collect_diff_files(base: str) -> List[DiffFile]:
    """Coleta lista de arquivos alterados entre base e HEAD.

    Args:
        base: Referência base.

    Returns:
        Lista de DiffFile.
    """
    raw = run_git(["diff", "--name-status", f"{base}..HEAD"])
    if not raw:
        return []
    diff_files: List[DiffFile] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:  # renomeado
            diff_files.append(DiffFile(status="R", path=parts[2], extra=parts[1]))
        else:
            path = parts[1] if len(parts) > 1 else ""
            diff_files.append(DiffFile(status=status, path=path))
    return diff_files


def categorize_files(files: List[DiffFile]) -> Dict[str, List[DiffFile]]:
    """Agrupa arquivos por status simplificado.

    Args:
        files: Lista de arquivos diff.

    Returns:
        Dicionário com chaves: added, modified, deleted, renamed, others.
    """
    categories: Dict[str, List[DiffFile]] = {"added": [], "modified": [], "deleted": [], "renamed": [], "others": []}
    for f in files:
        if f.status == "A":
            categories["added"].append(f)
        elif f.status == "M":
            categories["modified"].append(f)
        elif f.status == "D":
            categories["deleted"].append(f)
        elif f.status == "R":
            categories["renamed"].append(f)
        else:
            categories["others"].append(f)
    return categories


def build_markdown(branch: str, base: str, commits: List[CommitInfo], files: List[DiffFile]) -> str:
    """Monta conteúdo em Markdown.

    Args:
        branch: Branch atual.
        base: Branch base.
        commits: Lista de commits.
        files: Lista de arquivos alterados.

    Returns:
        Texto em Markdown.
    """
    categories = categorize_files(files)
    now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: List[str] = []
    lines.append(f"# Nota de Implementações - branch {branch}")
    lines.append("")
    lines.append(f"Base: {base}")
    lines.append(f"Data de geração: {now}")
    lines.append("")
    lines.append("## Resumo")
    lines.append(f"- Commits: {len(commits)}")
    total_files = len(files)
    lines.append(f"- Arquivos alterados: {total_files} (Adicionados: {len(categories['added'])}, Modificados: {len(categories['modified'])}, Removidos: {len(categories['deleted'])}, Renomeados: {len(categories['renamed'])})")
    lines.append("")
    lines.append("## Commits")
    if commits:
        for c in commits:
            lines.append(f"- {c.hash} ({c.date}) {c.subject} — autor: {c.author}")
    else:
        lines.append("*(Sem commits exclusivos em relação à base)*")
    lines.append("")
    lines.append("## Arquivos por categoria")
    for cat_label, key in [("Adicionados", "added"), ("Modificados", "modified"), ("Removidos", "deleted"), ("Renomeados", "renamed"), ("Outros", "others")]:
        group = categories[key]
        if not group:
            continue
        lines.append(f"### {cat_label}")
        for f in group:
            if f.status == "R" and f.extra:
                lines.append(f"- {f.extra} -> {f.path}")
            else:
                lines.append(f"- {f.path}")
        lines.append("")
    lines.append("## Observações")
    lines.append("(Adicionar detalhes manuais conforme necessário.)")
    return "\n".join(lines).rstrip() + "\n"


def build_json(branch: str, base: str, commits: List[CommitInfo], files: List[DiffFile]) -> str:
    """Monta conteúdo em JSON.

    Args:
        branch: Branch atual.
        base: Branch base.
        commits: Lista de commits.
        files: Lista de arquivos alterados.

    Returns:
        JSON formatado.
    """
    categories = categorize_files(files)
    payload = {
        "branch": branch,
        "base": base,
        "generated_at": dt.datetime.now(dt.UTC).isoformat().replace("+00:00", "Z"),
        "stats": {
            "commits": len(commits),
            "files_total": len(files),
            "files_added": len(categories["added"]),
            "files_modified": len(categories["modified"]),
            "files_deleted": len(categories["deleted"]),
            "files_renamed": len(categories["renamed"]),
            "files_others": len(categories["others"]),
        },
        "commits": [c.__dict__ for c in commits],
        "files": [f.__dict__ for f in files],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def parse_args() -> argparse.Namespace:
    """Faz o parse dos argumentos de linha de comando."""
    parser = argparse.ArgumentParser(description="Gera nota de implementações da branch atual.")
    parser.add_argument("--base", help="Branch base (ex: origin/develop)")
    parser.add_argument("--output", help="Arquivo de saída")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown", help="Formato de saída (padrão: markdown)")
    return parser.parse_args()


def ensure_git_repo():
    """Valida se diretório atual é um repositório git."""
    try:
        run_git(["rev-parse", "--is-inside-work-tree"])
    except RuntimeError as e:
        raise RuntimeError("Diretório atual não é um repositório git válido.") from e


def main() -> int:
    """Função principal.

    Returns:
        Código de saída (0 sucesso, !=0 erro).
    """
    try:
        ensure_git_repo()
        args = parse_args()
        base = detect_base_branch(args.base)
        branch = get_current_branch()
        commits = collect_commits(base)
        diff_files = collect_diff_files(base)
        if args.format == "markdown":
            content = build_markdown(branch, base, commits, diff_files)
            default_name = f"implementacoes_{branch}.md"
        else:
            content = build_json(branch, base, commits, diff_files)
            default_name = f"implementacoes_{branch}.json"
        output_path = args.output or default_name
        FileIO.create(output_path, content).save(exist_ok=True)
        print(output_path)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

