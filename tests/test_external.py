"""
Environment handed to external programs from a frozen build.

A PyInstaller bundle puts its own Qt on LD_LIBRARY_PATH. Leaking that into
xdg-open breaks kde-open, which is how sign-in silently stopped opening the
browser on KDE.
"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from utils import external  # noqa: E402

BUNDLE = '/tmp/_MEIabc123'


def frozen_env(**extra):
    env = {
        'HOME': '/home/user',
        'PATH': '/usr/bin:/bin',
        'LD_LIBRARY_PATH': BUNDLE,
        '_PYI_APPLICATION_HOME_DIR': BUNDLE,
        '_PYI_ARCHIVE_FILE': '/opt/app/anime-updater',
    }
    env.update(extra)
    return env


class ExternalEnvTests(unittest.TestCase):

    def run_frozen(self, env):
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(sys, 'frozen', True, create=True), \
                mock.patch.object(sys, '_MEIPASS', BUNDLE, create=True):
            return external.external_env()

    def test_drops_bundle_library_path(self):
        env = self.run_frozen(frozen_env())
        self.assertNotIn('LD_LIBRARY_PATH', env)

    def test_restores_original_library_path(self):
        env = self.run_frozen(frozen_env(LD_LIBRARY_PATH_ORIG='/opt/cuda/lib64'))
        self.assertEqual(env['LD_LIBRARY_PATH'], '/opt/cuda/lib64')
        self.assertNotIn('LD_LIBRARY_PATH_ORIG', env)

    def test_drops_bootloader_variables(self):
        env = self.run_frozen(frozen_env())
        self.assertFalse([key for key in env if key.startswith('_PYI_')])

    def test_filters_bundle_entries_from_path_lists(self):
        env = self.run_frozen(frozen_env(
            QT_PLUGIN_PATH=os.pathsep.join([f'{BUNDLE}/plugins', '/usr/lib64/qt6/plugins']),
        ))
        self.assertEqual(env['QT_PLUGIN_PATH'], '/usr/lib64/qt6/plugins')

    def test_keeps_unrelated_variables(self):
        env = self.run_frozen(frozen_env())
        self.assertEqual(env['HOME'], '/home/user')
        self.assertEqual(env['PATH'], '/usr/bin:/bin')

    def test_source_checkout_is_untouched(self):
        source_env = {'LD_LIBRARY_PATH': '/opt/lib', 'HOME': '/home/user'}
        with mock.patch.dict(os.environ, source_env, clear=True):
            if hasattr(sys, 'frozen'):
                self.skipTest('running frozen')
            self.assertEqual(external.external_env(), source_env)


if __name__ == '__main__':
    unittest.main()
