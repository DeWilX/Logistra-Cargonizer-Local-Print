"""Verified TLS using the certificate bundle shipped with frozen applications."""
from pathlib import Path
import ssl
import sys


def verified_context():
    certificate = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / 'cacert.pem'
    if getattr(sys, 'frozen', False) and certificate.is_file():
        return ssl.create_default_context(cafile=str(certificate))
    return ssl.create_default_context()
