import mock
import unittest

import reactive.designate_utils as dutils

DOMAIN_LIST = b"""
b78d458c-2a69-47e7-aa40-a1f9ff8809e3 frodo.com. 1467534540
fa5111a7-5659-45c6-a101-525b4259e8f0 bilbo.com. 1467534855
"""

SERVER_LIST = b"""
77eee1aa-27fc-49b9-acca-3faf68126530 ns1.www.example.com.
"""


class TestDesignateUtils(unittest.TestCase):

    def setUp(self):
        self._patches = {}
        self._patches_start = {}

    def tearDown(self):
        for k, v in self._patches.items():
            v.stop()
            setattr(self, k, None)
        self._patches = None
        self._patches_start = None

    def patch(self, obj, attr, return_value=None):
        mocked = mock.patch.object(obj, attr)
        self._patches[attr] = mocked
        started = mocked.start()
        started.return_value = return_value
        self._patches_start[attr] = started
        setattr(self, attr, started)

    def test_run_command(self):
        self.patch(dutils, 'get_environment')
        self.patch(dutils.subprocess, 'Popen')
        process_mock = mock.Mock()
        attrs = {
            'communicate.return_value': ('ouput', 'error'),
            'returncode': 0}
        process_mock.configure_mock(**attrs)
        self.Popen.return_value = process_mock
        self.Popen.returncode.return_value = 0
        dutils.run_command(['ls'])
        self.Popen.assert_called_once_with(
            ['ls'],
            env=None,
            stderr=-1,
            stdout=-1)

    def test_run_command_fail(self):
        self.patch(dutils, 'get_environment')
        self.patch(dutils.subprocess, 'Popen')
        process_mock = mock.Mock()
        attrs = {
            'communicate.return_value': ('ouput', 'error'),
            'returncode': 1}
        process_mock.configure_mock(**attrs)
        self.Popen.return_value = process_mock
        self.Popen.returncode.return_value = 0
        with self.assertRaises(RuntimeError):
            dutils.run_command(['ls'])

    def test_get_environment(self):
        text_file_data = '\n'.join(["export a=b", "export c=d"])
        with mock.patch('builtins.open',
                        mock.mock_open(read_data=text_file_data),
                        create=True) as m:
            m.return_value.__iter__.return_value = text_file_data.splitlines()
            with open('filename', 'rU'):
                self.assertEqual(
                    dutils.get_environment({}),
                    {'a': 'b', 'c': 'd'})

    def test_get_server_id(self):
        self.patch(dutils, 'get_servers')
        self.get_servers.return_value = {'server1': {'id': 'servid1'}}
        self.assertEqual(dutils.get_server_id('server1'), 'servid1')
        self.assertEqual(dutils.get_server_id('server2'), None)

    def test_get_domain_id(self):
        self.patch(dutils, 'get_domains')
        self.get_domains.return_value = {'domain1': {'id': 'domainid1'}}
        self.assertEqual(dutils.get_domain_id('domain1'), 'domainid1')
        self.assertEqual(dutils.get_domain_id('domain2'), None)

    def test_create_server(self):
        _server_ids = ['servid1', None]
        self.patch(dutils, 'get_server_id')
        self.patch(dutils, 'display')
        self.get_server_id.side_effect = lambda x: _server_ids.pop()
        self.patch(dutils, 'run_command')
        self.run_command.return_value = ('out', 'err')
        dutils.create_server('server1')
        cmd = [
            'designate', 'server-create',
            '--name', 'server1',
            '-f', 'value',
        ]
        self.run_command.assert_called_with(cmd)
        self.display.assert_called_with('servid1')

    def test_create_domain(self):
        _domain_ids = ['domainid1', None]
        self.patch(dutils, 'get_domain_id')
        self.patch(dutils, 'display')
        self.get_domain_id.side_effect = lambda x: _domain_ids.pop()
        self.patch(dutils, 'run_command')
        self.run_command.return_value = ('out', 'err')
        dutils.create_domain('dom1', 'email1')
        cmd = [
            'designate', 'domain-create',
            '--name', 'dom1',
            '--email', 'email1',
            '-f', 'value',
        ]
        self.run_command.assert_called_with(cmd)
        self.display.assert_called_with('domainid1')

    def test_delete_domain(self):
        self.patch(dutils, 'get_domain_id', return_value='dom1')
        self.patch(dutils, 'run_command')
        dutils.delete_domain('dom1')
        self.run_command.assert_called_with(['domain-delete', 'dom1'])

    def test_get_domains(self):
        self.patch(dutils, 'run_command')
        self.run_command.return_value = (DOMAIN_LIST, 'err')
        expect = {
            'bilbo.com.':
                {
                    'id': 'fa5111a7-5659-45c6-a101-525b4259e8f0',
                    'serial': '1467534855'},
            'frodo.com.':
                {
                    'id': 'b78d458c-2a69-47e7-aa40-a1f9ff8809e3',
                    'serial': '1467534540'}}
        self.assertEqual(dutils.get_domains(), expect)
        self.run_command.assert_called_with(
            ['designate', 'domain-list', '-f', 'value'])

    def test_get_servers(self):
        self.patch(dutils, 'run_command')
        self.run_command.return_value = (SERVER_LIST, 'err')
        expect = {
            'ns1.www.example.com.': {
                'id': '77eee1aa-27fc-49b9-acca-3faf68126530'}}
        self.assertEqual(dutils.get_servers(), expect)
        self.run_command.assert_called_with(
            ['designate', 'server-list', '-f', 'value'])
