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

from __future__ import absolute_import
from __future__ import print_function

import contextlib
import unittest

import mock

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


class TestOpenStackDesignate(Helper):

    def test_install(self):
        self.patch(designate.DesignateCharm.singleton, 'install')
        designate.install()
        self.install.assert_called_once_with()

    def test_db_sync_done(self):
        self.patch(designate.DesignateCharm.singleton, 'db_sync_done')
        designate.db_sync_done()
        self.db_sync_done.assert_called_once_with()

    def test_db_sync(self):
        self.patch(designate.DesignateCharm.singleton, 'db_sync')
        designate.db_sync()
        self.db_sync.assert_called_once_with()

    def test_render_base_config(self):
        self.patch(designate.DesignateCharm.singleton, 'render_base_config')
        designate.render_base_config('interfaces_list')
        self.render_base_config.assert_called_once_with('interfaces_list')

    def test_domain_init_done(self):
        self.patch(designate.DesignateCharm.singleton, 'domain_init_done')
        designate.domain_init_done()
        self.domain_init_done.assert_called_once_with()

    def test_render_full_config(self):
        self.patch(designate.DesignateCharm.singleton, 'render_full_config')
        designate.render_full_config('interfaces_list')
        self.render_full_config.assert_called_once_with('interfaces_list')

    def test_register_endpoints(self):
        self.patch(designate.DesignateCharm, 'service_type',
                   new_callable=mock.PropertyMock)
        self.patch(designate.DesignateCharm, 'region',
                   new_callable=mock.PropertyMock)
        self.patch(designate.DesignateCharm, 'public_url',
                   new_callable=mock.PropertyMock)
        self.patch(designate.DesignateCharm, 'internal_url',
                   new_callable=mock.PropertyMock)
        self.patch(designate.DesignateCharm, 'admin_url',
                   new_callable=mock.PropertyMock)
        self.service_type.return_value = 'type1'
        self.region.return_value = 'region1'
        self.public_url.return_value = 'public_url'
        self.internal_url.return_value = 'internal_url'
        self.admin_url.return_value = 'admin_url'
        keystone = mock.MagicMock()
        designate.register_endpoints(keystone)
        keystone.register_endpoints.assert_called_once_with(
            'type1', 'region1', 'public_url', 'internal_url', 'admin_url')

    def test_configure_ha_resources(self):
        self.patch(designate.DesignateCharm.singleton, 'db_sync')
        designate.db_sync()
        self.db_sync.assert_called_once_with()

    def test_restart_all(self):
        self.patch(designate.DesignateCharm.singleton, 'restart_all')
        designate.restart_all()
        self.restart_all.assert_called_once_with()

    def test_configure_ssl(self):
        self.patch(designate.DesignateCharm.singleton, 'configure_ssl')
        designate.configure_ssl()
        self.configure_ssl.assert_called_once_with(None)

    def test_update_peers(self):
        self.patch(designate.DesignateCharm.singleton, 'update_peers')
        designate.update_peers('cluster')
        self.update_peers.assert_called_once_with('cluster')

    def test_render_rndc_keys(self):
        self.patch(designate.DesignateCharm.singleton, 'render_rndc_keys')
        designate.render_rndc_keys()
        self.render_rndc_keys.assert_called_once_with()

    def test_assess_status(self):
        self.patch(designate.DesignateCharm.singleton, 'assess_status')
        designate.assess_status()
        self.assess_status.assert_called_once_with()


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
                       'nameserver': 'nameserver_unit_1',
                       'pool_target': 'nameserver_unit_1'},
                      {'address': 'addr2',
                       'nameserver': 'nameserver_unit_2',
                       'pool_target': 'nameserver_unit_2'}]
            self.assertEqual(a.pool_config, expect)
            self.assertEqual(
                a.pool_targets,
                'nameserver_unit_1, nameserver_unit_2')
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


class TestDesignateAdapters(Helper):

    def test_designate_adapters(self):
        self.patch(
            designate.openstack_adapters.APIConfigurationAdapter,
            'get_network_addresses')
        cluster_relation = mock.MagicMock()
        cluster_relation.relation_name = 'cluster'
        amqp_relation = mock.MagicMock()
        amqp_relation.relation_name = 'amqp'
        shared_db_relation = mock.MagicMock()
        shared_db_relation.relation_name = 'shared_db'
        other_relation = mock.MagicMock()
        other_relation.relation_name = 'other'
        other_relation.thingy = 'help'
        # verify that the class is created with a DesignateConfigurationAdapter
        b = designate.DesignateAdapters([amqp_relation,
                                         cluster_relation,
                                         shared_db_relation,
                                         other_relation])
        # ensure that the relevant things got put on.
        self.assertTrue(
            isinstance(
                b.other,
                designate.openstack_adapters.OpenStackRelationAdapter))
        self.assertTrue(isinstance(b.options,
                                   designate.DesignateConfigurationAdapter))


class TestDesignateCharm(Helper):

    def test_install(self):
        self.patch(designate.DesignateCharm, 'configure_source')
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
            'nameservers': 'dnsserverrec1',
            'nova-domain': 'novadomain',
            'nova-domain-email': 'novaemail',
            'neutron-domain': 'neutrondomain',
            'neutron-domain-email': 'neutronemail',
        }
        self.patch(designate.DesignateCharm, 'ensure_api_responding')
        self.ensure_api_responding.return_value = True
        self.patch(designate.hookenv, 'is_leader', return_value=True)
        self.patch(designate.hookenv, 'leader_set')
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
            self.create_server.assert_called_once_with('dnsserverrec1')
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
