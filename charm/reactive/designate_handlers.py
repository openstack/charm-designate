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


@reactive.when('dns-backend.available')
@reactive.when('shared-db.available')
@reactive.when('identity-service.available')
@reactive.when('amqp.available')
def configure_designate(amqp_interface, identity_interface, db_interface,
                        dns_interface):
    designate.render_base_config()
    designate.db_sync()
    designate.create_initial_servers_and_domains()
    designate.render_full_config()


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    designate.configure_ha_resources(hacluster)
