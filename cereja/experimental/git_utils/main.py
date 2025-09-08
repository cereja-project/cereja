from cereja.experimental.git_utils.repository import GitRepository
from cereja import conf

if __name__ == "__main__":
    print(conf.BASE_DIR)
    repo = GitRepository(repo_path=conf.BASE_DIR)

    print("Branch atual:", repo.current_branch)
    print("Todas locais:", repo.local_branches)
    print("Todas remotas:", repo.remote_branches)

    # Filtrar por padrão
    print("Locais feature/*:", repo.filter_local_branches("feature/*"))
    print("Remotas origin/bugfix/*:", repo.filter_remote_branches("origin/bugfix/*"))

    # Procurar branch por nome
    print("Encontrar 'develop':", repo.find_branch("develop"))