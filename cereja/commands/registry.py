"""Static command metadata for the Cereja CLI.

This module must stay lightweight: command implementation modules are imported
only after a command is selected by the root dispatcher.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CommandSpec:
    name: str
    help: str
    module: str


COMMANDS = (
    CommandSpec("compress", "Compress a file or directory.", "cereja.commands.compress"),
    CommandSpec("decompress", "Decompress a file or directory archive.", "cereja.commands.decompress"),
    CommandSpec("encrypt", "Encrypt a file.", "cereja.commands.encrypt"),
    CommandSpec("decrypt", "Decrypt a file.", "cereja.commands.decrypt"),
    CommandSpec("tree", "Draw a repository tree.", "cereja.commands.tree"),
    CommandSpec("context", "Search or list bounded textual context.", "cereja.commands.context"),
    CommandSpec("security", "Inspect untrusted files without executing them.", "cereja.commands.security"),
    CommandSpec("http", "Send HTTP requests.", "cereja.commands.http"),
    CommandSpec("download", "Download files with streaming transfers.", "cereja.commands.download"),
    CommandSpec("system", "Inspect local system information.", "cereja.commands.system"),
    CommandSpec("privacy", "Run tools with process-scoped privacy policies.", "cereja.commands.privacy"),
    CommandSpec("module", "Manage Cereja module scaffolding.", "cereja.commands.module"),
)

_BY_NAME = {command.name: command for command in COMMANDS}


def get_command(name: str) -> CommandSpec:
    return _BY_NAME[name]
