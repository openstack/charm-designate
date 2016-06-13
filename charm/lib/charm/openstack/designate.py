import os
import subprocess

import charmhelpers.contrib.openstack.utils as ch_utils
import charms_openstack.adapters as openstack_adapters
import charms_openstack.charm as openstack_charm
import charms_openstack.ip as openstack_ip
import charmhelpers.core.hookenv as hookenv

DESIGNATE_DIR = '/etc/designate'
DESIGNATE_DEFAULT = '/etc/default/openstack'
DESIGNATE_CONF = DESIGNATE_DIR + '/designate.conf'
RNDC_KEY_CONF = DESIGNATE_DIR + '/rndc.key'
NOVA_SINK_FILE = DESIGNATE_DIR + '/conf.d/nova_sink.cfg'
NEUTRON_SINK_FILE = DESIGNATE_DIR + '/conf.d/neutron_sink.cfg'
RC_FILE = '/root/novarc'


def install():
    """Use the singleton from the DesignateCharm to install the packages on the
    unit
    """
    DesignateCharm.singleton.install()


def db_sync_done():
    """Use the singleton from the DesignateCharm to run db migration
    """
    return DesignateCharm.singleton.db_sync_done()

def db_sync():
    """Use the singleton from the DesignateCharm to run db migration
    """
    DesignateCharm.singleton.db_sync()


def render_base_config(interfaces_list):
    """Use the singleton from the DesignateCharm to run render_base_config
    """
    DesignateCharm.singleton.render_base_config(interfaces_list)


def create_initial_servers_and_domains():
    """Use the singleton from the DesignateCharm to run render_base_config
    """
    DesignateCharm.singleton.create_initial_servers_and_domains()

def domain_init_done():
    """Use the singleton from the DesignateCharm to run render_base_config
    """
    return DesignateCharm.singleton.domain_init_done()


def render_full_config(interfaces_list):
    """Use the singleton from the DesignateCharm to run render_base_config
    """
    DesignateCharm.singleton.render_full_config(interfaces_list)


                                                                                
def register_endpoints(keystone):
    """When the keystone interface connects, register this unit in the keystone
    catalogue.
    """
    charm = DesignateCharm.singleton
    keystone.register_endpoints(charm.service_type,
                                charm.region,
                                charm.public_url,
                                charm.internal_url,
                                charm.admin_url)

def configure_ha_resources(hacluster):
    """Use the singleton from the DesignateCharm to run render_base_config
    """
    DesignateCharm.singleton.configure_ha_resources(hacluster)

def restart_all():
    """Use the singleton from the DesignateCharm to run render_base_config
    """
    DesignateCharm.singleton.restart_all()

#def configure_ca(keystone=None):
#    """Use the singleton from the DesignateCharm to run render_base_config
#    """
#    DesignateCharm.singleton.configure_apache_ssl(keystone)

def configure_ssl(keystone=None):
    """Use the singleton from the DesignateCharm to run render_base_config
    """
    DesignateCharm.singleton.configure_ssl(keystone)


class DesignateDBAdapter(openstack_adapters.DatabaseRelationAdapter):
    """Get database URIs for the two designate databases"""

    def __init__(self, relation):
        super(DesignateDBAdapter, self).__init__(relation)

    @property
    def designate_uri(self):
        return self.get_uri(prefix='designate')

    @property
    def designate_pool_uri(self):
        return self.get_uri(prefix='dpm')


class DesignateAdapters(openstack_adapters.OpenStackRelationAdapters):
    """
    Adapters class for the Designate charm.
    """
    relation_adapters = {
        'shared_db': DesignateDBAdapter,
        'cluster': openstack_adapters.PeerHARelationAdapter,
    }

    def __init__(self, relations):
        print(relations)
        super(DesignateAdapters, self).__init__(
            relations,
            options_instance=DesignateConfigurationAdapter(
                port_map=DesignateCharm.api_ports))

class DesignateCharm(openstack_charm.HAOpenStackCharm):
    """Designate charm"""

    name = 'designate'
    packages = ['designate-agent', 'designate-api', 'designate-central',
                'designate-common', 'designate-mdns',
                'designate-pool-manager', 'designate-sink',
                'designate-zone-manager', 'bind9utils', 'python-apt']

    services = ['designate-mdns', 'designate-zone-manager',
                'designate-agent', 'designate-pool-manager',
                'designate-central', 'designate-sink',
                'designate-api']

    api_ports = {
        'designate-api': {
            openstack_ip.PUBLIC: 9001,
            openstack_ip.ADMIN: 9001,
            openstack_ip.INTERNAL: 9001,
        }
    }

    restart_map = {
        '/etc/default/openstack': services,
        '/etc/designate/designate.conf': services,
        '/etc/designate/rndc.key': services,
        '/etc/designate/conf.d/nova_sink.cfg': services,
        '/etc/designate/conf.d/neutron_sink.cfg': services,
        RC_FILE: [''],
    }
    service_type = 'designate'
    default_service = 'designate-api'
    sync_cmd = ['designate-manage', 'database', 'sync']
    adapters_class = DesignateAdapters

    ha_resources = ['vips', 'haproxy']
    release = 'liberty'

    def __init__(self, release=None, **kwargs):
        """Custom initialiser for class
        If no release is passed, then the charm determines the release from the
        ch_utils.os_release() function.
        """
        if release is None:
            release = ch_utils.os_release('python-keystonemiddleware')
        super(DesignateCharm, self).__init__(release=release, **kwargs)


    def install(self):
        """Customise the installation, configure the source and then call the
        parent install() method to install the packages
        """
        self.configure_source()
        super(DesignateCharm, self).install()


    def render_base_config(self, interfaces_list):
        """Render initial config to bootstrap Designate service

        @returns None
        """
        configs = [RC_FILE, DESIGNATE_CONF, RNDC_KEY_CONF, DESIGNATE_DEFAULT]
        DesignateCharm.singleton.render_with_interfaces(
            interfaces_list,
            configs=configs)

    def render_full_config(self, interfaces_list):
        """Render all config for Designate service

        @returns None
        """
        DesignateCharm.singleton.render_with_interfaces(interfaces_list)

    @classmethod
    def get_domain_id(cls, domain):
        """Return the domain ID for a given domain name

        @param domain: Domain name
        @returns domain_id
        """
        get_cmd = ['reactive/designate_utils.py', 'domain-get', domain]
        output = subprocess.check_output(get_cmd)
        if output:
            return output.decode('utf8').strip()

    @classmethod
    def create_domain(cls, domain, email):
        """Create a domain

        @param domain: The name of the domain you are creating. The name must
                       end with a full stop.
        @param email: An email address of the person responsible for the
                      domain.
        @returns None
        """
        create_cmd = ['reactive/designate_utils.py', 'domain-create', domain,
                      email]
        subprocess.check_call(create_cmd)

    @classmethod
    def create_server(cls, nsname):
        """ create a nameserver entry with the supplied name

        @param nsname: Name of NameserverS record
        @returns None
        """
        create_cmd = ['reactive/designate_utils.py', 'server-create', nsname]
        subprocess.check_call(create_cmd)

    def domain_init_done(self):
        return hookenv.leader_get(attribute='domain-init-done')

    @classmethod
    def create_initial_servers_and_domains(cls):
        """Create the nameserver entry and domains based on the charm user
        supplied config

        @returns None
        """
        if hookenv.is_leader():
            cls.create_server(hookenv.config('dns-server-record'))
            cls.create_domain(
                hookenv.config('nova-domain'),
                hookenv.config('nova-domain-email'))
            cls.create_domain(
                hookenv.config('neutron-domain'),
                hookenv.config('neutron-domain-email'))
            hookenv.leader_set({'domain-init-done': True})

class DesignateConfigurationAdapter(
      openstack_adapters.APIConfigurationAdapter):

    def __init__(self, port_map=None):
        super(DesignateConfigurationAdapter, self).__init__(
            port_map=port_map,
            service_name='designate')

    @property
    def nova_domain_id(self):
        """Returns the id of the domain corresponding to the user supplied
        'nova-domain'

        @returns nova domain id
        """
        domain = hookenv.config('nova-domain')
        return DesignateCharm.get_domain_id(domain)

    @property
    def neutron_domain_id(self):
        """Returns the id of the domain corresponding to the user supplied
        'neutron-domain'

        @returns neutron domain id
        """
        domain = hookenv.config('neutron-domain')
        return DesignateCharm.get_domain_id(domain)

    @property
    def nova_conf_args(self):
        """Returns config file directive to point daemons at nova config file.
        These directives are designed to be used in /etc/default/ files

        @returns startup config file option
        """
        daemon_arg = ''
        if os.path.exists(NOVA_SINK_FILE):
            daemon_arg = '--config-file={}'.format(NOVA_SINK_FILE)
        return daemon_arg

    @property
    def neutron_conf_args(self):
        """Returns config file directive to point daemons at neutron config
        file. These directives are designed to be used in /etc/default/ files

        @returns startup config file option
        """
        daemon_arg = ''
        if os.path.exists(NEUTRON_SINK_FILE):
            daemon_arg = '--config-file={}'.format(NEUTRON_SINK_FILE)
        return daemon_arg


#class DesignateCharmFactory(openstack_charm.OpenStackCharmFactory):
#
#    releases = {
#        'liberty': DesignateCharm
#    }
#
#    first_release = 'liberty'
