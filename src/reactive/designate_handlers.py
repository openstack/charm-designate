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
    '''Install charms packages'''
    designate.install()
    reactive.set_state('installed')


@reactive.when('amqp.connected')
def setup_amqp_req(amqp):
    '''Send request fir rabbit access and vhost'''
    amqp.request_access(username='designate',
                        vhost='openstack')
    designate.assess_status()


@reactive.when('shared-db.connected')
def setup_database(database):
    '''Send request designate accounts and dbs'''
    database.configure('designate', 'designate',
                       hookenv.unit_private_ip(), prefix='designate')
    database.configure('dpm', 'dpm',
                       hookenv.unit_private_ip(), prefix='dpm')
    designate.assess_status()


@reactive.when('identity-service.connected')
def setup_endpoint(keystone):
    '''Register endpoints with keystone'''
    designate.register_endpoints(keystone)
    designate.assess_status()


@reactive.when_not('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def configure_designate(*args):
    '''Configure the minimum to boostrap designate'''
    designate.render_base_config(args)
    reactive.set_state('base-config.rendered')


@reactive.when('identity-service.available')
def configure_ssl(keystone):
    '''Configure SSL access to designate if requested'''
    designate.configure_ssl(keystone)


@reactive.when_not('db.synched')
@reactive.when('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def run_db_migration(*args):
    '''Run database migrations'''
    designate.db_sync()
    if designate.db_sync_done():
        reactive.set_state('db.synched')


@reactive.when_not('domains.created')
@reactive.when('db.synched')
@reactive.when('base-config.rendered')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def create_servers_and_domains(*args):
    '''Create designate servers and domains within designate'''
    designate.create_initial_servers_and_domains()
    if designate.domain_init_done():
        reactive.set_state('domains.created')


@reactive.when('cluster.available')
def update_peers(cluster):
    '''Inform designate peers about this unit'''
    designate.update_peers(cluster)


@reactive.when('cluster.available')
@reactive.when('domains.created')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def render_all_configs(*args):
    '''Write out all designate config include bootstrap domain info'''
    designate.render_full_config(args)
    designate.update_pools()


@reactive.when_not('cluster.available')
@reactive.when('domains.created')
@reactive.when(*COMPLETE_INTERFACE_STATES)
def render_all_configs_single_node(*args):
    '''Write out all designate config include bootstrap domain info'''
    designate.render_full_config(args)
    designate.render_rndc_keys()
    designate.update_pools()


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    '''Configure HA resources in corosync'''
    designate.configure_ha_resources(hacluster)
    designate.assess_status()


@reactive.when('config.changed')
def config_changed():
    '''When the configuration changes, assess the unit's status to update any
    juju state required'''
    designate.assess_status()
