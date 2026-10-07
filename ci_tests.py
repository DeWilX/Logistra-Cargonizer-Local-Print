"""Run offline tests and expose failures in GitHub check annotations."""
import os
import sys
import unittest

suite = unittest.defaultTestLoader.discover('tests')
result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
if os.environ.get('GITHUB_ACTIONS'):
    for test, traceback in result.failures + result.errors:
        message = (test.id() + '\n' + traceback)[-6000:]
        message = message.replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
        print('::error title=Offline test failure::' + message)
raise SystemExit(0 if result.wasSuccessful() else 1)
