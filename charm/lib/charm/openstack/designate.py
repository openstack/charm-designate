import os
import subprocess

import charm.openstack.adapters as openstack_adapters
import charm.openstack.charm as openstack_charm
import charm.openstack.ip as openstack_ip
import charmhelpers.core.hookenv as hookenv

DESIGNATE_DIR = '/etc/designate'
DESIGNATE_DEFAULT = '/etc/default/openstack'
DESIGNATE_CONF = DESIGNATE_DIR + '/designate.conf'
RNDC_KEY_CONF = DESIGNATE_DIR + '/rndc.key'
NOVA_SINK_FILE = DESIGNATE_DIR + '/conf.d/nova_sink.cfg'
NEUTRON_SINK_FILE = DESIGNATE_DIR + '/conf.d/neutron_sink.cfg'
RC_FILE = '/root/novarc'


def get_charm():
    """ Return a new instance of Designate or existing global instance
    @returns Designate
    """
    global designate_charm
    if designate_charm is None:
        designate_charm = DesignateCharmFactory.charm()
    return designate_charm


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
    }

    def __init__(self, relations):
        super(DesignateAdapters, self).__init__(
            relations,
            options=DesignateConfigurationAdapter,
            port_map=DesignateCharm.api_ports)


class DesignateCharm(openstack_charm.OpenStackCharm):
    """Designate charm"""

    base_packages = ['designate-agent', 'designate-api', 'designate-central',
                     'designate-common', 'designate-mdns',
                     'designate-pool-manager', 'designate-sink',
                     'designate-zone-manager', 'bind9utils']

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

    base_restart_map = {
        '/etc/default/openstack': services,
        '/etc/designate/designate.conf': services,
        '/etc/designate/rndc.key': services,
        '/etc/designate/conf.d/nova_sink.cfg': services,
        '/etc/designate/conf.d/neutron_sink.cfg': services,
    }
    service_type = 'designate'
    default_service = 'designate-api'
    sync_cmd = ['designate-manage', 'database', 'sync']
    adapters_class = DesignateAdapters

    ha_resources = ['vips', 'haproxy']

    def render_base_config(self):
        """Render initial config to bootstrap Designate service

        @returns None
        """
        self.render_configs([RC_FILE, DESIGNATE_CONF, RNDC_KEY_CONF,
                             DESIGNATE_DEFAULT])

    def render_full_config(self):
        """Render all config for Designate service

        @returns None
        """
        self.render_configs([RC_FILE, DESIGNATE_CONF, RNDC_KEY_CONF,
                             DESIGNATE_DEFAULT, NOVA_SINK_FILE,
                             NEUTRON_SINK_FILE, self.HAPROXY_CONF])

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

    @classmethod
    def create_initial_servers_and_domains(cls):
        """Create the nameserver entry and domains based on the charm user
        supplied config

        @returns None
        """
        cls.create_server(hookenv.config('dns-server-record'))
        cls.create_domain(
            hookenv.config('nova-domain'),
            hookenv.config('nova-domain-email'))
        cls.create_domain(hookenv.config('neutron-domain'),
                          hookenv.config('neutron-domain-email'))


class DesignateConfigurationAdapter(
      openstack_adapters.APIConfigurationAdapter):

    def __init__(self, port_map=None):
        super(DesignateConfigurationAdapter, self).__init__(port_map=port_map)

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


class DesignateCharmFactory(openstack_charm.OpenStackCharmFactory):

    releases = {
        'liberty': DesignateCharm
    }

    first_release = 'liberty'
