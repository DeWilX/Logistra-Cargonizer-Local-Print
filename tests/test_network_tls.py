from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import patch
import network_tls
import updater


class NetworkTlsTests(unittest.TestCase):
    def test_packaged_certificate_is_explicitly_loaded(self):
        context = ssl.create_default_context()
        with tempfile.TemporaryDirectory() as folder:
            certificate = Path(folder) / 'cacert.pem'
            certificate.write_text('bundle sentinel')
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, '_MEIPASS', folder, create=True), patch.object(network_tls.ssl, 'create_default_context', return_value=context) as factory:
                self.assertIs(network_tls.verified_context(), context)
                factory.assert_called_once_with(cafile=str(certificate))
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)

    def test_update_opener_uses_verified_context_and_restricted_redirects(self):
        context = ssl.create_default_context()
        with patch.object(updater, 'verified_context', return_value=context):
            opener = updater.github_opener()
        https = next(handler for handler in opener.handlers if isinstance(handler, updater.urllib.request.HTTPSHandler))
        self.assertIs(https._context, context)
        self.assertTrue(any(isinstance(handler, updater.GitHubRedirect) for handler in opener.handlers))
        self.assertTrue(https._context.check_hostname)
        self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
