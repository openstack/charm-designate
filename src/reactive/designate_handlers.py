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

import subprocess

import charm.openstack.designate as designate
import charms.reactive as reactive
import charms.reactive.relations as relations
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host
import charmhelpers.contrib.network.ip as ip

import charms_openstack.charm as charm
from charms_openstack.charm.utils import is_data_changed


charm.use_defaults(
    'certificates.available',
    'cluster.available',
)

# If either dns-backend.available is set OR config('dns-slaves') is valid, then
# the following state will be set.
DNS_CONFIG_AVAILABLE = 'dns-config.available'

COMPLETE_INTERFACE_STATES = [
    DNS_CONFIG_AVAILABLE,
    'shared-db.available',
    'identity-service.available',
    'amqp.available',
    'coordinator-memcached.available',
]


@reactive.hook('config-changed')
def check_dns_slaves():
    """verify if the config('dns-slaves') is valid and set or remove the state
    accordingly.  Note, that hooks run BEFORE the reactive handlers so this
    should happen first during a hook.
    """
    with charm.provide_charm_instance() as instance:
        # ensure policy.d overrides are picked up
        instance.config_changed()
        if hookenv.config('dns-slaves'):
            if not instance.options.invalid_pool_config():
                reactive.set_state('dns-slaves-config-valid')
                return
    reactive.remove_state('dns-slaves-config-valid')


@reactive.when_not('is-update-status-hook')
@reactive.when_any('dns-slaves-config-valid',
                   'dns-backend.available')
def set_dns_config_available(*args):
    reactive.set_state(DNS_CONFIG_AVAILABLE)


@reactive.when_none('dns-slaves-config-valid',
                    'dns-backend.available')
def clear_dns_config_available():
    reactive.remove_state(DNS_CONFIG_AVAILABLE)


@reactive.when_not('installed')
def install_packages():
    """Install charms packages"""
    with charm.provide_charm_instance() as instance:
        instance.install()
    reactive.set_state('installed')
    reactive.remove_state('shared-db.setup')
    reactive.remove_state('base-config.rendered')
    reactive.remove_state('db.synched')
    reactive.remove_state('pool-manager-cache.synched')


@reactive.when_not('is-update-status-hook')
@reactive.when('amqp.connected')
def setup_amqp_req(amqp):
    """Send request for rabbit access and vhost"""
    amqp.request_access(username='designate',
                        vhost='openstack')


@reactive.when('base-config.rendered')
@reactive.when_not('config.rendered')
def config_rendered():
    """Set the config.rendered state when ready for operation.

    The config.rendered flag is used by the default handlers in
    charms.openstack to enable/disable services based on the
    readiness of the deployment. This functionality ensure
    that the Designate services start up only after the
    database has been synced.
    LP#1925233
    """
    reactive.set_state('config.rendered')


@reactive.when_not('is-update-status-hook')
@reactive.when_none('charm.paused')
@reactive.when('config.rendered', 'base-config.rendered')
def start_designate_services():
    """Enable services when database is synchronized"""
    with charm.provide_charm_instance() as instance:
        if instance.db_sync_done():
            instance.enable_services()
        else:
            hookenv.log("Services not enabled, waiting for db sync",
                        level=hookenv.WARNING)


@reactive.when('shared-db.connected')
@reactive.when_not('shared-db.setup')
def setup_database(database):
    """Send request designate accounts and dbs"""
    hostname = None
    if database.access_network():
        hostname = ip.get_address_in_network(database.access_network())
    database.configure('designate', 'designate', prefix='designate',
                       hostname=hostname)
    database.configure('dpm', 'dpm', prefix='dpm',
                       hostname=hostname)
    if database.base_data_complete():
        reactive.set_state('shared-db.setup')


@reactive.when_not('is-update-status-hook')
@reactive.when('identity-service.connected')
def maybe_setup_endpoint(keystone):
    """When the keystone interface connects, register this unit in the keystone
    catalogue.
    """
    with charm.provide_charm_instance() as instance:
        args = [instance.service_type, instance.region, instance.public_url,
                instance.internal_url, instance.admin_url]
        # This function checkes that the data has changed before sending it
        with is_data_changed('charms.openstack.register-endpoints', args) as c:
            if c:
                keystone.register_endpoints(*args)


@reactive.when_not('is-update-status-hook')
@reactive.when('cluster.connected')
def expose_rndc_address(cluster):
    rndc_address = ip.get_relation_ip('dns-backend')
    cluster.set_address('rndc', rndc_address)


@reactive.when_not('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_designate_basic(*args):
    """Configure the minimum to bootstrap designate"""
    # If cluster relation is available it needs to passed in
    cluster = relations.endpoint_from_flag('cluster.available')
    if cluster is not None:
        args = args + (cluster, )
    dns_backend = relations.endpoint_from_flag('dns-backend.available')
    if dns_backend is not None:
        args = args + (dns_backend, )
    with charm.provide_charm_instance() as instance:
        instance.render_base_config(args)
        instance.disable_services()
    reactive.set_state('base-config.rendered')


@reactive.when_not('db.synched')
@reactive.when('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def run_db_migration(*args):
    """Run database migrations"""
    with charm.provide_charm_instance() as instance:
        instance.db_sync()
        if instance.db_sync_done():
            reactive.set_state('db.synched')


@reactive.when_not('pool-manager-cache.synched')
@reactive.when('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def sync_pool_manager_cache(*args):
    with charm.provide_charm_instance() as instance:
        instance.pool_manager_cache_sync()
        if instance.pool_manager_cache_sync_done():
            reactive.set_state('pool-manager-cache.synched')


@reactive.when_not('is-update-status-hook')
@reactive.when('db.synched')
@reactive.when('pool-manager-cache.synched')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_designate_full(*args):
    """Write out all designate config include bootstrap domain info"""
    # If cluster relation is available it needs to passed in
    cluster = relations.endpoint_from_flag('cluster.available')
    if cluster is not None:
        args = args + (cluster, )
    dns_backend = relations.endpoint_from_flag('dns-backend.available')
    if dns_backend is not None:
        args = args + (dns_backend, )
    with charm.provide_charm_instance() as instance:
        instance.upgrade_if_available(args)
        instance.configure_ssl()
        instance.render_full_config(args)
        try:
            # the following function should only run once for the leader.
            if instance.configure_sink():
                instance.create_initial_servers_and_domains()
                _render_sink_configs(instance, args)
            instance.render_rndc_keys()
            instance.update_pools()
        except subprocess.CalledProcessError as e:
            hookenv.log("ensure_api_responding() errored out: {}"
                        .format(str(e)),
                        level=hookenv.ERROR)


@reactive.when_not('is-update-status-hook')
@reactive.when('dns-backend.available')
@reactive.when('db.synched')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_dns_backend_rndc_keys(*args):
    """Write the dns-backend relation configuration files and restart
    designate-worker to apply the new config.
    """
    with charm.provide_charm_instance() as instance:
        instance.render_relation_rndc_keys()
    host.service_restart('designate-worker')


def _render_sink_configs(instance, interfaces_list):
    """Helper: use the singleton from the DesignateCharm to render sink configs

    @param instance: an instance that has the render_with_intefaces() method
    @param interfaces_list: List of instances of interface classes.
    @returns: None
    """
    configs = [designate.NOVA_SINK_FILE,
               designate.NEUTRON_SINK_FILE,
               designate.DESIGNATE_DEFAULT]
    instance.render_with_interfaces(interfaces_list, configs=configs)


@reactive.when_not('is-update-status-hook')
@reactive.when('ha.connected')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    with charm.provide_charm_instance() as instance:
        instance.configure_ha_resources(hacluster)


@reactive.when_not('is-update-status-hook')
@reactive.when('dnsaas.connected')
def expose_endpoint(endpoint):
    with charm.provide_charm_instance() as instance:
        if hookenv.config('use-internal-endpoints'):
            endpoint.expose_endpoint(instance.internal_url)
        else:
            endpoint.expose_endpoint(instance.public_url)


@reactive.when_not('dont-set-assess-status')
def run_assess_status_on_every_hook():
    """The call to charm instance.assess_status() sets up the assess status
    functionality to be called atexit() of the charm.  i.e. as the last thing
    it does.  Thus, this handle gets called for EVERY hook invocation, which
    means that no other handlers need to call the assess_status function.
    """
    with charm.provide_charm_instance() as instance:
        instance.assess_status()


@reactive.when('leadership.changed.pool-yaml-hash')
def remote_pools_updated():
    hookenv.log(
        "Pools updated on remote host, restarting pool manager",
        level=hookenv.DEBUG)
    host.service_restart('designate-pool-manager')


@reactive.when_file_changed(designate.POOLS_YAML)
def local_pools_updated():
    hookenv.log(
        "Pools updated locally, restarting pool manager",
        level=hookenv.DEBUG)
    host.service_restart('designate-pool-manager')


@reactive.when('shared-db.setup')
@reactive.when_not('shared-db.connected')
def reset_shared_db():
    """Clear flags on shared-db departed.

    When shared-db is rejoined the charm will reconfigure the DB IFF these
    flags have been cleared. See LP Bug#1887265
    """
    reactive.remove_state('shared-db.setup')
    reactive.remove_state('db.synched')


@reactive.when_not('is-update-status-hook')
@reactive.when('base-config.rendered')
@reactive.when_any('config.changed.nagios_context',
                   'config.changed.nagios_servicegroups',
                   'config.changed.nameservers',
                   'endpoint.nrpe-external-master.changed',
                   'nrpe-external-master.available')
def configure_nrpe():
    """Handle config-changed for NRPE options."""
    with charm.provide_charm_instance() as charm_instance:
        charm_instance.render_nrpe()
        # regenerate service checks for upstream nameservers
        charm_instance.remove_nrpe_nameserver_checks()
        charm_instance.add_nrpe_nameserver_checks()
