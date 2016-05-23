import charmhelpers.core.hookenv as hookenv
import charms.reactive as reactive
import charm.openstack.designate as designate


@reactive.when_not('installed')
def install_packages():
    charm = designate.DesignateCharmFactory.charm()
    charm.configure_source()
    charm.install()
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
    charm = designate.DesignateCharmFactory.charm()
    keystone.register_endpoints(charm.service_type,
                                charm.region,
                                charm.public_url,
                                charm.internal_url,
                                charm.admin_url)


@reactive.when('dns-backend.available')
@reactive.when('shared-db.available')
@reactive.when('identity-service.available')
@reactive.when('amqp.available')
def configure_designate(amqp_interface, identity_interface, db_interface,
                        dns_interface):
    charm = designate.DesignateCharmFactory.charm(
        interfaces=[amqp_interface, identity_interface, db_interface,
                    dns_interface]
    )
    charm.render_base_config()
    charm.db_sync()
    charm.create_initial_servers_and_domains()
    charm.render_full_config()


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    charm = designate.DesignateCharmFactory.charm()
    charm.configure_ha_resources(hacluster)
