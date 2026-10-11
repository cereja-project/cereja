"""Official opt-in Ledger entry. Help and plain fallback never construct a UI loop."""
import argparse
import os
import sys


def create_parser():
    parser = argparse.ArgumentParser(prog='cereja ui', description='Cereja Ledger terminal application.')
    parser.add_argument('--plain', action='store_true', help='Print a bounded reference and exit; never read stdin.')
    parser.add_argument('--no-color', action='store_true', help='Disable color independently of Unicode/motion.')
    parser.add_argument('--ascii', action='store_true', help='Use ASCII presentation.')
    parser.add_argument('--reduced-motion', action='store_true', help='Disable decorative timers.')
    parser.add_argument('--low-bandwidth', action='store_true', help='Use the existing reduced frame/indicator ceilings.')
    parser.add_argument('--bracketed-paste', action='store_true',
                        help='Assert a POSIX terminal supporting bracketed paste (required for interactive Ledger).')
    return parser


def _plain(reason='Interactive Ledger requires cursor support and delimited paste.'):
    from cereja.ledger.catalogue import COMMANDS
    print('Cereja Ledger | plain reference')
    print(reason)
    print('No input consumed, history written or service started. Use cereja COMMAND --help for CLI help.')
    for entry in COMMANDS:
        print('/' + entry.name + ' [' + ' | '.join(entry.badges) + '] ' + entry.purpose)
    return 0


def main(argv=None):
    args = create_parser().parse_args(argv)
    if args.plain or not (sys.stdin.isatty() and sys.stdout.isatty()):
        return _plain()
    if os.name == 'nt':
        return _plain('Windows record input cannot distinguish paste from Enter. Interactive Ledger unavailable.')
    if os.name != 'posix' or not args.bracketed_paste:
        return _plain('Interactive Ledger needs POSIX bracketed paste. Use --bracketed-paste on a supporting terminal.')
    from cereja.ui.terminal import CapabilityOptions, TerminalSession
    options = CapabilityOptions(color=0 if args.no_color else None,
                                unicode=False if args.ascii else None,
                                reduced_motion=True if args.reduced_motion else None, paste=True)
    from cereja.ui.posix import PosixBackend as Backend
    with TerminalSession(Backend(options=options)) as session:
        if session.capabilities.plain:
            return _plain()
        from cereja.ledger.app import Ledger
        app = Ledger(session, low_bandwidth=args.low_bandwidth)
        app.run()
    return 0
