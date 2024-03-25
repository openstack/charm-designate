from unittest import mock

import reactive.designate_handlers as handlers

import charms_openstack.test_utils as test_utils


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        # test that the hooks actually registered the relation expressions that
        # are meaningful for this interface: this is to handle regressions.
        # The keys are the function names that the hook attaches to.
        all_interfaces = (
            'dns-config.available',
            'shared-db.available',
            'identity-service.available',
            'coordinator-memcached.available',
            'amqp.available')
        hook_set = {
            'when': {
                'setup_amqp_req': ('amqp.connected', ),
                'setup_database': ('shared-db.connected', ),
                'maybe_setup_endpoint': ('identity-service.connected', ),
                'start_designate_services': ('config.rendered',
                                             'base-config.rendered', ),
                'expose_rndc_address': ('cluster.connected', ),
                'config_rendered': ('base-config.rendered', ),
                'configure_ssl': ('identity-service.available', ),
                'config_changed': ('config.changed', ),
                'cluster_connected': ('ha.connected', ),
                'create_servers_and_domains': (
                    all_interfaces + ('base-config.rendered', 'db.synched')),
                'configure_designate_full': (
                    all_interfaces + (
                        'db.synched', 'pool-manager-cache.synched')),
                'run_db_migration': (
                    all_interfaces + ('base-config.rendered', )),
                'sync_pool_manager_cache': (
                    all_interfaces + ('base-config.rendered', )),
                'configure_designate_basic': all_interfaces,
                'expose_endpoint': ('dnsaas.connected', ),
                'remote_pools_updated': (
                    'leadership.changed.pool-yaml-hash', ),
                'reset_shared_db': ('shared-db.setup', ),
                'configure_nrpe': ('base-config.rendered', ),
                'configure_dns_backend_rndc_keys': (
                    all_interfaces + ('dns-backend.available', 'db.synched')),
            },
            'when_not': {
                'setup_amqp_req': ('is-update-status-hook', ),
                'setup_database': ('shared-db.setup', ),
                'config_rendered': ('config.rendered', ),
                'install_packages': ('installed', ),
                'run_db_migration': ('db.synched', ),
                'sync_pool_manager_cache': ('pool-manager-cache.synched', ),
                'configure_designate_basic': ('base-config.rendered', ),
                'create_servers_and_domains': ('domains.created', ),
                'run_assess_status_on_every_hook': (
                    'dont-set-assess-status', ),
                'reset_shared_db': ('shared-db.connected', ),
                'configure_nrpe': ('is-update-status-hook', ),
                'set_dns_config_available': ('is-update-status-hook', ),
                'start_designate_services': ('is-update-status-hook', ),
                'maybe_setup_endpoint': ('is-update-status-hook', ),
                'expose_endpoint': ('is-update-status-hook', ),
                'configure_designate_full': ('is-update-status-hook', ),
                'expose_rndc_address': ('is-update-status-hook', ),
                'cluster_connected': ('is-update-status-hook', ),
                'configure_dns_backend_rndc_keys': ('is-update-status-hook', ),
            },
            'when_any': {
                'set_dns_config_available': (
                    'dns-slaves-config-valid', 'dns-backend.available', ),
                'configure_nrpe': (
                    'config.changed.nagios_context',
                    'config.changed.nagios_servicegroups',
                    'config.changed.nameservers',
                    'endpoint.nrpe-external-master.changed',
                    'nrpe-external-master.available',
                ),
            },
            'when_none': {
                'clear_dns_config_available': (
                    'dns-slaves-config-valid', 'dns-backend.available', ),
                'start_designate_services': (
                    'charm.paused', ),
            },
            'when_file_changed': {
                'local_pools_updated': ('/etc/designate/pools.yaml', ),
            },
            'hook': {
                'check_dns_slaves': ('config-changed', ),
            },
        }
        # test that the hooks were registered via the
        # reactive.barbican_handlers
        self.registered_hooks_test_helper(handlers, hook_set, [])


class TestHandlers(test_utils.PatchHelper):

    def _patch_provide_charm_instance(self):
        the_charm = mock.MagicMock()
        self.patch_object(handlers.charm, 'provide_charm_instance',
                          name='provide_charm_instance',
                          new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = the_charm
        self.provide_charm_instance().__exit__.return_value = None
        return the_charm

    def test_install_packages(self):
        the_charm = self._patch_provide_charm_instance()
        self.patch_object(handlers.reactive, 'set_state')
        self.patch_object(handlers.reactive, 'remove_state')
        handlers.install_packages()
        the_charm.install.assert_called_once_with()
        calls = [mock.call('shared-db.setup'),
                 mock.call('base-config.rendered'),
                 mock.call('db.synched')]
        self.remove_state.assert_has_calls(calls)

    def test_setup_amqp_req(self):
        self.patch_object(handlers.reactive, 'set_state')
        amqp = mock.MagicMock()
        handlers.setup_amqp_req(amqp)
        amqp.request_access.assert_called_once_with(
            username='designate', vhost='openstack')

    def test_database(self):
        database = mock.MagicMock()
        handlers.setup_database(database)
        calls = [
            mock.call(
                'designate',
                'designate',
                prefix='designate'),
            mock.call(
                'dpm',
                'dpm',
                prefix='dpm'),
        ]
        database.configure.has_calls(calls)

    def test_setup_endpoint(self):
        the_charm = self._patch_provide_charm_instance()
        the_charm.service_type = 's1'
        the_charm.region = 'r1'
        the_charm.public_url = 'p1'
        the_charm.internal_url = 'i1'
        the_charm.admin_url = 'a1'
        args = ['s1', 'r1', 'p1', 'i1', 'a1']
        self.patch_object(handlers, 'is_data_changed',
                          name='is_data_changed',
                          new=mock.MagicMock())
        self.is_data_changed().__enter__.return_value = True
        self.is_data_changed().__exit__.return_value = None
        keystone = mock.MagicMock()
        handlers.maybe_setup_endpoint(keystone)
        keystone.register_endpoints.assert_called_once_with(*args)
        endpoint = mock.MagicMock()
        handlers.expose_endpoint(endpoint)
        endpoint.expose_endpoint.assert_called_once_with('i1')
        endpoint = mock.MagicMock()
        self.patch_object(handlers.hookenv, 'config', return_value=False)
        handlers.expose_endpoint(endpoint)
        endpoint.expose_endpoint.assert_called_once_with('p1')

    def test_configure_designate_basic(self):
        the_charm = self._patch_provide_charm_instance()
        self.patch_object(handlers.reactive, 'set_state')
        self.patch_object(handlers.reactive.RelationBase, 'from_state',
                          return_value=None)
        handlers.configure_designate_basic('arg1', 'arg2')
        the_charm.render_base_config.assert_called_once_with(
            ('arg1', 'arg2', ))
        self.set_state.assert_called_once_with('base-config.rendered')

    def test_run_db_migration(self):
        the_charm = self._patch_provide_charm_instance()
        self.patch_object(handlers.reactive, 'set_state')
        the_charm.db_sync_done.return_value = False
        handlers.run_db_migration('arg1', 'arg2')
        the_charm.db_sync.assert_called_once_with()
        self.assertFalse(self.set_state.called)
        the_charm.db_sync.reset_mock()
        the_charm.db_sync_done.return_value = True
        handlers.run_db_migration('arg1', 'arg2')
        the_charm.db_sync.assert_called_once_with()
        self.set_state.assert_called_once_with('db.synched')

    def test_sync_pool_manager_cache(self):
        the_charm = self._patch_provide_charm_instance()
        self.patch_object(handlers.reactive, 'set_state')
        the_charm.pool_manager_cache_sync_done.return_value = False
        handlers.sync_pool_manager_cache('arg1', 'arg2')
        the_charm.pool_manager_cache_sync.assert_called_once_with()
        self.assertFalse(self.set_state.called)
        the_charm.pool_manager_cache_sync.reset_mock()
        the_charm.pool_manager_cache_sync_done.return_value = True
        handlers.sync_pool_manager_cache('arg1', 'arg2')
        the_charm.pool_manager_cache_sync.assert_called_once_with()
        self.set_state.assert_called_once_with('pool-manager-cache.synched')

    def test_configure_designate_full(self):
        the_charm = self._patch_provide_charm_instance()
        self.patch_object(handlers.reactive.RelationBase,
                          'from_state',
                          return_value=None)
        handlers.configure_designate_full('arg1', 'arg2')
        the_charm.configure_ssl.assert_called_once_with()
        the_charm.render_full_config.assert_called_once_with(
            ('arg1', 'arg2', ))
        the_charm.create_initial_servers_and_domains.assert_called_once_with()
        the_charm.render_with_interfaces.assert_called_once_with(
            ('arg1', 'arg2'), configs=mock.ANY)
        the_charm.render_rndc_keys.assert_called_once_with()
        the_charm.update_pools.assert_called_once_with()
        the_charm.upgrade_if_available.assert_called_once_with(
            ('arg1', 'arg2', ))

    def test_cluster_connected(self):
        the_charm = self._patch_provide_charm_instance()
        hacluster = mock.MagicMock()
        handlers.cluster_connected(hacluster)
        the_charm.configure_ha_resources.assert_called_once_with(hacluster)
