"""A failed dependency download must remain recoverable on the next setup run."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('bootstrap', Path(__file__).resolve().parents[1]/'pipeline/bootstrap.py')
bootstrap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bootstrap)

class BootstrapRecoveryTests(unittest.TestCase):
    def test_interrupted_clone_is_not_published_and_can_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'.toolchain/venv').mkdir(parents=True)
            calls = []
            fail_fetch = True
            def run(*args):
                nonlocal fail_fetch
                calls.append(tuple(map(str, args)))
                if 'clone' in args:
                    Path(args[-1]).mkdir()
                if 'fetch' in args and fail_fetch:
                    fail_fetch = False
                    raise subprocess.CalledProcessError(1, args)
            with patch.object(bootstrap, 'ROOT', root), patch.object(bootstrap, 'run', run), patch.object(bootstrap.subprocess, 'check_output', return_value=bootstrap.PIN['dpf_repository']+'\n'):
                with self.assertRaises(subprocess.CalledProcessError):
                    bootstrap.main()
                self.assertFalse((root/'.toolchain/dpf').exists())
                self.assertTrue((root/'.toolchain/dpf.pending').exists())
                bootstrap.main()
            self.assertTrue((root/'.toolchain/dpf').exists())
            self.assertFalse((root/'.toolchain/dpf.pending').exists())
            self.assertEqual(sum('clone' in args for args in calls), 1)

if __name__ == '__main__':
    unittest.main()
