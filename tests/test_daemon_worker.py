"""Standalone local worker lock tests without a rendering dependency."""
import tempfile
import unittest
from pathlib import Path
from scripts.daemon_worker import WorkerLock


class LocalWorkerLockTests(unittest.TestCase):
    def test_prevent_two_workers_on_same_local_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "runtime" / "rfactory.lock"
            with WorkerLock(file):
                with self.assertRaises(RuntimeError):
                    with WorkerLock(file):
                        pass
            with WorkerLock(file):
                self.assertTrue(file.exists())

    def test_exception_releases_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/"worker.lock"
            with self.assertRaises(ValueError):
                with WorkerLock(file):
                    raise ValueError("simulated worker failure")
            with WorkerLock(file):
                self.assertTrue(file.exists())


if __name__=="__main__":
    unittest.main()
