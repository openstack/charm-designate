# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import unittest

from unittest import mock

import charm.openstack.designate as designate


def FakeConfig(init_dict):

    def _config(key=None):
        return init_dict[key] if key else init_dict

    return _config


class Helper(unittest.TestCase):

    def setUp(self):
        self._patches = {}
        self._patches_start = {}
        self.ch_config_patch = mock.patch('charmhelpers.core.hookenv.config')
        self.ch_config = self.ch_config_patch.start()
        self.ch_config.side_effect = lambda: {'ssl_param': None}

    def tearDown(self):
        for k, v in self._patches.items():
            v.stop()
            setattr(self, k, None)
        self._patches = None
        self._patches_start = None
        self.ch_config_patch.stop()

    def patch(self, obj, attr, return_value=None, **kwargs):
        mocked = mock.patch.object(obj, attr, **kwargs)
        self._patches[attr] = mocked
        started = mocked.start()
        started.return_value = return_value
        self._patches_start[attr] = started
        setattr(self, attr, started)

    def patch_object(self, obj, attr, return_value=None, name=None, new=None):
        if name is None:
            name = attr
        if new is not None:
            mocked = mock.patch.object(obj, attr, new=new)
        else:
            mocked = mock.patch.object(obj, attr)
        self._patches[name] = mocked
        started = mocked.start()
        if new is None:
            started.return_value = return_value
        self._patches_start[name] = started
        setattr(self, name, started)


class TestDesignateDBAdapter(Helper):

    def fake_get_uri(self, prefix):
        return 'mysql://uri/{}-database'.format(prefix)

    def test_designate_uri(self):
        relation = mock.MagicMock()
        a = designate.DesignateDBAdapter(relation)
        self.patch(designate.DesignateDBAdapter, 'get_uri')
        self.get_uri.side_effect = self.fake_get_uri
        self.assertEqual(a.designate_uri, 'mysql://uri/designate-database')
        self.assertEqual(a.designate_pool_uri, 'mysql://uri/dpm-database')


class TestBindRNDCRelationAdapter(Helper):

    def test_slave_ips(self):
        relation = mock.MagicMock()
        relation.slave_ips.return_value = 'slave_ips_info'
        a = designate.BindRNDCRelationAdapter(relation)
        self.assertEqual(a.slave_ips, 'slave_ips_info')

    def test_pool_configs(self):
        relation = mock.MagicMock()
        _slave_ips = [
            {'unit': 'unit/1',
             'address': 'addr1'},
            {'unit': 'unit/2',
             'address': 'addr2'}]
        with mock.patch.object(designate.BindRNDCRelationAdapter,
                               'slave_ips', new=_slave_ips):
            a = designate.BindRNDCRelationAdapter(relation)
            expect = [{'address': 'addr1',
                       'nameserver': 'nameserver_unit',
                       'pool_target': 'nameserver_unit',
                       'rndc_key_file': '/etc/designate/rndc_unit.key'},
                      {'address': 'addr2',
                       'nameserver': 'nameserver_unit',
                       'pool_target': 'nameserver_unit',
                       'rndc_key_file': '/etc/designate/rndc_unit.key'}]
            self.assertEqual(a.pool_config, expect)
            self.assertEqual(
                a.pool_targets,
                'nameserver_unit, nameserver_unit')
            self.assertEqual(a.slave_addresses, 'addr1:53, addr2:53')

    def test_rndc_info(self):
        relation = mock.MagicMock()
        relation.rndc_info = 'rndcstuff'
        a = designate.BindRNDCRelationAdapter(relation)
        self.assertEqual(a.rndc_info, 'rndcstuff')


class TestDesignateConfigurationAdapter(Helper):

    def test_designate_configuration_adapter_pool_info(self):
        relation = mock.MagicMock()
        self.patch(
            designate.openstack_adapters.APIConfigurationAdapter,
            'get_network_addresses')
        test_config = {
            'dns_slaves': 'ip1:port1:key1 ip2:port2:key2',
        }
        with mock.patch.object(designate.openstack_adapters.hookenv, 'config',
                               new=lambda: test_config):
            a = designate.DesignateConfigurationAdapter(relation)
            expect = [{'address': 'ip1',
                       'nameserver': 'nameserver_ip1',
                       'pool_target': 'nameserver_ip1',
                       'rndc_key_file': '/etc/designate/rndc_ip1.key'},
                      {'address': 'ip2',
                       'nameserver': 'nameserver_ip2',
                       'pool_target': 'nameserver_ip2',
                       'rndc_key_file': '/etc/designate/rndc_ip2.key'}]
            self.assertEqual(a.pool_config, expect)
            self.assertEqual(a.pool_targets, 'nameserver_ip1, nameserver_ip2')
            self.assertEqual(a.slave_addresses, 'ip1:53, ip2:53')

    def test_designate_configuration_domains(self):
        relation = mock.MagicMock()
        self.patch(
            designate.openstack_adapters.APIConfigurationAdapter,
            'get_network_addresses')
        test_config = {
            'nova-domain': 'bob.com',
            'neutron-domain': 'bill.com',
        }
        domain_map = {
            'bob.com': 12,
            'bill.com': 13,
        }
        with mock.patch.object(designate.hookenv, 'config',
                               side_effect=FakeConfig(test_config)):
            self.patch(designate.DesignateCharm, 'get_domain_id')
            self.get_domain_id.side_effect = lambda x: domain_map.get(x)
            a = designate.DesignateConfigurationAdapter(relation)
            self.assertEqual(a.nova_domain_id, 12)
            self.assertEqual(a.neutron_domain_id, 13)

    def test_designate_configuration_daemon_args(self):
        relation = mock.MagicMock()
        self.patch(
            designate.openstack_adapters.APIConfigurationAdapter,
            'get_network_addresses')
        self.patch(designate.os.path, 'exists', return_value=True)
        a = designate.DesignateConfigurationAdapter(relation)
        self.assertEqual(
            a.nova_conf_args,
            '--config-file=/etc/designate/conf.d/nova_sink.cfg')
        self.assertEqual(
            a.neutron_conf_args,
            '--config-file=/etc/designate/conf.d/neutron_sink.cfg')
        self.patch(designate.os.path, 'exists', return_value=False)
        self.assertEqual(a.nova_conf_args, '')
        self.assertEqual(a.neutron_conf_args, '')

    def test_rndc_master_ip(self):
        relation = mock.MagicMock()
        self.patch(
            designate.openstack_adapters.APIConfigurationAdapter,
            'get_network_addresses')
        self.patch(designate.os_ip, 'resolve_address', return_value='intip')
        a = designate.DesignateConfigurationAdapter(relation)
        self.assertEqual(a.rndc_master_ip, 'intip')

    def test_also_notifies_hosts(self):
        relation = mock.MagicMock
        test_config = {
            'also-notifies': '10.0.0.1:53 10.0.0.2:10053',
        }
        with mock.patch.object(designate.hookenv, 'config',
                               side_effect=FakeConfig(test_config)):
            expect = [{'address': '10.0.0.1',
                       'port': '53'},
                      {'address': '10.0.0.2',
                       'port': '10053'}]
            a = designate.DesignateConfigurationAdapter(relation)
            self.assertEqual(a.also_notifies_hosts, expect)


class TestDesignateCharm(Helper):

    def test_install(self):
        self.patch(designate.DesignateCharm, 'configure_source')
        self.patch(designate.DesignateCharm, 'update_api_ports')
        self.ch_config.side_effect = lambda: {'openstack-origin': 'distro'}
        a = designate.DesignateCharm(release='mitaka')
        a.install()
        self.configure_source.assert_called_with()

    def test_render_base_config(self):
        self.patch(designate.DesignateCharm, 'haproxy_enabled')
        self.patch(
            designate.DesignateCharm,
            'render_with_interfaces')
        self.patch_object(designate.DesignateCharm, 'haproxy_enabled',
                          new=lambda x: True)
        a = designate.DesignateCharm(release='mitaka')
        a.render_base_config('interface_list')
        expect_configs = [
            '/root/novarc',
            '/etc/designate/designate.conf',
            '/etc/designate/rndc.key',
            '/etc/default/openstack',
            '/etc/haproxy/haproxy.cfg']
        self.render_with_interfaces.assert_called_with(
            'interface_list',
            configs=expect_configs)

    def test_render_full_config(self):
        self.patch(
            designate.DesignateCharm,
            'render_with_interfaces')
        a = designate.DesignateCharm(release='mitaka')
        a.render_full_config('interface_list')
        self.render_with_interfaces.assert_called_with('interface_list')

    def test_write_key_file(self):
        self.patch(designate.host, 'write_file')
        a = designate.DesignateCharm(release='mitaka')
        a.write_key_file('unit1', 'keydigest')
        self.write_file.assert_called_with(
            '/etc/designate/rndc_unit1.key',
            mock.ANY,
            owner='root',
            group='designate',
            perms=0o440)

    def test_render_rndc_keys(self):
        test_config = {
            'dns-slaves': '10.0.0.10:port1:key1 192.168.23.4:port2:key2',
        }
        self.patch(designate.DesignateCharm, 'write_key_file')
        with mock.patch.object(designate.hookenv, 'config',
                               side_effect=FakeConfig(test_config)):
            a = designate.DesignateCharm(release='mitaka')
            a.render_rndc_keys()
            calls = [
                mock.call('10_0_0_10', 'key1'),
                mock.call('192_168_23_4', 'key2'),
            ]
            self.write_key_file.assert_has_calls(calls)

    def test_rndc_keys(self):

        def fake_conversations():
            conversations = []
            Conversation = mock.Mock()
            Conversation.key = 'reactive.conversations.dns-backend:65.'
            'designate-bind-t1/1'
            Conversation.namespace = 'dns-backend:65'
            self.patch(Conversation, 'relation_ids',
                       return_value='dns-backend:65')
            Conversation.relation_name = 'dns-backend'
            Conversation.scope = 'designate-bind-t1/1'
            self.patch(Conversation, 'get_remote', return_value='rndckey1')
            conversations.append(Conversation)
            Conversation = mock.Mock()
            Conversation.key = 'reactive.conversations.dns-backend:66.'
            'designate-bind-t0/1'
            Conversation.namespace = 'dns-backend:66'
            self.patch(Conversation, 'relation_ids',
                       return_value='dns-backend:66')
            Conversation.relation_name = 'dns-backend'
            Conversation.scope = 'designate-bind-t0/1'
            self.patch(Conversation, 'get_remote', return_value='rndckey2')
            conversations.append(Conversation)
            return conversations

        mock_endpoint_from_flag = mock.MagicMock()
        mock_endpoint_from_flag.conversations.side_effect = fake_conversations

        def fake_endpoint_from_flag(*args, **kwargs):
            return mock_endpoint_from_flag

        relation = mock.MagicMock()
        self.patch(designate.DesignateCharm, 'write_key_file')
        self.patch(designate.relations, 'endpoint_from_flag',
                   side_effect=fake_endpoint_from_flag)

        designate.DesignateConfigurationAdapter(relation)
        d = designate.DesignateCharm()
        d.render_relation_rndc_keys()
        calls = [
            mock.call('designate_bind_t1', 'rndckey1'),
            mock.call('designate_bind_t0', 'rndckey2'),
        ]

        self.write_key_file.assert_has_calls(calls)

    def test_get_domain_id(self):
        self.patch(designate.DesignateCharm, 'ensure_api_responding')
        self.patch(designate.subprocess, 'check_output')
        self.check_output.return_value = b'hi\n'
        self.assertEqual(designate.DesignateCharm.get_domain_id('domain'),
                         'hi')
        self.check_output.assert_called_with(
            ['reactive/designate_utils.py',
             'domain-get', '--domain-name', 'domain'])

    def test_create_domain(self):
        self.patch(designate.DesignateCharm, 'ensure_api_responding')
        self.patch(designate.subprocess, 'check_call')
        designate.DesignateCharm.create_domain('domain', 'email')
        self.check_call.assert_called_with(
            ['reactive/designate_utils.py',
             'domain-create', '--domain-name', 'domain',
             '--email', 'email'])

    def test_create_server(self):
        self.patch(designate.subprocess, 'check_call')
        self.patch(designate.DesignateCharm, 'ensure_api_responding')
        designate.DesignateCharm.create_server('nameservername')
        self.check_call.assert_called_with(
            ['reactive/designate_utils.py',
             'server-create', '--server-name',
             'nameservername'])

    def test_domain_init_done(self):
        self.patch(designate.hookenv, 'leader_get')
        self.leader_get.return_value = True
        a = designate.DesignateCharm(release='mitaka')
        self.assertTrue(a.domain_init_done())
        self.leader_get.return_value = False
        a = designate.DesignateCharm(release='mitaka')
        self.assertFalse(a.domain_init_done())

    def test_create_initial_servers_and_domains(self):
        test_config = {
            'nameservers': 'dnsserverrec1. dnsserverrec2',
            'nova-domain': 'novadomain',
            'nova-domain-email': 'novaemail',
            'neutron-domain': 'neutrondomain',
            'neutron-domain-email': 'neutronemail',
        }
        self.patch(designate.DesignateCharm, 'ensure_api_responding')
        self.ensure_api_responding.return_value = True
        self.patch(designate.hookenv, 'is_leader', return_value=True)
        self.patch(designate.hookenv, 'leader_set')
        self.patch(designate.hookenv, 'leader_get', return_value=False)
        self.patch(designate.DesignateCharm, 'create_server')
        self.patch(designate.DesignateCharm, 'create_domain')

        @contextlib.contextmanager
        def fake_check_zone_ids(a, b):
            yield
        self.patch(designate.DesignateCharm, 'check_zone_ids',
                   new=fake_check_zone_ids)
        with mock.patch.object(designate.hookenv, 'config',
                               side_effect=FakeConfig(test_config)):
            designate.DesignateCharm.create_initial_servers_and_domains()
            self.create_server.assert_has_calls([mock.call('dnsserverrec1.'),
                                                 mock.call('dnsserverrec2.')])
            calls = [
                mock.call('novadomain', 'novaemail'),
                mock.call('neutrondomain', 'neutronemail')]
            self.create_domain.assert_has_calls(calls)

    def test_check_zone_ids_change(self):
        self.patch(designate.hookenv, 'leader_set')
        DOMAIN_LOOKSUPS = ['novaid1', 'neutronid1', 'novaid1', 'neutronid2']

        def fake_get_domain_id(a):
            return DOMAIN_LOOKSUPS.pop()
        self.patch(designate.DesignateCharm, 'get_domain_id',
                   side_effect=fake_get_domain_id)
        with designate.DesignateCharm.check_zone_ids('novadom', 'neutrondom'):
            pass
        self.leader_set.assert_called_once_with({'domain-init-done': mock.ANY})

    def test_check_zone_ids_nochange(self):
        self.patch(designate.hookenv, 'leader_set')
        DOMAIN_LOOKSUPS = ['novaid1', 'neutronid1', 'novaid1', 'neutronid1']

        def fake_get_domain_id(a):
            return DOMAIN_LOOKSUPS.pop()
        self.patch(designate.DesignateCharm, 'get_domain_id',
                   side_effect=fake_get_domain_id)
        with designate.DesignateCharm.check_zone_ids('novadom', 'neutrondom'):
            pass
        self.assertFalse(self.leader_set.called)

    def test_render_nrpe(self):
        self.patch_object(designate.nrpe, 'add_init_service_checks')
        charm_instance = designate.DesignateCharm(release='queens')
        charm_instance.render_nrpe()
        self.add_init_service_checks.assert_has_calls([
            mock.call().add_init_service_checks(
                mock.ANY,
                charm_instance.services,
                mock.ANY
            ),
        ])

    def test_add_nrpe_nameserver_checks(self):
        test_config = {
            'nameservers': '8.8.8.8. 9.9.9.9. ns1-example.com.',
        }
        charm_instance = designate.DesignateCharm(release='queens')
        self.patch_object(designate.hookenv, 'config')
        self.config.return_value = test_config
        self.patch_object(designate.nrpe, 'NRPE')
        nrpe_mock = mock.MagicMock()
        self.NRPE.return_value = nrpe_mock
        charm_instance.add_nrpe_nameserver_checks()
        nrpe_mock.add_check.assert_has_calls([
            mock.call(
                'nameserver-8.8.8.8',
                'Check the upstream DNS server.',
                'check_dns -H canonical.com -s 8.8.8.8',
            ),
            mock.call(
                'nameserver-9.9.9.9',
                'Check the upstream DNS server.',
                'check_dns -H canonical.com -s 9.9.9.9',
            ),
            mock.call(
                'nameserver-ns1-example.com',
                'Check the upstream DNS server.',
                'check_dns -H canonical.com -s ns1-example.com',
            ),
        ])
        nrpe_mock.write.assert_called_once_with()

    def test_remove_nrpe_nameserver_checks(self):
        charm_instance = designate.DesignateCharm(release='queens')
        self.patch_object(designate.hookenv, 'config')
        config_mock = mock.MagicMock()
        config_mock.changed.return_value = True
        config_mock.previous.return_value = 'previous-ns-1. previous-ns-2.'
        self.config.return_value = config_mock
        self.patch_object(designate.nrpe, 'NRPE')
        nrpe_mock = mock.MagicMock()
        self.NRPE.return_value = nrpe_mock
        charm_instance.remove_nrpe_nameserver_checks()
        nrpe_mock.remove_check.assert_has_calls([
            mock.call(
                shortname='nameserver-previous-ns-1'
            ),
            mock.call(
                shortname='nameserver-previous-ns-2'
            ),
        ])
        nrpe_mock.write.assert_called_once_with()


class TestDesignateQueensCharm(Helper):

    def test_upgrade(self):
        self.patch(designate.DesignateCharm, 'run_upgrade')
        self.patch(designate.relations, 'endpoint_from_flag')
        endpoint = mock.MagicMock()
        self.endpoint_from_flag.return_value = endpoint
        a = designate.DesignateCharmQueens(release='queens')
        a.run_upgrade()
        self.run_upgrade.assert_called_once_with(interfaces_list=None)
        endpoint.request_restart.assert_called_once_with()
