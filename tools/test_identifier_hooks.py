"""Offline synthetic hook checks; no project imports, credentials or transports."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / '.githooks'


class HookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        home = self.base / 'home'
        home.mkdir()
        # Allowlist environment: no inherited credentials, Git config or hooks.
        self.env = {
            'PATH': os.defpath,
            'HOME': str(home), 'USERPROFILE': str(home),
            'XDG_CONFIG_HOME': str(home),
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_ALLOW_PROTOCOL': '', 'GIT_TERMINAL_PROMPT': '0',
            'GIT_AUTHOR_NAME': 'Hook Test', 'GIT_COMMITTER_NAME': 'Hook Test',
            'GIT_AUTHOR_EMAIL': 'test@example.invalid',
            'GIT_COMMITTER_EMAIL': 'test@example.invalid',
        }
        if os.name == 'nt':
            # Git for Windows is located explicitly, not through inherited PATH.
            git = shutil.which('git')
            if not git:
                self.fail('Git for Windows is required')
            git_root = Path(git).resolve().parent.parent
            self.env['PATH'] = os.pathsep.join([
                str(Path(git).parent), str(git_root / 'usr' / 'bin'), os.defpath])
            if 'SystemRoot' in os.environ:
                self.env['SystemRoot'] = os.environ['SystemRoot']
        self.run_cmd('git', 'init', '--template=')
        shutil.copytree(SOURCE, self.repo / '.githooks')
        for path in (self.repo / '.githooks').iterdir():
            path.chmod(0o755)
        self.run_cmd('git', 'config', 'core.hooksPath', '.githooks')
        self.run_cmd('git', 'config', 'alias.stage-clean',
                     '!sh .githooks/stage_clean.sh')
        self.write('.gitignore', '*.Identifier\n')

    def run_cmd(self, *args, cwd=None, success=True):
        result = subprocess.run(args, cwd=cwd or self.repo, env=self.env,
                                input=b'', capture_output=True, timeout=20)
        if success:
            self.assertEqual(result.returncode, 0, result.stderr.decode())
        return result

    def write(self, name, content='synthetic\n'):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return path

    def test_commit_cleans_recursive_matches_and_preserves_boundaries(self):
        names = ['root.Identifier', 'deep/a b.Identifier', '-dash.Identifier']
        if os.name != 'nt':
            names.append('deep/line\nbreak.Identifier')
        matches = [self.write(name) for name in names]
        kept = [self.write(name) for name in
                ['keep.txt', 'keep.identifier', 'keep.Identifier.extra',
                 '.git/keep.Identifier', 'nested/.git/marker',
                 'nested/keep.Identifier', 'worktree/.git',
                 'worktree/keep.Identifier', 'directory.Identifier/keep.txt']]
        outside = self.base / 'outside'
        outside.mkdir()
        target = outside / 'keep.Identifier'
        target.write_text('synthetic', encoding='utf-8')
        if os.name != 'nt':
            (self.repo / 'external').symlink_to(outside, target_is_directory=True)
            (self.repo / 'link.Identifier').symlink_to(target)
        self.run_cmd('git', 'add', 'keep.txt')
        self.run_cmd('git', 'commit', '-m', 'synthetic commit')
        self.assertTrue(all(not path.exists() for path in matches))
        self.assertTrue(all(path.exists() for path in kept))
        self.assertTrue(target.exists())
        self.assertFalse((self.repo / 'link.Identifier').is_symlink())

    def test_force_staged_match_blocks_commit_until_removal_staged(self):
        match = self.write('deep/forced.Identifier')
        self.write('keep.txt')
        self.run_cmd('git', 'add', '-f', 'deep/forced.Identifier', 'keep.txt')
        result = self.run_cmd('git', 'commit', '-m', 'blocked', success=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'commit stopped', result.stderr)
        self.assertFalse(match.exists())
        self.run_cmd('git', 'stage-clean', '--all')
        self.run_cmd('git', 'commit', '-m', 'clean commit')
        tree = self.run_cmd('git', 'ls-tree', '-r', '--name-only', 'HEAD').stdout
        self.assertNotIn(b'forced.Identifier', tree)

    def test_staging_alias_preserves_subdirectory_context(self):
        self.write('root.txt')
        self.write('sub/keep.txt')
        match = self.write('elsewhere/remove.Identifier')
        self.run_cmd('git', 'stage-clean', '.', cwd=self.repo / 'sub')
        self.assertFalse(match.exists())
        staged = self.run_cmd('git', 'diff', '--cached', '--name-only').stdout
        self.assertEqual(staged, b'sub/keep.txt\n')

    def test_push_hook_cleans_without_changing_index_or_history(self):
        self.write('keep.txt')
        self.run_cmd('git', 'add', 'keep.txt')
        self.run_cmd('git', 'commit', '-m', 'baseline')
        match = self.write('force.Identifier')
        self.run_cmd('git', 'add', '-f', 'force.Identifier')
        before = self.run_cmd('git', 'write-tree').stdout
        head = self.run_cmd('git', 'rev-parse', 'HEAD').stdout
        # Invoke the hook directly: never execute a push, even to a local remote.
        self.run_cmd('sh', '.githooks/pre-push')
        self.assertFalse(match.exists())
        self.assertEqual(before, self.run_cmd('git', 'write-tree').stdout)
        self.assertEqual(head, self.run_cmd('git', 'rev-parse', 'HEAD').stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
