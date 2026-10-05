import os
import tempfile


_test_home = tempfile.TemporaryDirectory(prefix='ptti-test-bootstrap-')


def pytest_configure():
    # backend.main exposes an ASGI app at import time; keep that bootstrap DB
    # isolated even before per-test tmp_path databases are constructed.
    os.environ['PTTI_ENV'] = 'test'
    os.environ['PTTI_DB'] = os.path.join(_test_home.name, 'bootstrap.db')
