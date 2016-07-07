
import os
import subprocess

import charmhelpers.contrib.openstack.utils as ch_utils
import charms_openstack.adapters as openstack_adapters
import charms_openstack.charm as openstack_charm
import charms_openstack.ip as os_ip
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host

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


def configure_ssl(keystone=None):
    """Use the singleton from the DesignateCharm to run render_base_config
    """
    DesignateCharm.singleton.configure_ssl(keystone)


def update_peers(cluster):
    DesignateCharm.singleton.update_peers(cluster)


def render_rndc_keys():
    DesignateCharm.singleton.render_rndc_keys()


def assess_status():
    """Just call the BarbicanCharm.singleton.assess_status() command to update
    status on the unit.
    """
    DesignateCharm.singleton.assess_status()


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


class BindRNDCRelationAdapter(openstack_adapters.OpenStackRelationAdapter):

    interface_type = "dns"

    def __init__(self, relation):
        super(BindRNDCRelationAdapter, self).__init__(relation)

    @property
    def slave_ips(self):
        return self.relation.slave_ips()

    @property
    def pool_config(self):
        pconfig = []
        for slave in self.slave_ips:
            unit_name = slave['unit'].replace('/', '_').replace('-', '_')
            pconfig.append({
                'nameserver': 'nameserver_{}'.format(unit_name),
                'pool_target': 'nameserver_{}'.format(unit_name),
                'address': slave['address'],
            })
        return pconfig

    @property
    def nameservers(self):
        return ', '.join([s['nameserver'] for s in self.pool_config])

    @property
    def pool_targets(self):
        return ', '.join([s['pool_target'] for s in self.pool_config])

    @property
    def slave_addresses(self):
        return ', '.join(['{}:53'.format(s['address'])
                         for s in self.pool_config])

    @property
    def rndc_info(self):
        return self.relation.rndc_info()


class DesignateConfigurationAdapter(
      openstack_adapters.APIConfigurationAdapter):

    def __init__(self, port_map=None):
        super(DesignateConfigurationAdapter, self).__init__(
            port_map=port_map,
            service_name='designate')

    @property
    def pool_config(self):
        pconfig = []
        for entry in self.dns_slaves.split():
            address, port, key = entry.split(':')
            unit_name = address.replace('.', '_')
            pconfig.append({
                'nameserver': 'nameserver_{}'.format(unit_name),
                'pool_target': 'nameserver_{}'.format(unit_name),
                'address': address,
                'rndc_key_file': '/etc/designate/rndc_{}.key'.format(
                    unit_name),
            })
        return pconfig

    @property
    def nameservers(self):
        return ', '.join([s['nameserver'] for s in self.pool_config])

    @property
    def pool_targets(self):
        return ', '.join([s['pool_target'] for s in self.pool_config])

    @property
    def slave_addresses(self):
        return ', '.join(['{}:53'.format(s['address'])
                         for s in self.pool_config])

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

    @property
    def rndc_master_ip(self):
        """Returns IP address slave DNS slave should use to query master
        """
        return os_ip.resolve_address(endpoint_type=os_ip.INTERNAL)


class DesignateAdapters(openstack_adapters.OpenStackAPIRelationAdapters):
    """
    Adapters class for the Designate charm.
    """
    relation_adapters = {
        'shared_db': DesignateDBAdapter,
        'cluster': openstack_adapters.PeerHARelationAdapter,
        'dns_backend': BindRNDCRelationAdapter,
    }

    def __init__(self, relations):
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
            os_ip.PUBLIC: 9001,
            os_ip.ADMIN: 9001,
            os_ip.INTERNAL: 9001,
        }
    }

    required_relations = ['shared-db', 'amqp', 'identity-service',
                          'dns-backend']

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
        if self.haproxy_enabled():
            configs.append(self.HAPROXY_CONF)
        DesignateCharm.singleton.render_with_interfaces(
            interfaces_list,
            configs=configs)

    def render_full_config(self, interfaces_list):
        """Render all config for Designate service

        @returns None
        """
        DesignateCharm.singleton.render_with_interfaces(interfaces_list)

    def write_key_file(self, unit_name, key):
        """Write rndc keyfile for given unit_name

        @param unit_name: str Name of unit using key
        @param key: str RNDC key
        @returns None
        """
        key_file = '/etc/designate/rndc_{}.key'.format(unit_name)
        template = ('key "rndc-key" {{\n    algorithm hmac-md5;\n    '
                    'secret "{}";\n}};')
        host.write_file(
            key_file,
            str.encode(template.format(key)),
            owner='root',
            group='designate',
            perms=0o440)

    def render_rndc_keys(self):
        """Render the rndc keys supplied via user config

        @returns None
        """
        for entry in hookenv.config('dns-slaves').split():
            address, port, key = entry.split(':')
            unit_name = address.replace('.', '_')
            self.write_key_file(unit_name, key)

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
