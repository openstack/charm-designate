import mock

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
            'amqp.available')
        hook_set = {
            'when': {
                'setup_amqp_req': ('amqp.connected', ),
                'setup_database': ('shared-db.connected', ),
                'setup_endpoint': ('identity-service.connected', ),
                'configure_ssl': ('identity-service.available', ),
                'update_peers': ('cluster.available', ),
                'config_changed': ('config.changed', ),
                'cluster_connected': ('ha.connected', ),
                'create_servers_and_domains': (
                    all_interfaces + ('base-config.rendered', 'db.synched')),
                'configure_designate_full': (
                    all_interfaces + ('db.synched', )),
                'run_db_migration': (
                    all_interfaces + ('base-config.rendered', )),
                'configure_designate_basic': all_interfaces,
            },
            'when_not': {
                'install_packages': ('installed', ),
                'run_db_migration': ('db.synched', ),
                'configure_designate_basic': ('base-config.rendered', ),
                'create_servers_and_domains': ('domains.created', ),
            },
            'when_any': {
                'set_dns_config_available': (
                    'dns-slaves-config-valid', 'dns-backend.available', ),
            },
            'when_none': {
                'clear_dns_config_available': (
                    'dns-slaves-config-valid', 'dns-backend.available', ),
            },
            'hook': {
                'check_dns_slaves': ('config-changed', ),
            },
        }
        # test that the hooks were registered via the
        # reactive.barbican_handlers
        self.registered_hooks_test_helper(handlers, hook_set, [])


class TestHandlers(test_utils.PatchHelper):

    def test_install_packages(self):
        self.patch_object(handlers.designate, 'install')
        self.patch_object(handlers.reactive, 'set_state')
        handlers.install_packages()
        self.install.assert_called_once_with()
        self.set_state.assert_called_once_with('installed')

    def test_setup_amqp_req(self):
        self.patch_object(handlers.designate, 'assess_status')
        amqp = mock.MagicMock()
        handlers.setup_amqp_req(amqp)
        amqp.request_access.assert_called_once_with(
            username='designate', vhost='openstack')
        self.assess_status.assert_called_once_with()

    def test_database(self):
        self.patch_object(handlers.designate, 'assess_status')
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
        self.assess_status.assert_called_once_with()

    def test_setup_endpoint(self):
        self.patch_object(handlers.designate, 'assess_status')
        self.patch_object(handlers.designate, 'register_endpoints')
        handlers.setup_endpoint('endpoint_object')
        self.register_endpoints.assert_called_once_with('endpoint_object')
        self.assess_status.assert_called_once_with()

    def test_configure_designate_basic(self):
        self.patch_object(handlers.reactive, 'set_state')
        self.patch_object(handlers.designate, 'render_base_config')
        self.patch_object(handlers.reactive.RelationBase, 'from_state',
                          return_value=None)
        handlers.configure_designate_basic('arg1', 'arg2')
        self.render_base_config.assert_called_once_with(('arg1', 'arg2', ))
        self.set_state.assert_called_once_with('base-config.rendered')

    def test_run_db_migration(self):
        self.patch_object(handlers.reactive, 'set_state')
        self.patch_object(handlers.designate, 'db_sync')
        self.patch_object(handlers.designate, 'db_sync_done')
        self.db_sync_done.return_value = False
        handlers.run_db_migration('arg1', 'arg2')
        self.db_sync.assert_called_once_with()
        self.assertFalse(self.set_state.called)
        self.db_sync.reset_mock()
        self.db_sync_done.return_value = True
        handlers.run_db_migration('arg1', 'arg2')
        self.db_sync.assert_called_once_with()
        self.set_state.assert_called_once_with('db.synched')

    def test_update_peers(self):
        cluster = mock.MagicMock()
        self.patch_object(handlers.designate, 'update_peers')
        handlers.update_peers(cluster)
        self.update_peers.assert_called_once_with(cluster)

    def test_configure_designate_full(self):
        self.patch_object(handlers.reactive.RelationBase,
                          'from_state',
                          return_value=None)
        self.patch_object(handlers.designate, 'upgrade_if_available')
        self.patch_object(handlers.designate, 'configure_ssl')
        self.patch_object(handlers.designate, 'render_full_config')
        self.patch_object(handlers.designate,
                          'create_initial_servers_and_domains')
        self.patch_object(handlers.designate, 'render_sink_configs')
        self.patch_object(handlers.designate, 'render_rndc_keys')
        self.patch_object(handlers.designate, 'update_pools')
        handlers.configure_designate_full('arg1', 'arg2')
        self.configure_ssl.assert_called_once_with()
        self.render_full_config.assert_called_once_with(('arg1', 'arg2', ))
        self.create_initial_servers_and_domains.assert_called_once_with()
        self.render_sink_configs.assert_called_once_with(('arg1', 'arg2', ))
        self.render_rndc_keys.assert_called_once_with()
        self.update_pools.assert_called_once_with()
        self.upgrade_if_available.assert_called_once_with(('arg1', 'arg2', ))

    def test_cluster_connected(self):
        hacluster = mock.MagicMock()
        self.patch_object(handlers.designate, 'configure_ha_resources')
        self.patch_object(handlers.designate, 'assess_status')
        handlers.cluster_connected(hacluster)
        self.configure_ha_resources.assert_called_once_with(hacluster)
        self.assess_status.assert_called_once_with()

    def test_config_changed(self):
        self.patch_object(handlers.designate, 'assess_status')
        handlers.config_changed()
        self.assess_status.assert_called_once_with()
