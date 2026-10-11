"""Curated discovery data. No service imports, reflection or invocation registry."""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    purpose: str
    ui: str
    cli: tuple[str, ...] = ()
    api: tuple[str, ...] = ()
    parameters: str = ''
    example: str = ''
    guide: str = ''

    @property
    def badges(self):
        return (self.ui,) + (('CLI',) if self.cli else ()) + (('Python API',) if self.api else ())

    def description(self):
        parts = [self.name + ' [' + ' | '.join(self.badges) + ']', self.purpose]
        if self.ui != 'Available UI':
            parts.append('Reference only. This Ledger does not execute this capability.')
        parts.extend('CLI: ' + entry for entry in self.cli)
        parts.extend('Python API: ' + entry for entry in self.api)
        if self.parameters:
            parts.append('Parameters: ' + self.parameters)
        if self.example:
            parts.append('Example (documentation only): ' + self.example)
        if self.guide:
            parts.append('Guide: ' + self.guide)
        return '\n'.join(parts)


COMMANDS = (
    Capability('home', 'Ledger: discover Cereja capabilities and inspect ephemeral results.', 'Available UI'),
    Capability('system', 'Inspect system information after explicit collection.', 'Planned UI',
               ('cereja system info',), ('cereja.system.hardware.info',),
               'Basic detail, optional sections; sensitive identifiers off.',
               'cereja system info --help', 'docs/guides/system-info.md'),
    Capability('tree', 'Inspect an explicit directory tree. No filesystem browser.', 'Planned UI',
               ('cereja tree',), ('cereja.system.render_repository_tree',),
               'Explicit path and depth. CLI/API render text; a bounded UI adapter is pending.',
               'cereja tree PATH --depth 3', 'docs/design/cereja-ui-operation-contracts.md'),
    Capability('context', 'Search text under explicit roots.', 'Planned UI',
               ('cereja context search',), ('cereja.system.search_text_context',),
               'Roots, query, extensions and limits. Result limits are not whole-scan bounds.',
               'cereja context search --root ROOT --query TEXT', 'docs/guides/context-cache.md'),
    Capability('compress', 'Compress/decompress files and directories.', 'Planned UI',
               ('cereja compress', 'cereja decompress'),
               ('cereja.hashtools.compress_file', 'cereja.hashtools.decompress_file',
                'cereja.hashtools.compress_dir', 'cereja.hashtools.decompress_dir'),
               'Mode, source, destination, format and publication policy. UI safety integration pending.',
               'cereja compress --help', 'docs/design/cereja-ui-operation-contracts.md'),
    Capability('download', 'Download to an explicit destination.', 'Planned UI',
               ('cereja download',), ('cereja.transfers.download',),
               'HTTP(S) URL and destination. No UI execution, resume or service Cancel claim.',
               'cereja download --help', 'docs/design/cereja-ui-operation-contracts.md'),
    Capability('examples', 'Bounded synthetic text/layout, input/selection and progress/feedback.', 'Available UI',
               parameters='Kind: text, input, progress. Progress steps: 1..20.',
               guide='docs/guides/ui-ledger.md'),
    Capability('tools', 'Informational CLI/API catalogue. Entries never invoke services.', 'Available UI'),
    Capability('diagnostics', 'Sanitized terminal policies and versions, without automatic export.', 'Available UI'),
    Capability('help', 'Keyboard help; F1 preserves the invoking draft and selection.', 'Available UI'),
)

REFERENCES = (
    Capability('HTTP', 'HTTP client reference.', 'Reference', ('cereja http',), ('cereja.http.Client',)),
    Capability('Encrypt/decrypt', 'Encryption command reference.', 'Reference',
               ('cereja encrypt', 'cereja decrypt')),
    Capability('Protect', 'Protected-code command reference.', 'Reference', ('cereja protect',)),
    Capability('Privacy', 'Process-scoped privacy command reference.', 'Reference', ('cereja privacy',)),
    Capability('Security', 'Static inspection command reference.', 'Reference', ('cereja security',)),
    Capability('Module', 'Module scaffolding command reference.', 'Reference', ('cereja module',)),
    Capability('Registry', 'Static CLI metadata; not an execution extension mechanism.', 'Reference',
               api=('cereja.commands.registry.COMMANDS',)),
)
BY_NAME = {entry.name: entry for entry in COMMANDS}


@dataclass(frozen=True, slots=True)
class Command:
    capability: Capability
    arguments: tuple[str, ...] = ()


def parse_command(text):
    """Only this finite grammar is accepted; errors never echo user arguments."""
    if not isinstance(text, str) or len(text) > 4096:
        raise ValueError('Command exceeds the 4096-character grammar limit')
    if any(ord(c) < 32 or ord(c) == 127 for c in text):
        raise ValueError('Use one command line; pasted newlines never submit')
    words = text.strip().split()
    if not words or not words[0].startswith('/') or words[0][1:] not in BY_NAME:
        raise ValueError('Unknown command. Use / or F1 for registered commands')
    capability = BY_NAME[words[0][1:]]
    args = tuple(words[1:])
    allowed = {'examples': ('text', 'input', 'progress'), 'help': tuple(BY_NAME)}
    if args and (len(args) != 1 or args[0] not in allowed.get(capability.name, ())):
        raise ValueError('Unsupported parameters. Submit the command alone for help or its form')
    return Command(capability, args)
