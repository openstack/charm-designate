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


import charm.openstack.designate as designate
import charmhelpers.core.hookenv as hookenv
import charms.reactive as reactive

COMPLETE_INTERFACE_STATES = [
    'dns-backend.available',
    'shared-db.available',
    'identity-service.available',
    'amqp.available',
]


@reactive.when_not('installed')
def install_packages():
    """Install charms packages"""
    designate.install()
    reactive.set_state('installed')


@reactive.when('amqp.connected')
def setup_amqp_req(amqp):
    """Send request fir rabbit access and vhost"""
    amqp.request_access(username='designate',
                        vhost='openstack')
    designate.assess_status()


@reactive.when('shared-db.connected')
def setup_database(database):
    """Send request designate accounts and dbs"""
    database.configure('designate', 'designate',
                       hookenv.unit_private_ip(), prefix='designate')
    database.configure('dpm', 'dpm',
                       hookenv.unit_private_ip(), prefix='dpm')
    designate.assess_status()


@reactive.when('identity-service.connected')
def setup_endpoint(keystone):
    """Register endpoints with keystone"""
    designate.register_endpoints(keystone)
    designate.assess_status()


@reactive.when_not('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_designate_basic(*args):
    """Configure the minimum to boostrap designate"""
    # If cluster relation is available it needs to passed in
    cluster = reactive.RelationBase.from_state('cluster.available')
    if cluster is not None:
        args = args + (cluster, )
    designate.render_base_config(args)
    reactive.set_state('base-config.rendered')


@reactive.when_not('db.synched')
@reactive.when('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def run_db_migration(*args):
    """Run database migrations"""
    designate.db_sync()
    if designate.db_sync_done():
        reactive.set_state('db.synched')


@reactive.when('cluster.available')
def update_peers(cluster):
    """Inform designate peers about this unit"""
    designate.update_peers(cluster)


@reactive.when('db.synched')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_designate_full(*args):
    """Write out all designate config include bootstrap domain info"""
    # If cluster relation is available it needs to passed in
    cluster = reactive.RelationBase.from_state('cluster.available')
    if cluster is not None:
        args = args + (cluster, )
    designate.upgrade_if_available(args)
    designate.configure_ssl()
    designate.render_full_config(args)
    designate.create_initial_servers_and_domains()
    designate.render_sink_configs(args)
    designate.render_rndc_keys()
    designate.update_pools()


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    designate.configure_ha_resources(hacluster)
    designate.assess_status()


@reactive.when('config.changed')
def config_changed():
    """When the configuration changes, assess the unit's status to update any
    juju state required"""
    designate.assess_status()
