import importlib.util
from pathlib import Path
import smtplib
import unittest
from unittest.mock import MagicMock, patch


SCRIPT = Path(__file__).resolve().parents[1] / 'tools/local-mail/send_mail.py'
SPEC = importlib.util.spec_from_file_location('local_mail', SCRIPT)
mail = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mail)


class MailTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(host='smtp.example.com', port=587, security='starttls',
                           username='test', sender='sender@example.com')
        self.message = mail.build_message(self.config, '任务完成', '结果：校验通过。')

    def test_starttls_before_auth_and_fixed_recipient(self):
        client = MagicMock()
        client.send_message.return_value = {}
        with patch.object(mail.smtplib, 'SMTP', return_value=client):
            result, code = mail.deliver(self.config, self.message, 'test-secret')
        self.assertEqual((result['status'], code), ('accepted', 0))
        self.assertEqual([call[0] for call in client.method_calls],
                         ['ehlo', 'starttls', 'ehlo', 'login', 'send_message', 'close'])
        self.assertEqual(client.send_message.call_args.kwargs['to_addrs'],
                         ['fanoykaka@outlook.com'])

    def test_no_plaintext_fallback_when_tls_fails(self):
        client = MagicMock()
        client.starttls.side_effect = smtplib.SMTPNotSupportedError('no TLS')
        with patch.object(mail.smtplib, 'SMTP', return_value=client):
            result, code = mail.deliver(self.config, self.message, 'test-secret')
        self.assertEqual((result['status'], code), ('not_sent', 1))
        client.login.assert_not_called()
        client.send_message.assert_not_called()

    def test_disconnect_during_send_is_unknown_and_never_retried(self):
        client = MagicMock()
        client.send_message.side_effect = smtplib.SMTPServerDisconnected('sensitive response')
        with patch.object(mail.smtplib, 'SMTP', return_value=client):
            result, code = mail.deliver(self.config, self.message, 'test-secret')
        self.assertEqual((result['status'], code), ('unknown', 2))
        self.assertNotIn('sensitive response', str(result))
        client.send_message.assert_called_once()

    def test_auth_failure_is_not_sent(self):
        client = MagicMock()
        client.login.side_effect = smtplib.SMTPAuthenticationError(535, b'sensitive')
        with patch.object(mail.smtplib, 'SMTP', return_value=client):
            result, code = mail.deliver(self.config, self.message, 'test-secret')
        self.assertEqual((result['status'], code), ('not_sent', 1))
        client.send_message.assert_not_called()

    def test_explicit_data_rejection(self):
        client = MagicMock()
        client.send_message.side_effect = smtplib.SMTPDataError(550, b'rejected')
        with patch.object(mail.smtplib, 'SMTP', return_value=client):
            result, code = mail.deliver(self.config, self.message, 'test-secret')
        self.assertEqual((result['status'], code), ('rejected', 1))

    def test_ssl_uses_verified_context(self):
        client = MagicMock()
        client.send_message.return_value = {}
        self.config.update(security='ssl', port=465)
        with patch.object(mail.smtplib, 'SMTP_SSL', return_value=client) as factory:
            result, _ = mail.deliver(self.config, self.message, 'test-secret')
        self.assertEqual(result['status'], 'accepted')
        self.assertTrue(factory.call_args.kwargs['context'].check_hostname)
        client.starttls.assert_not_called()

    def test_rejects_subject_header_injection(self):
        with self.assertRaises(ValueError):
            mail.build_message(self.config, 'Hello\nBcc: other@example.com', 'body')


if __name__ == '__main__':
    unittest.main()
