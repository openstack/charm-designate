from __future__ import absolute_import
from __future__ import print_function

import unittest

import mock

import reactive.designate_handlers as handlers


_when_args = {}
_when_not_args = {}


def mock_hook_factory(d):

    def mock_hook(*args, **kwargs):

        def inner(f):
            # remember what we were passed.  Note that we can't actually
            # determine the class we're attached to, as the decorator only gets
            # the function.
            try:
                d[f.__name__].append(dict(args=args, kwargs=kwargs))
            except KeyError:
                d[f.__name__] = [dict(args=args, kwargs=kwargs)]
            return f
        return inner
    return mock_hook


class TestDesignateHandlers(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._patched_when = mock.patch('charms.reactive.when',
                                       mock_hook_factory(_when_args))
        cls._patched_when_started = cls._patched_when.start()
        cls._patched_when_not = mock.patch('charms.reactive.when_not',
                                           mock_hook_factory(_when_not_args))
        cls._patched_when_not_started = cls._patched_when_not.start()
        # force requires to rerun the mock_hook decorator:
        # try except is Python2/Python3 compatibility as Python3 has moved
        # reload to importlib.
        try:
            reload(handlers)
        except NameError:
            import importlib
            importlib.reload(handlers)

    @classmethod
    def tearDownClass(cls):
        cls._patched_when.stop()
        cls._patched_when_started = None
        cls._patched_when = None
        cls._patched_when_not.stop()
        cls._patched_when_not_started = None
        cls._patched_when_not = None
        # and fix any breakage we did to the module
        try:
            reload(handlers)
        except NameError:
            import importlib
            importlib.reload(handlers)

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

    def test_registered_hooks(self):
        # test that the hooks actually registered the relation expressions that
        # are meaningful for this interface: this is to handle regressions.
        # The keys are the function names that the hook attaches to.
        all_interfaces = (
            'dns-backend.available',
            'shared-db.available',
            'identity-service.available',
            'amqp.available')
        when_patterns = {
            'setup_amqp_req': [('amqp.connected', )],
            'setup_database': [('shared-db.connected', )],
            'setup_endpoint': [('identity-service.connected', )],
            'configure_ssl': [('identity-service.available', )],
            'update_peers': [('cluster.available', )],
            'config_changed': [('config.changed', )],
            'cluster_connected': [('ha.connected', )],
            'create_servers_and_domains': [
                all_interfaces,
                ('base-config.rendered', ),
                ('db.synched', ),
            ],
            'configure_designate_full': [
                all_interfaces,
                ('db.synched', ),
            ],
            'run_db_migration': [
                all_interfaces,
                ('base-config.rendered', ),
            ],
            'configure_designate_basic': [
                all_interfaces,
            ],
        }
        when_not_patterns = {
            'install_packages': [('installed', )],
            'run_db_migration': [('db.synched', )],
            'configure_designate_basic': [('base-config.rendered', )],
            'create_servers_and_domains': [('domains.created', )],
        }
        # check the when hooks are attached to the expected functions
        for t, p in [(_when_args, when_patterns),
                     (_when_not_args, when_not_patterns)]:
            for f, args in t.items():
                # check that function is in patterns
                print(f)
                self.assertTrue(f in p.keys())
                # check that the lists are equal
                l = [a['args'] for a in args]
                self.assertEqual(l, p[f])

    def test_install_packages(self):
        self.patch(handlers.designate, 'install')
        self.patch(handlers.reactive, 'set_state')
        handlers.install_packages()
        self.install.assert_called_once_with()
        self.set_state.assert_called_once_with('installed')

    def test_setup_amqp_req(self):
        self.patch(handlers.designate, 'assess_status')
        amqp = mock.MagicMock()
        handlers.setup_amqp_req(amqp)
        amqp.request_access.assert_called_once_with(
            username='designate', vhost='openstack')
        self.assess_status.assert_called_once_with()

    def test_database(self):
        self.patch(handlers.designate, 'assess_status')
        database = mock.MagicMock()
        self.patch(handlers.hookenv, 'unit_private_ip', 'private_ip')
        handlers.setup_database(database)
        calls = [
            mock.call(
                'designate',
                'designate',
                'private_ip',
                prefix='designate'),
            mock.call(
                'dpm',
                'dpm',
                'private_ip',
                prefix='dpm'),
        ]
        database.configure.has_calls(calls)
        self.assess_status.assert_called_once_with()

    def test_setup_endpoint(self):
        self.patch(handlers.designate, 'assess_status')
        self.patch(handlers.designate, 'register_endpoints')
        handlers.setup_endpoint('endpoint_object')
        self.register_endpoints.assert_called_once_with('endpoint_object')
        self.assess_status.assert_called_once_with()

    def test_configure_designate_basic(self):
        self.patch(handlers.reactive, 'set_state')
        self.patch(handlers.designate, 'render_base_config')
        self.patch(handlers.reactive.RelationBase, 'from_state')
        handlers.configure_designate_basic('arg1', 'arg2')
        self.render_base_config.assert_called_once_with(('arg1', 'arg2', ))
        self.set_state.assert_called_once_with('base-config.rendered')

    def test_run_db_migration(self):
        self.patch(handlers.reactive, 'set_state')
        self.patch(handlers.designate, 'db_sync')
        self.patch(handlers.designate, 'db_sync_done')
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
        self.patch(handlers.designate, 'update_peers')
        handlers.update_peers(cluster)
        self.update_peers.assert_called_once_with(cluster)

    def test_configure_designate_full(self):
        self.patch(handlers.reactive.RelationBase, 'from_state',
                   return_value=None)
        self.patch(handlers.designate, 'configure_ssl')
        self.patch(handlers.designate, 'render_full_config')
        self.patch(handlers.designate, 'create_initial_servers_and_domains')
        self.patch(handlers.designate, 'render_sink_configs')
        self.patch(handlers.designate, 'render_rndc_keys')
        self.patch(handlers.designate, 'update_pools')
        handlers.configure_designate_full('arg1', 'arg2')
        self.configure_ssl.assert_called_once_with()
        self.render_full_config.assert_called_once_with(('arg1', 'arg2', ))
        self.create_initial_servers_and_domains.assert_called_once_with()
        self.render_sink_configs.assert_called_once_with(('arg1', 'arg2', ))
        self.render_rndc_keys.assert_called_once_with()
        self.update_pools.assert_called_once_with()

    def test_cluster_connected(self):
        hacluster = mock.MagicMock()
        self.patch(handlers.designate, 'configure_ha_resources')
        self.patch(handlers.designate, 'assess_status')
        handlers.cluster_connected(hacluster)
        self.configure_ha_resources.assert_called_once_with(hacluster)
        self.assess_status.assert_called_once_with()

    def test_config_changed(self):
        self.patch(handlers.designate, 'assess_status')
        handlers.config_changed()
        self.assess_status.assert_called_once_with()
