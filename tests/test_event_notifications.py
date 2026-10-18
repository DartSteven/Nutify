"""Real upsmon delivery paths with bootstrap/storage and transports isolated.

Run with: python -m unittest discover -s tests -v
No NUT daemon, application database, SMTP server or Telegram bot is required.
"""

from contextlib import ExitStack
import importlib
import logging
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from flask import Flask
import pytz


APP_DIR = Path(__file__).resolve().parents[1] / 'nutify'


def module(name, **attributes):
    result = ModuleType(name)
    result.__path__ = [str(APP_DIR.joinpath(*name.split('.')))]
    result.__dict__.update(attributes)
    return result


class EventNotificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # ups_notifier is a command-line entrypoint that normally boots the full
        # app, patches eventlet, opens /var/log files and initializes NUT models.
        # Replace that bootstrap, while importing its actual event/channel code.
        cls.stack = ExitStack()
        cls.addClassCleanup(cls.stack.close)
        cls.app = Flask(__name__)
        cls.app.CACHE_TIMEZONE = pytz.UTC
        cls.app.config['SECRET_KEY'] = 'test-only-not-for-production'
        cls.server_name = Mock(return_value='Lab server')
        logger = logging.getLogger('notification-tests')
        model_classes = SimpleNamespace(
            UPSEvent=Mock(), NotificationSettings=Mock(), MailConfig=Mock(),
        )
        db = SimpleNamespace(ModelClasses=model_classes)
        settings = module('core.settings', get_server_name=cls.server_name,
                          MSMTP_PATH='/unused/msmtp', TLS_CERT_PATH='/unused/ca')
        modules = {name: module(name) for name in (
            'core.db', 'core.events', 'core.multi_nut', 'core.mail',
            'core.extranotifs', 'core.extranotifs.ntfy',
            'core.extranotifs.telegram', 'core.report',
        )}
        modules.update({
            'core': module('core', create_app=lambda: cls.app),
            'app': module('app', CACHE_TIMEZONE=pytz.UTC),
            'core.settings': settings,
            'core.settings.settings': settings,
            'core.logger': module('core.logger', system_logger=logger,
                                  mail_logger=logger, database_logger=logger),
            'core.db.ups': module('core.db.ups', db=db, data_lock=Mock(),
                                 get_ups_data=Mock(), UPSData=dict, UPSEvent=Mock(),
                                 get_ups_model=Mock(), get_static_model=Mock()),
            'core.db.ups.utils': module('core.db.ups.utils',
                                       ups_config=Mock(is_initialized=lambda: True)),
            'core.db.model_classes': module('core.db.model_classes',
                init_model_classes=Mock(), register_models_for_global_access=Mock()),
            'core.multi_nut.target_scope': module('core.multi_nut.target_scope',
                apply_target_scope=Mock(), resolve_settings_target_id=lambda value=None: value),
            'core.multi_nut.storage': module('core.multi_nut.storage', get_target_with_policy=Mock()),
            'core.multi_nut.storage_snapshots': module('core.multi_nut.storage_snapshots',
                extract_metric=Mock(), get_latest_target_snapshot=Mock(), infer_error_status=Mock()),
            'core.template_loader': module('core.template_loader', configure_template_loader=Mock()),
            'core.report.report': module('core.report.report', report_manager=SimpleNamespace()),
            'core.extranotifs.webhook': module('core.extranotifs.webhook', WebhookNotifier=Mock()),
            'core.extranotifs.webhook.webhook': module('core.extranotifs.webhook.webhook',
                                                    send_event_notification=Mock()),
        })
        cls.stack.enter_context(patch.dict(sys.modules, modules))
        cls.stack.enter_context(patch.dict('os.environ', SECRET_KEY='test-only-not-for-production'))
        cls.mail = importlib.import_module('core.mail.mail')
        modules['core.mail'].get_mail_config_model = cls.mail.get_mail_config_model
        modules['core.mail'].get_notification_settings_model = cls.mail.get_notification_settings_model
        ntfy = importlib.import_module('core.extranotifs.ntfy.ntfy')
        modules['core.extranotifs.ntfy'].NtfyNotifier = ntfy.NtfyNotifier
        with patch('eventlet.monkey_patch'), patch('os.makedirs'), \
                patch('logging.FileHandler', return_value=logging.NullHandler()):
            cls.notifier = importlib.import_module('core.events.ups_notifier')
        cls.stack.enter_context(cls.app.app_context())

    def setUp(self):
        self.server_name.reset_mock(return_value=True, side_effect=True)
        self.server_name.return_value = 'Lab server'
        self.stack_test = ExitStack()
        self.addCleanup(self.stack_test.close)
        self.stack_test.enter_context(patch.object(self.notifier, 'log_message'))
        self.stack_test.enter_context(patch.object(self.notifier, 'get_detailed_ups_info',
                                                   return_value={'ups_status': 'OB', 'battery_charge': '90%'}))
        self.stack_test.enter_context(patch.object(self.notifier, '_resolve_target_name',
                                                   return_value='Rack UPS'))

    def card(self, event='ONBATT'):
        return self.notifier.build_unified_notification_card_for_event(
            'ups@nut.example', event, target_id=7)

    def test_card_contains_configured_server_name(self):
        self.assertEqual(self.card()['context']['serverName'], 'Lab server')
        self.server_name.assert_called_once_with()

    def test_telegram_real_events_reach_transport(self):
        config = {'id': 1, 'bot_token': 'test-token', 'chat_id': '123', 'render_mode': 'text'}
        response = Mock(status_code=200, content=b'{}')
        response.json.return_value = {'ok': True}
        for event in ('ONBATT', 'ONLINE'):
            with self.subTest(event=event), patch('requests.post', return_value=response) as post:
                result = self.notifier.send_telegram_notification(
                    'ups@nut.example', event, config, target_id=7)
                self.assertTrue(result['success'], result)
                post.assert_called_once()
                payload = post.call_args.kwargs['json']
                self.assertEqual(payload['chat_id'], '123')
                self.assertIn('Lab server', payload['text'])
                self.assertIn('Rack UPS', payload['text'])
        self.assertNotIn('server_name', config)

    def test_upsmon_dispatch_sends_telegram_after_recording_event(self):
        config = {'id': 1, 'bot_token': 'test-token', 'chat_id': '123', 'render_mode': 'text'}
        response = Mock(status_code=200, content=b'{}')
        response.json.return_value = {'ok': True}
        with patch.object(self.notifier, 'resolve_target_id_for_ups_name', return_value=7), \
                patch.object(self.notifier, '_load_power_event_sanity_metrics', return_value=({}, False)), \
                patch.object(self.notifier, 'store_event_in_database', return_value=True) as record, \
                patch.object(self.notifier, 'get_enabled_notifications', return_value=[]), \
                patch.object(self.notifier, 'get_enabled_ntfy_configs', return_value=[]), \
                patch.object(self.notifier, 'get_enabled_telegram_configs', return_value=[config]), \
                patch.object(self.notifier, 'HAS_WEBHOOK', False), \
                patch('requests.post', return_value=response) as post:
            self.assertTrue(self.notifier.process_ups_event('ups@nut.example', 'ONBATT'))
        record.assert_called_once_with('ups@nut.example', 'ONBATT', target_id=7)
        post.assert_called_once()
        self.assertIn('Lab server', post.call_args.kwargs['json']['text'])

    def test_telegram_card_without_server_name_uses_settings(self):
        card = self.card()
        card['context']['serverName'] = ''
        with patch.object(self.notifier.TelegramNotifier, 'send_notification',
                          return_value={'success': True}) as send:
            result = self.notifier.send_telegram_notification('ups', 'ONBATT',
                {'bot_token': 'test-token', 'chat_id': '123'}, notification_card=card)
        self.assertTrue(result['success'], result)
        send.assert_called_once()

    def test_ntfy_card_without_server_name_uses_settings(self):
        card = self.card()
        card['context']['serverName'] = ''
        with patch.object(self.notifier.NtfyNotifier, 'send_notification',
                          return_value={'success': True}) as send:
            result = self.notifier.send_ntfy_notification('ups', 'ONBATT',
                {'server': 'https://ntfy.example', 'topic': 'ups'}, notification_card=card)
        self.assertTrue(result['success'], result)
        self.assertIn('Lab server', send.call_args.args[0])

    def send_mail(self, *, recipient='', sender='', username='', override=None):
        config = SimpleNamespace(id=1, enabled=True, is_default=True,
            smtp_server='smtp.example', smtp_port=25, username=username,
            password='', from_email=sender, to_email=recipient,
            provider='custom', tls=False, tls_starttls=False, render_mode='text')
        query = Mock()
        query.filter.return_value.first.return_value = config
        settings = SimpleNamespace(enabled=True, id_email=1)
        payload = {'target_id': 7, 'notification_card': self.card()}
        if override is not None:
            payload['to_email'] = override
        with patch.object(self.mail, 'get_mail_config_model', return_value=Mock()), \
                patch.object(self.mail, 'get_notification_settings_model', return_value=Mock()), \
                patch.object(self.mail, 'scoped_mail_query', return_value=(query, 7)), \
                patch.object(self.mail, 'ensure_notification_setting', return_value=settings), \
                patch.object(self.mail, 'send_email', return_value=(True, 'sent')) as send:
            result = self.mail.EmailNotifier.send_notification('ONBATT', payload)
        self.assertTrue(result[0], result)
        send.assert_called_once()
        return send.call_args.kwargs

    def test_mail_relay_uses_sender_when_recipient_and_username_are_empty(self):
        for recipient in (None, '', '   '):
            with self.subTest(recipient=recipient):
                sent = self.send_mail(recipient=recipient, sender='alerts@example.com')
                self.assertEqual(sent['to_addr'], ['alerts@example.com'])
                self.assertEqual(sent['smtp_settings']['username'], '')

    def test_mail_explicit_recipient_takes_precedence(self):
        sent = self.send_mail(recipient='owner@example.com', sender='alerts@example.com',
                              username='smtp-account')
        self.assertEqual(sent['to_addr'], ['owner@example.com'])

    def test_mail_event_recipient_takes_precedence(self):
        sent = self.send_mail(override='override@example.com', recipient='owner@example.com',
                              sender='alerts@example.com')
        self.assertEqual(sent['to_addr'], ['override@example.com'])

    def test_mail_sender_precedes_non_email_smtp_username(self):
        sent = self.send_mail(sender='alerts@example.com', username='smtp-account')
        self.assertEqual(sent['to_addr'], ['alerts@example.com'])

    def test_mail_username_remains_last_fallback(self):
        sent = self.send_mail(username='owner@example.com')
        self.assertEqual(sent['to_addr'], ['owner@example.com'])


if __name__ == '__main__':
    unittest.main()
