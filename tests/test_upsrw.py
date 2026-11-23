"""upsrw write result handling with NUT, storage and notifications isolated.

Run with: python -m unittest discover -s tests -v
No NUT daemon, UPS or application database is required.
"""

from contextlib import ExitStack
import importlib
import logging
from pathlib import Path
import subprocess
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


APP_DIR = Path(__file__).resolve().parents[1] / 'nutify'


def module(name, **attributes):
    result = ModuleType(name)
    result.__path__ = [str(APP_DIR.joinpath(*name.split('.')))]
    result.__dict__.update(attributes)
    return result


class SetUpsVariableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Import only core.upsrw.upsrw; its package also registers Flask routes.
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.db = SimpleNamespace(
            ModelClasses=SimpleNamespace(UPSVariable=Mock()), session=Mock(),
        )
        cls.notify = Mock()
        cls.ups_config = SimpleNamespace(
            is_initialized=lambda: True, host='nut.example', name='ups',
        )
        modules = {name: module(name) for name in (
            'core', 'core.db', 'core.multi_nut', 'core.upsrw',
        )}
        modules.update({
            'core.db.ups': module('core.db.ups', db=cls.db, data_lock=threading.Lock()),
            'core.db.ups.utils': module('core.db.ups.utils', ups_config=cls.ups_config),
            'core.db.nut_parser': module('core.db.nut_parser',
                                         get_nut_configuration=lambda: {}),
            'core.logger': module('core.logger',
                                  ups_logger=logging.getLogger('upsrw-tests')),
            'core.socket': module('core.socket', notify_variable_update=cls.notify),
            'core.multi_nut.target_scope': module('core.multi_nut.target_scope',
                apply_target_scope=Mock(), resolve_settings_target_id=lambda value=None: value),
        })
        cls.stack.enter_context(patch.dict(sys.modules, modules))
        cls.upsrw = importlib.import_module('core.upsrw.upsrw')

    def setUp(self):
        self.db.session.reset_mock()
        self.notify.reset_mock()
        self.stack_test = ExitStack()
        self.addCleanup(self.stack_test.close)
        self.stack_test.enter_context(patch.object(self.upsrw.time, 'sleep'))
        # Initial read returns the old value; readback returns the written one.
        self.stack_test.enter_context(patch.object(self.upsrw, 'get_ups_variables', side_effect=[
            [{'name': 'battery.date', 'value': '2020/01/01'}],
            [{'name': 'battery.date', 'value': '2026/11/23'}],
        ]))

    def write(self, returncode, stdout='', stderr=''):
        result = subprocess.CompletedProcess(['upsrw'], returncode, stdout, stderr)
        with patch.object(self.upsrw.subprocess, 'run', return_value=result) as run:
            outcome = self.upsrw.set_ups_variable('battery.date', '2026/11/23')
        run.assert_called_once()
        self.assertIn('battery.date=2026/11/23', run.call_args.args[0])
        return outcome

    def assert_success(self, outcome):
        self.assertEqual(outcome, (True, 'Variable updated successfully'))
        self.db.session.commit.assert_called_once_with()
        self.notify.assert_called_once()
        self.assertTrue(self.notify.call_args.args[0]['success'])

    def assert_failure(self, outcome, message):
        self.assertEqual(outcome, (False, message))
        self.db.session.commit.assert_not_called()
        self.notify.assert_not_called()

    def test_zero_exit_without_output_is_success(self):
        self.assert_success(self.write(0))

    def test_zero_exit_with_ok_on_stderr_is_success(self):
        self.assert_success(self.write(0, stderr='OK\n'))

    def test_zero_exit_with_ok_on_stdout_is_success(self):
        self.assert_success(self.write(0, stdout='OK\n'))

    def test_zero_exit_with_warning_and_ok_is_success(self):
        self.assert_success(self.write(0, stderr='Warning: example\nOK\n'))

    def test_nonzero_exit_with_ok_is_failure(self):
        self.assert_failure(self.write(1, stderr='OK\n'), 'Error: OK\n')

    def test_nonzero_exit_with_access_denied_is_failure(self):
        stderr = 'Unexpected response from upsd: ERR ACCESS-DENIED\n'
        self.assert_failure(self.write(1, stderr=stderr), f'Error: {stderr}')


if __name__ == '__main__':
    unittest.main()
