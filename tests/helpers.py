from contextlib import contextmanager


@contextmanager
def connected(signal, receiver):
    signal.connect(receiver)
    try:
        yield
    finally:
        signal.disconnect(receiver)
