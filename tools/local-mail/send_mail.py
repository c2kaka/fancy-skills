#!/usr/bin/env python3
"""Send one task notification using TLS SMTP and a macOS Keychain credential."""

import argparse
import json
from pathlib import Path
import smtplib
import ssl
import subprocess
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid


DEFAULT_CONFIG = Path.home() / '.config/codex-mail/config.json'
RECIPIENT = 'fanoykaka@outlook.com'


def load_config(path):
    config = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(config, dict):
        raise ValueError('Configuration must be a JSON object')
    for key in ('host', 'username', 'sender', 'keychain_service'):
        value = config.get(key)
        if not isinstance(value, str) or not value.strip() or any(
            c in value for c in '\r\n\x00'
        ):
            raise ValueError(f'Invalid or missing configuration field: {key}')
    if config.get('security') not in ('ssl', 'starttls'):
        raise ValueError('security must be ssl or starttls; plaintext is unsupported')
    port = config.get('port')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('port must be an integer between 1 and 65535')
    if any(key in config for key in ('password', 'token', 'secret')):
        raise ValueError('Store credentials in Keychain, not the JSON configuration')
    return config


def credential(config):
    result = subprocess.run(
        ['/usr/bin/security', 'find-generic-password', '-s',
         config['keychain_service'], '-a', config['username'], '-w'],
        capture_output=True, timeout=30, check=False,
    )
    if result.returncode or not result.stdout.rstrip(b'\r\n'):
        raise ValueError('Keychain credential unavailable; unlock/authorize it locally')
    return result.stdout.rstrip(b'\r\n').decode('utf-8')


def build_message(config, subject, body):
    if not subject.strip() or '\r' in subject or '\n' in subject:
        raise ValueError('Subject must be a nonempty single line')
    if not body.strip():
        raise ValueError('Message body must not be empty')
    message = EmailMessage()
    message['From'] = config['sender']
    message['To'] = RECIPIENT
    message['Subject'] = subject
    message['Date'] = formatdate(localtime=True)
    message['Message-ID'] = make_msgid()
    message.set_content(body)
    return message


def deliver(config, message, password):
    context = ssl.create_default_context()
    client = None
    sending = False
    try:
        if config['security'] == 'ssl':
            client = smtplib.SMTP_SSL(config['host'], config['port'],
                                      timeout=30, context=context)
        else:
            client = smtplib.SMTP(config['host'], config['port'], timeout=30)
            client.ehlo()
            client.starttls(context=context)
            client.ehlo()
        client.login(config['username'], password)
        sending = True
        refused = client.send_message(message, from_addr=config['sender'],
                                      to_addrs=[RECIPIENT])
        if refused:
            return {'status': 'rejected', 'reason': 'recipient_refused'}, 1
        return {'status': 'accepted', 'message_id': message['Message-ID'],
                'recipient': RECIPIENT,
                'note': 'SMTP server accepted the message; inbox delivery is unverified'}, 0
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError) as error:
        return {'status': 'rejected', 'reason': type(error).__name__}, 1
    except (OSError, smtplib.SMTPException) as error:
        return {'status': 'unknown' if sending else 'not_sent',
                'reason': type(error).__name__,
                'note': 'No automatic retry; verify delivery before retrying an unknown outcome'}, 2 if sending else 1
    finally:
        if client is not None:
            # DATA acceptance is authoritative; a QUIT failure must not cause a resend.
            client.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=DEFAULT_CONFIG)
    parser.add_argument('--subject', required=True)
    parser.add_argument('--body-file', type=Path, help='UTF-8 file; otherwise read stdin')
    parser.add_argument('--send', action='store_true', help='Actually send; default is preview')
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        body = args.body_file.read_text(encoding='utf-8') if args.body_file else sys.stdin.read()
        message = build_message(config, args.subject, body)
        if not args.send:
            result, code = {'status': 'preview', 'sender': config['sender'],
                            'recipient': RECIPIENT, 'subject': args.subject, 'body': body}, 0
        else:
            result, code = deliver(config, message, credential(config))
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Do not echo service responses, config contents, or credential output.
        result, code = {'status': 'not_sent', 'reason': type(error).__name__,
                        'note': 'Check configuration, input file, and local Keychain access'}, 1
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == '__main__':
    sys.exit(main())
