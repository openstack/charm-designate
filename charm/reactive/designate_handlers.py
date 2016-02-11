from charmhelpers.core.hookenv import config, unit_private_ip
from charms.reactive import (
    hook,
    when,
)
from designate import DesignateCharmFactory


@hook('install')
def install_packages():
    charm = DesignateCharmFactory.charm()
    charm.configure_source()
    charm.install()


@when('amqp.connected')
def setup_amqp_req(amqp):
    amqp.request_access(username=config('rabbit-user'),
                        vhost=config('rabbit-vhost'))


@when('shared-db.connected')
def setup_database(database):
    database.configure(config('database'), config('database-user'),
                       unit_private_ip(), prefix='designate')
    database.configure('dpm', 'dpm',
                       unit_private_ip(), prefix='dpm')


@when('identity-service.connected')
def setup_endpoint(keystone):
    charm = DesignateCharmFactory.charm()
    keystone.register_endpoints(charm.service_type,
                                charm.region,
                                charm.public_url,
                                charm.internal_url,
                                charm.admin_url)


@when('dns-backend.available')
@when('shared-db.available')
@when('identity-service.available')
@when('amqp.available')
def render_stuff(amqp_interface, identity_interface, db_interface,
                 dns_interface):
    charm = DesignateCharmFactory.charm(
        interfaces=[amqp_interface, identity_interface, db_interface,
                    dns_interface]
    )
    charm.render_base_config()
    charm.db_sync()
    charm.create_domains()
    charm.render_full_config()
