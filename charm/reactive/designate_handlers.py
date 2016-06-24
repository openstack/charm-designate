import charmhelpers.core.hookenv as hookenv
import charms.reactive as reactive
import charm.openstack.designate as designate

COMPLETE_INTERFACE_STATES = [
    'dns-backend.available',
    'shared-db.available',
    'identity-service.available',
    'amqp.available',
]

@reactive.when_not('installed')
def install_packages():
    designate.install()
    reactive.set_state('installed')


@reactive.when('amqp.connected')
def setup_amqp_req(amqp):
    amqp.request_access(username='designate',
                        vhost='openstack')


@reactive.when('shared-db.connected')
def setup_database(database):
    database.configure('designate', 'designate',
                       hookenv.unit_private_ip(), prefix='designate')
    database.configure('dpm', 'dpm',
                       hookenv.unit_private_ip(), prefix='dpm')


@reactive.when('identity-service.connected')
def setup_endpoint(keystone):
    designate.register_endpoints(keystone) 


@reactive.when_not('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_designate(*args):
    designate.render_base_config(args)
    reactive.set_state('base-config.rendered')

@reactive.when('identity-service.available')
def configure_ssl(keystone):
    designate.configure_ssl(keystone)

@reactive.when_not('db.synched')
@reactive.when('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def run_db_migration(*args):
    designate.db_sync()
    if designate.db_sync_done():
        reactive.set_state('db.synched')

@reactive.when_not('domains.created')
@reactive.when('db.synched')
@reactive.when('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def create_servers_and_domains(*args):
    designate.create_initial_servers_and_domains()
    if designate.domain_init_done():
        reactive.set_state('domains.created')

@reactive.when('cluster.available')
def update_peers(cluster):
    designate.update_peers(cluster)

@reactive.when('cluster.available')
@reactive.when('domains.created')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def render_all_configs(*args):
    designate.render_full_config(args)

@reactive.when_not('cluster.available')
@reactive.when('domains.created')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def render_all_configs_single_node(*args):
    designate.render_full_config(args)

@reactive.when('ha.connected')
def cluster_connected(hacluster):
    designate.configure_ha_resources(hacluster)
