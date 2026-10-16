"""APP-02 requirement fixtures, no native inventory persisted."""
import threading
import time
import unittest
from unittest.mock import patch

from cereja.ledger.app import Ledger
from cereja.ui.events import KeyEvent, ResizeEvent
from cereja.ui.terminal import TerminalSession
from cereja.ui.testing import VirtualBackend
from cereja.system.hardware.models import HardwareInfo, CPUInfo, OperatingSystemInfo, GPUInfo


class SystemProjectionTest(unittest.TestCase):
    def test_typed_partial_missing_and_privacy(self):
        from cereja.ledger.system import project
        result = project(HardwareInfo(cpu=CPUInfo(name='fixture', cores=0, identifier='SECRET'),
                                     os=OperatingSystemInfo(name='Test OS', hostname='SECRET')),
                         ('os', 'cpu', 'gpu'))
        self.assertIn('[os]', result)
        self.assertIn('cores: 0', result)
        self.assertIn('logical_processors: Unavailable', result)
        self.assertIn('[gpu]\nUnavailable', result)
        self.assertNotIn('SECRET', result)
        self.assertNotIn('[bios]', result)

    def test_bounded_safe_unicode_and_wrong_types(self):
        from cereja.ledger.system import project
        result = project(HardwareInfo(gpus=(GPUInfo(name='界e\u0301\x1b' * 20000),) * 100), ('gpu',))
        self.assertLessEqual(len(result.encode('utf-8')), 12288)
        self.assertIn('truncated', result.lower())
        self.assertNotIn('\x1b', result)
        with self.assertRaises(TypeError):
            project({'cpu': {}}, ('cpu',))

    def test_section_validation(self):
        from cereja.ledger.system import parse_sections
        self.assertEqual(parse_sections('cpu,os'), ('os', 'cpu'))
        for text in ('', 'all', 'cpu,cpu', 'cpu,', 'cpu SECRET', 'full'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_sections(text)


class SystemLedgerTest(unittest.TestCase):
    def app(self):
        session = TerminalSession(VirtualBackend())
        session.__enter__()
        self.addCleanup(session.close)
        app = Ledger(session)
        self.addCleanup(app.close)
        return app

    def finish(self, app):
        deadline = time.monotonic() + 3
        while app.bridge.active and time.monotonic() < deadline:
            app.loop.turn()
            app.refresh()
            time.sleep(.001)
        self.assertFalse(app.bridge.active)
        app.refresh()

    def test_discovery_form_help_do_not_collect(self):
        with patch('cereja.system.hardware.info', side_effect=AssertionError('automatic collection')):
            app = self.app()
            for command in ('/system', '/help system', '/home', '/tools'):
                app.composer.set_selection(0, len(app.composer.text))
                app.composer.insert(command)
                app.submit()
                while app.overlays.top:
                    app.overlays.close()
            self.assertFalse(app.bridge.active)

    def test_explicit_run_busy_navigation_elapsed_and_final(self):
        app = self.app()
        prior = app.results.current
        app.results.select(prior.identity)
        app.results.select_text()
        selection = prior.selection
        app.focus.focus('content')
        app.composer.insert('draft')
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def collect(**kwargs):
            self.assertEqual(kwargs, dict(detail='basic', include_sensitive=False, sections=('os', 'cpu')))
            entered.set()
            if not release.wait(2):
                raise RuntimeError('watchdog')
            return HardwareInfo(cpu=CPUInfo(name='fixture'))
        with patch('cereja.system.hardware.info', side_effect=collect) as call:
            app._system('cpu,os')
            self.assertTrue(entered.wait(1))
            app.loop.turn()
            self.assertFalse(app.bridge.snapshot.cancellable)
            self.assertEqual(app.bridge.exit_choices, ('return', 'wait'))
            app._system('cpu')
            self.assertEqual(call.call_count, 1)
            self.assertIn('Nothing was queued', app.notice)
            app.handle(KeyEvent('c', modifiers=frozenset({'ctrl'})))
            self.assertFalse(app.exit_open)
            self.assertIs(prior.selection, selection)
            app.handle(ResizeEvent(80, 24))
            app.focus.focus('composer')
            app.handle(KeyEvent('x', text='x'))
            time.sleep(.02)
            app.render()
            self.assertIn('elapsed', app.activity.content.text)
            self.assertFalse(app.progress.determinate)
            release.set()
            self.finish(app)
        self.assertEqual(app.composer.text, 'draftx')
        self.assertIs(app.results.current, prior)
        self.assertIs(prior.selection, selection)
        block = app.results.blocks[-1]
        self.assertEqual(block.state, 'Succeeded')
        self.assertIn('[cpu]', block.content.text)
        self.assertIn('Collection duration:', block.content.text)
        self.assertIsNone(app.activity.timer_id)

    def test_error_retains_prior_and_omits_exception_secret(self):
        app = self.app()
        prior = app.results.append('/system', 'prior snapshot')
        with patch('cereja.system.hardware.info', side_effect=RuntimeError('SECRET host/path')):
            app._system('cpu')
            self.finish(app)
        self.assertIn(prior, app.results.blocks)
        block = app.results.blocks[-1]
        self.assertEqual(block.state, 'Failed')
        self.assertIn('RuntimeError', block.content.text)
        self.assertNotIn('SECRET', block.content.text)


    def test_actual_form_submit_and_invalid_no_worker(self):
        app = self.app()
        app.composer.insert('/system')
        app.submit()
        form = app.overlays.top
        field = form.input('sections')
        field.set_selection(0, len(field.text))
        field.insert('cpu,invalid')
        with patch('cereja.system.hardware.info', return_value=HardwareInfo()) as call:
            app.focus.focus('@primary')
            app.handle(KeyEvent('enter'))
            self.assertFalse(app.bridge.active)
            self.assertTrue(form.errors)
            field.set_selection(0, len(field.text))
            field.insert('cpu')
            app.handle(KeyEvent('enter'))
            self.finish(app)
            self.assertEqual(call.call_count, 1)
            self.assertIn('Unavailable', app.results.blocks[-1].content.text)

    def test_publication_failure_and_cleanup_failure_remain_distinct(self):
        from cereja.ui.events import OperationResultEvent
        from cereja.ledger.system import collect
        app = self.app()
        original = app.loop.wait_post
        def broken(event, **kwargs):
            if type(event) is OperationResultEvent:
                raise RuntimeError('SECRET publication')
            return original(event, **kwargs)
        with patch('cereja.system.hardware.info', return_value=HardwareInfo()), patch.object(app.loop, 'wait_post', side_effect=broken):
            app._system('cpu')
            self.finish(app)
        self.assertEqual(app.results.blocks[-1].state, 'Unavailable')
        self.assertNotIn('SECRET', app.results.blocks[-1].content.text)
        block = app.results.append('/system', 'requested', active=True)
        app._operation_block = block
        def cleanup():
            raise RuntimeError('SECRET cleanup')
        with patch('cereja.system.hardware.info', return_value=HardwareInfo()):
            app.bridge.start('System fixture', lambda ctx: collect(ctx, ('cpu',)), cleanup=cleanup)
            self.finish(app)
        self.assertEqual(block.state, 'CleanupFailed')
        self.assertNotIn('SECRET', block.content.text)

    def test_consumer_close_does_not_join_or_cancel_blocking_call(self):
        app = self.app()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def collect(**kwargs):
            entered.set()
            if not release.wait(2):
                raise RuntimeError('watchdog')
            return HardwareInfo()
        with patch('cereja.system.hardware.info', side_effect=collect):
            app._system('cpu')
            self.assertTrue(entered.wait(1))
            ui_thread = threading.get_ident()
            original_join = threading.Thread.join
            def checked_join(worker, *args, **kwargs):
                if threading.get_ident() == ui_thread:
                    raise AssertionError('UI join')
                return original_join(worker, *args, **kwargs)
            with patch.object(threading.Thread, 'join', checked_join):
                app.close()
            self.assertTrue(app.bridge.active)
            self.assertFalse(app.bridge.snapshot.cancellable)
            release.set()
            deadline = time.monotonic() + 2
            while app.bridge.active and time.monotonic() < deadline:
                time.sleep(.001)
            self.assertFalse(app.bridge.active)
            self.assertEqual(app.bridge.snapshot.delivery, 'unavailable')

    def test_stale_generation_and_exit_wait_reversible(self):
        from cereja.ui.events import OperationPhaseEvent
        app = self.app()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def collect(**kwargs):
            entered.set()
            if not release.wait(2):
                raise RuntimeError('watchdog')
            return HardwareInfo()
        with patch('cereja.system.hardware.info', side_effect=collect):
            app._system('cpu')
            self.assertTrue(entered.wait(1))
            app.loop.turn()
            state = app.bridge.snapshot
            self.assertFalse(app.bridge.handle(OperationPhaseEvent(state.source, state.generation + 1, 'Committing')))
            self.assertFalse(app.bridge.cancel())
            app._exit()
            app.focus.focus('wait')
            app.handle(KeyEvent('enter'))
            self.assertTrue(app.waiting)
            self.assertFalse(app.loop.stopped)
            app._exit()
            app.handle(KeyEvent('escape'))
            self.assertFalse(app.waiting)
            release.set()
            self.finish(app)
        self.assertFalse(app.loop.stopped)

    def test_presentation_dimensions_independent_and_no_post_completion_timer(self):
        from cereja.ui.terminal import CapabilityOptions
        for options in (CapabilityOptions(color=0), CapabilityOptions(unicode=False), CapabilityOptions(reduced_motion=True)):
            with self.subTest(options=options):
                session = TerminalSession(VirtualBackend(size=(40, 12), options=options))
                with session:
                    app = Ledger(session)
                    try:
                        with patch('cereja.system.hardware.info', return_value=HardwareInfo(cpu=CPUInfo(name='界e\u0301'))):
                            app._system('cpu')
                            self.finish(app)
                        app.render()
                        self.assertEqual(app.loop.timer_count, 0)
                        self.assertIn('界', app.results.blocks[-1].content.text)
                    finally:
                        app.close()


    def test_worker_start_failure_explicit_and_no_active_result(self):
        app = self.app()
        with patch.object(app.bridge, 'start', side_effect=RuntimeError('SECRET')):
            app._system('cpu')
        self.assertEqual(app.results.blocks[-1].state, 'Failed')
        self.assertFalse(app.results.blocks[-1].active)
        self.assertFalse(app.bridge.active)
        self.assertEqual(app.status.state, 'error')
        self.assertNotIn('SECRET', app.notice)

    def test_catalogue_unsupported_platform_reason_without_collection(self):
        from types import SimpleNamespace
        from cereja.ledger.catalogue import BY_NAME
        with patch('cereja.ledger.catalogue.sys', SimpleNamespace(platform='unsupported')):
            self.assertIn('Unavailable UI', BY_NAME['system'].badges)
            self.assertIn('Windows, Linux and macOS', BY_NAME['system'].description())
            self.assertEqual(BY_NAME['tree'].availability, 'Available UI')

    def test_complete_typed_fixture_all_sections_and_identity_exclusion(self):
        from cereja.system.hardware.models import SystemInfo, MemoryInfo, MotherboardInfo, BIOSInfo
        from cereja.ledger.system import project, SECTIONS
        result = project(HardwareInfo(
            system=SystemInfo(manufacturer='Vendor', model='Model', total_memory_bytes=1024,
                              serial_number='SECRET', hardware_uuid='SECRET', machine='SECRET'),
            os=OperatingSystemInfo(name='OS', hostname='SECRET', boot_time='SECRET'),
            cpu=CPUInfo(name='CPU', cores=4, identifier='SECRET'),
            memory=(MemoryInfo(capacity_bytes=1024, serial_number='SECRET', part_number='SECRET'),),
            gpus=(GPUInfo(name='GPU', adapter_memory_bytes=None),),
            motherboard=MotherboardInfo(product='Board', serial_number='SECRET'),
            bios=BIOSInfo(version='Firmware', serial_number='SECRET')), SECTIONS)
        for name in SECTIONS:
            self.assertIn('[' + name + ']', result)
        self.assertIn('total_memory_bytes: 1024', result)
        self.assertIn('adapter_memory_bytes: Unavailable', result)
        self.assertNotIn('SECRET', result)


if __name__ == '__main__':
    unittest.main()
