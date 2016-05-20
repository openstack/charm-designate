from charm.openstack.adapters import (
    OpenStackRelationAdapters,
    APIConfigurationAdapter,
    DatabaseRelationAdapter,
)
import subprocess
import os
from charm.openstack.ip import PUBLIC, INTERNAL, ADMIN
from charmhelpers.core.hookenv import config
from charmhelpers.core.hookenv import unit_private_ip
from charm.openstack.charm import OpenStackCharmFactory, OpenStackCharm
from charmhelpers.contrib.hahelpers.cluster import determine_api_port

DESIGNATE_DIR = '/etc/designate'
DESIGNATE_DEFAULT = '/etc/default/openstack'
DESIGNATE_CONF = DESIGNATE_DIR + '/designate.conf'
RNDC_KEY_CONF = DESIGNATE_DIR + '/rndc.key'
NOVA_SINK_FILE = DESIGNATE_DIR + '/conf.d/nova_sink.cfg'
NEUTRON_SINK_FILE = DESIGNATE_DIR + '/conf.d/neutron_sink.cfg'
RC_FILE = '/root/novarc'


class DesignateDBAdapter(DatabaseRelationAdapter):

    def __init__(self, relation):
        super(DesignateDBAdapter, self).__init__(relation)

    @property
    def designate_uri(self):
        return self.get_uri(prefix='designate')

    @property
    def designate_pool_uri(self):
        return self.get_uri(prefix='dpm')


class DesignateAdapters(OpenStackRelationAdapters):
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


class DesignateCharm(OpenStackCharm):

    base_packages = ['designate-agent', 'designate-api', 'designate-central',
                     'designate-common', 'designate-mdns', 'designate-pool-manager',
                     'designate-sink', 'designate-zone-manager', 'bind9utils']

    services = ['designate-mdns', 'designate-zone-manager',
                'designate-agent', 'designate-pool-manager',
                'designate-central', 'designate-sink',
                'designate-api']

    api_ports = {
        'designate-api': {
            PUBLIC: 9001,
            ADMIN: 9001,
            INTERNAL: 9001,
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
        self.render_configs([RC_FILE, DESIGNATE_CONF, RNDC_KEY_CONF,
                             DESIGNATE_DEFAULT])

    def render_full_config(self):
        self.render_configs([NOVA_SINK_FILE, NEUTRON_SINK_FILE,
                             DESIGNATE_DEFAULT, self.HAPROXY_CONF])

    @classmethod
    def get_domain_id(cls, domain):
        get_cmd = ['reactive/designate_utils.py', 'domain-get', domain]
        output = subprocess.check_output(get_cmd)
        if output:
            return output.decode('utf8').strip()

    @classmethod
    def create_domain(cls, domain, email):
        create_cmd = ['reactive/designate_utils.py', 'domain-create', domain,
                      email]
        subprocess.check_call(create_cmd)

    @classmethod
    def create_server(cls, domain):
        create_cmd = ['reactive/designate_utils.py', 'server-create', domain]
        subprocess.check_call(create_cmd)

    @classmethod
    def create_domains(cls):
        cls.create_server(config('dns-server-record'))
        cls.create_domain(config('nova-domain'), config('nova-domain-email'))
        cls.create_domain(config('neutron-domain'),
                          config('neutron-domain-email'))


class DesignateConfigurationAdapter(APIConfigurationAdapter):

    def __init__(self, port_map=None):
        super(DesignateConfigurationAdapter, self).__init__(port_map=port_map)

    @property
    def nova_domain_id(self):
        domain = config('nova-domain')
        return DesignateCharm.get_domain_id(domain)

    @property
    def nova_conf_args(self):
        daemon_arg = ''
        if os.path.exists(NOVA_SINK_FILE):
            daemon_arg = '--config-file={}'.format(NOVA_SINK_FILE)
        return daemon_arg

    @property
    def neutron_domain_id(self):
        domain = config('neutron-domain')
        return DesignateCharm.get_domain_id(domain)

    @property
    def neutron_conf_args(self):
        daemon_arg = ''
        if os.path.exists(NEUTRON_SINK_FILE):
            daemon_arg = '--config-file={}'.format(NEUTRON_SINK_FILE)
        return daemon_arg


class DesignateCharmFactory(OpenStackCharmFactory):

    releases = {
        'liberty': DesignateCharm
    }

    first_release = 'liberty'
