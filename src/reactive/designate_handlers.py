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
import charmhelpers.core.hookenv as hookenv

from charms_openstack.charm import provide_charm_instance
from charms_openstack.charm.utils import is_data_changed


# If either dns-backend.available is set OR config('dns-slaves') is valid, then
# the following state will be set.
DNS_CONFIG_AVAILABLE = 'dns-config.available'

COMPLETE_INTERFACE_STATES = [
    DNS_CONFIG_AVAILABLE,
    'shared-db.available',
    'identity-service.available',
    'amqp.available',
]


@reactive.hook('config-changed')
def check_dns_slaves():
    """verify if the config('dns-slaves') is valid and set or remove the state
    accordingly.  Note, that hooks run BEFORE the reactive handlers so this
    should happen first during a hook.
    """
    if hookenv.config('dns-slaves'):
        with provide_charm_instance() as instance:
            if not instance.options.invalid_pool_config():
                reactive.set_state('dns-slaves-config-valid')
                return
    reactive.remove_state('dns-slaves-config-valid')


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
    with provide_charm_instance() as instance:
        instance.install()
    reactive.set_state('installed')
    reactive.remove_state('amqp.requested-access')
    reactive.remove_state('shared-db.setup')
    reactive.remove_state('base-config.rendered')
    reactive.remove_state('db.synched')


@reactive.when('amqp.connected')
@reactive.when_not('amqp.requested-access')
def setup_amqp_req(amqp):
    """Send request for rabbit access and vhost"""
    amqp.request_access(username='designate',
                        vhost='openstack')
    reactive.set_state('amqp.requested-access')


@reactive.when('shared-db.connected')
@reactive.when_not('shared-db.setup')
def setup_database(database):
    """Send request designate accounts and dbs"""
    database.configure('designate', 'designate',
                       prefix='designate')
    database.configure('dpm', 'dpm',
                       prefix='dpm')
    reactive.set_state('shared-db.setup')


@reactive.when('identity-service.connected')
def maybe_setup_endpoint(keystone):
    """When the keystone interface connects, register this unit in the keystone
    catalogue.
    """
    with provide_charm_instance() as instance:
        args = [instance.service_type, instance.region, instance.public_url,
                instance.internal_url, instance.admin_url]
        # This function checkes that the data has changed before sending it
        with is_data_changed('charms.openstack.register-endpoints', args) as c:
            if c:
                keystone.register_endpoints(*args)


@reactive.when_not('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_designate_basic(*args):
    """Configure the minimum to boostrap designate"""
    # If cluster relation is available it needs to passed in
    cluster = reactive.RelationBase.from_state('cluster.available')
    if cluster is not None:
        args = args + (cluster, )
    dns_backend = reactive.RelationBase.from_state('dns-backend.available')
    if dns_backend is not None:
        args = args + (dns_backend, )
    with provide_charm_instance() as instance:
        instance.render_base_config(args)
    reactive.set_state('base-config.rendered')


@reactive.when_not('db.synched')
@reactive.when('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def run_db_migration(*args):
    """Run database migrations"""
    with provide_charm_instance() as instance:
        instance.db_sync()
        if instance.db_sync_done():
            reactive.set_state('db.synched')


@reactive.when('cluster.available')
def update_peers(cluster):
    """Inform designate peers about this unit"""
    with provide_charm_instance() as instance:
        # This function ONLY updates the peers if the data has changed.  Thus
        # it's okay to call it on every hook invocation.
        instance.update_peers(cluster)


@reactive.when('db.synched')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_designate_full(*args):
    """Write out all designate config include bootstrap domain info"""
    # If cluster relation is available it needs to passed in
    cluster = reactive.RelationBase.from_state('cluster.available')
    if cluster is not None:
        args = args + (cluster, )
    dns_backend = reactive.RelationBase.from_state('dns-backend.available')
    if dns_backend is not None:
        args = args + (dns_backend, )
    with provide_charm_instance() as instance:
        instance.upgrade_if_available(args)
        instance.configure_ssl()
        instance.render_full_config(args)
        try:
            # the following function should only run once for the leader.
            instance.create_initial_servers_and_domains()
            _render_sink_configs(instance, args)
            instance.render_rndc_keys()
            instance.update_pools()
        except subprocess.CalledProcessError as e:
            hookenv.log("ensure_api_responding() errored out: {}"
                        .format(str(e)),
                        level=hookenv.ERROR)


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


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    with provide_charm_instance() as instance:
        instance.configure_ha_resources(hacluster)


@reactive.when_not('dont-set-assess-status')
def run_assess_status_on_every_hook():
    """The call to charm instance.assess_status() sets up the assess status
    functionality to be called atexit() of the charm.  i.e. as the last thing
    it does.  Thus, this handle gets called for EVERY hook invocation, which
    means that no other handlers need to call the assess_status function.
    """
    with provide_charm_instance() as instance:
        instance.assess_status()
