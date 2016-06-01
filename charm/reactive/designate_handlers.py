import charmhelpers.core.hookenv as hookenv
import charms.reactive as reactive
import charm.openstack.designate as designate


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
@reactive.when('dns-backend.available')
@reactive.when('shared-db.available')
@reactive.when('identity-service.available')
@reactive.when('amqp.available')
def configure_designate(*args):
    designate.render_base_config(args)
    reactive.set_state('base-config.rendered')

@reactive.when_not('db.synched')
@reactive.when('base-config.rendered')
@reactive.when('dns-backend.available')
@reactive.when('shared-db.available')
@reactive.when('identity-service.available')
@reactive.when('amqp.available')
def run_db_migration(*args):
#    designate.db_sync()
#    designate.restart_all()
    reactive.set_state('db.synched')

@reactive.when_not('domains.created')
@reactive.when('base-config.rendered')
@reactive.when('dns-backend.available')
@reactive.when('shared-db.available')
@reactive.when('identity-service.available')
@reactive.when('amqp.available')
def create_servers_and_domains(*args):
    designate.create_initial_servers_and_domains()
    reactive.set_state('domains.created')

@reactive.when('domains.created')
@reactive.when('dns-backend.available')
@reactive.when('shared-db.available')
@reactive.when('identity-service.available')
@reactive.when('amqp.available')
@reactive.when('openstack-ha.available')
def render_all_configs(*args):
    print("Render with ha")
    designate.render_full_config(args)

@reactive.when('openstack-ha.available')
def bob(*args):
    print("Testing ha")


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    designate.configure_ha_resources(hacluster)
