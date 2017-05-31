# Copyright 2016 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import collections
import contextlib
import os
import subprocess
import uuid

import charmhelpers.contrib.openstack.utils as ch_utils
import charms_openstack.adapters as openstack_adapters
import charms_openstack.charm as openstack_charm
import charms_openstack.ip as os_ip
import charmhelpers.core.decorators as decorators
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host
import charms.reactive as reactive

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

    @returns: None
    """
    DesignateCharm.singleton.install()


def db_sync_done():
    """Use the singleton from the DesignateCharm to check if db migration has
    been run

    @returns: str or None. Str if sync has been done otherwise None
    """
    return DesignateCharm.singleton.db_sync_done()


def db_sync():
    """Use the singleton from the DesignateCharm to run db migration

    @returns: None
    """
    DesignateCharm.singleton.db_sync()


def render_base_config(interfaces_list):
    """Use the singleton from the DesignateCharm to run render_base_config

    @param interfaces_list: List of instances of interface classes.
    @returns: None
    """
    DesignateCharm.singleton.render_base_config(interfaces_list)


def create_initial_servers_and_domains():
    """Use the singleton from the DesignateCharm to run create inital servers
    and domains in designate

    @returns: None
    """
    DesignateCharm.singleton.create_initial_servers_and_domains()


def domain_init_done():
    """Use the singleton from the DesignateCharm to check if inital servers
    and domains have been created

    @returns: str or None. Str if init has been done otherwise None
    """
    return DesignateCharm.singleton.domain_init_done()


def render_full_config(interfaces_list):
    """Use the singleton from the DesignateCharm to render all configs

    @param interfaces_list: List of instances of interface classes.
    @returns: None
    """
    DesignateCharm.singleton.render_full_config(interfaces_list)


def render_sink_configs(interfaces_list):
    """Use the singleton from the DesignateCharm to render sink configs

    @param interfaces_list: List of instances of interface classes.
    @returns: None
    """
    configs = [NOVA_SINK_FILE, NEUTRON_SINK_FILE, DESIGNATE_DEFAULT]
    DesignateCharm.singleton.render_with_interfaces(
        interfaces_list,
        configs=configs)


def register_endpoints(keystone):
    """When the keystone interface connects, register this unit in the keystone
    catalogue.

    @param keystone: KeystoneRequires() interface class
    @returns: None
    """
    charm = DesignateCharm.singleton
    keystone.register_endpoints(charm.service_type,
                                charm.region,
                                charm.public_url,
                                charm.internal_url,
                                charm.admin_url)


def configure_ha_resources(hacluster):
    """Use the singleton from the DesignateCharm to run configure ha resources

    @param hacluster: OpenstackHAPeers() interface class
    @returns: None
    """
    DesignateCharm.singleton.configure_ha_resources(hacluster)


def restart_all():
    """Use the singleton from the DesignateCharm to restart all registered
    services

    @returns: None
    """
    DesignateCharm.singleton.restart_all()


def configure_ssl(keystone=None):
    """Use the singleton from the DesignateCharm to configure ssl

    @param keystone: KeystoneRequires() interface class
    @returns: None
    """
    DesignateCharm.singleton.configure_ssl(keystone)


def update_peers(hacluster):
    """Use the singleton from the DesignateCharm to update peers with detials
    of this unit

    @param hacluster: OpenstackHAPeers() interface class
    @returns: None
    """
    DesignateCharm.singleton.update_peers(hacluster)


def render_rndc_keys():
    """Use the singleton from the DesignateCharm write out rndc key files

    @returns: None
    """
    DesignateCharm.singleton.render_rndc_keys()


def assess_status():
    """Just call the DesignateCharm.singleton.assess_status() command to update
    status on the unit.

    @returns: None
    """
    DesignateCharm.singleton.assess_status()


def update_pools():
    """Just call the DesignateCharm.singleton.update_pools() command to update
    pool info in the db

    @returns: None
    """
    DesignateCharm.singleton.update_pools()


def upgrade_if_available(interfaces_list):
    """Just call the DesignateCharm.singleton.upgrade_if_available() command to
    update OpenStack package if upgrade is available

    @returns: None
    """
    DesignateCharm.singleton.upgrade_if_available(interfaces_list)


class DesignateDBAdapter(openstack_adapters.DatabaseRelationAdapter):
    """Get database URIs for the two designate databases"""

    def __init__(self, relation):
        super(DesignateDBAdapter, self).__init__(relation)

    @property
    def designate_uri(self):
        """URI for designate DB"""
        return self.get_uri(prefix='designate')

    @property
    def designate_pool_uri(self):
        """URI for designate pool DB"""
        return self.get_uri(prefix='dpm')


class BindRNDCRelationAdapter(openstack_adapters.OpenStackRelationAdapter):

    interface_type = "dns"

    def __init__(self, relation):
        super(BindRNDCRelationAdapter, self).__init__(relation)

    @property
    def slave_ips(self):
        """List of DNS slave address infoprmation

        @returns: list [{'unit': unitname, 'address': 'address'},
                        ...]
        """
        return self.relation.slave_ips()

    @property
    def pool_config(self):
        """List of DNS slave information from Juju attached DNS slaves

        Creates a dict for each backends and returns a list of those dicts.
        The designate config file has a section per backend. The template uses
        the nameserver and pool_target names to create a section for each
        backend

        @returns: list [{'nameserver': name, 'pool_target': name,
                         'address': slave_ip_addr},
                        ...]
        """
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
    def pool_targets(self):
        """List of pool_target section names

        @returns: str Comma delimited list of pool_target section names
        """
        return ', '.join([s['pool_target'] for s in self.pool_config])

    @property
    def slave_addresses(self):
        """List of slave IP addresses

        @returns: str Comma delimited list of slave IP addresses
        """
        return ', '.join(['{}:53'.format(s['address'])
                         for s in self.pool_config])

    @property
    def rndc_info(self):
        """Rndc key and algorith in formation.

        @returns: dict {'algorithm': rndc_algorithm,
                        'secret': rndc_secret_digest}
        """
        return self.relation.rndc_info


class DesignateConfigurationAdapter(
        openstack_adapters.APIConfigurationAdapter):

    def __init__(self, port_map=None, *args, **kwargs):
        super(DesignateConfigurationAdapter, self).__init__(
            port_map=port_map, service_name='designate', *args, **kwargs)

    @property
    def pool_config(self):
        """List of DNS slave information from user defined config

        Creates a dict for each backends and returns a list of those dicts.
        The designate config file has a section per backend. The template uses
        the nameserver and pool_target names to create a section for each
        backend.

        @returns: list [{'nameserver': name,
                         'pool_target': name,
                         'address': slave_ip_addr,
                         'rndc_key_file': rndc_key_file},
                        ...]
        """
        pconfig = []
        if self.dns_slaves:
            for entry in self.dns_slaves.split():
                try:
                    address, port, key = entry.split(':')
                    unit_name = address.replace('.', '_')
                    pconfig.append({
                        'nameserver': 'nameserver_{}'.format(unit_name),
                        'pool_target': 'nameserver_{}'.format(unit_name),
                        'address': address,
                        'rndc_key_file': '/etc/designate/rndc_{}.key'.format(
                            unit_name),
                    })
                except ValueError:
                    # the entry doesn't until 3 values, so ignore it.
                    pass
        return pconfig

    def invalid_pool_config(self):
        """Validates that the pool config at least looks like something that
        can be used.

        @returns: Error string or None if okay
        """
        if self.dns_slaves:
            for entry in self.dns_slaves.split():
                try:
                    _, __, ___ = entry.split(':')
                except ValueError:
                    return "dns_slaves is malformed"
        return None

    @property
    def pool_targets(self):
        """List of pool_target section names

        @returns: str Comma delimited list of pool_target section names
        """
        return ', '.join([s['pool_target'] for s in self.pool_config])

    @property
    def slave_addresses(self):
        """List of slave IP addresses

        @returns: str Comma delimited list of slave IP addresses
        """
        return ', '.join(['{}:53'.format(s['address'])
                         for s in self.pool_config])

    @property
    def nova_domain_id(self):
        """Returns the id of the domain corresponding to the user supplied
        'nova-domain'

        @returns nova domain id
        """
        domain = hookenv.config('nova-domain')
        if domain:
            return DesignateCharm.get_domain_id(domain)
        return None

    @property
    def neutron_domain_id(self):
        """Returns the id of the domain corresponding to the user supplied
        'neutron-domain'

        @returns neutron domain id
        """
        domain = hookenv.config('neutron-domain')
        if domain:
            return DesignateCharm.get_domain_id(domain)
        return None

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

    required_relations = ['shared-db', 'amqp', 'identity-service', ]

    restart_map = {
        '/etc/default/openstack': services,
        '/etc/designate/designate.conf': services,
        '/etc/designate/rndc.key': services,
        '/etc/designate/conf.d/nova_sink.cfg': services,
        '/etc/designate/conf.d/neutron_sink.cfg': services,
        '/etc/designate/pools.yaml': [''],
        RC_FILE: [''],
    }
    service_type = 'designate'
    default_service = 'designate-api'
    sync_cmd = ['designate-manage', 'database', 'sync']
    adapters_class = DesignateAdapters
    configuration_class = DesignateConfigurationAdapter

    ha_resources = ['vips', 'haproxy']
    release = 'mitaka'
    release_pkg = 'designate-common'
    package_codenames = {
        'designate-common': collections.OrderedDict([
            ('2', 'mitaka'),
            ('3', 'newton'),
            ('4', 'ocata'),
            ('5', 'pike'),
            ('6', 'queens'),
            ('7', 'rocky'),
        ]),
    }

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
        self.render_with_interfaces(
            interfaces_list,
            configs=configs)

    def render_full_config(self, interfaces_list):
        """Render all config for Designate service

        @returns None
        """
        # Render base config first to ensure Designate API is responding as
        # sink configs rely on it.
        self.render_base_config(interfaces_list)
        self.render_with_interfaces(interfaces_list)

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
        slaves = hookenv.config('dns-slaves') or ''
        try:
            for entry in slaves.split():
                address, port, key = entry.split(':')
                unit_name = address.replace('.', '_')
                self.write_key_file(unit_name, key)
        except ValueError as e:
            hookenv.log("Problem with 'dns-slaves' config: {}"
                        .format(str(e)), level=hookenv.ERROR)

    @classmethod
    def get_domain_id(cls, domain):
        """Return the domain ID for a given domain name

        @param domain: Domain name
        @returns domain_id
        """
        if domain:
            cls.ensure_api_responding()
            get_cmd = ['reactive/designate_utils.py', 'domain-get',
                       '--domain-name', domain]
            output = subprocess.check_output(get_cmd)
            if output:
                return output.decode('utf8').strip()
        return None

    @classmethod
    def create_domain(cls, domain, email):
        """Create a domain

        @param domain: The name of the domain you are creating. The name must
                       end with a full stop.
        @param email: An email address of the person responsible for the
                      domain.
        @returns None
        """
        cls.ensure_api_responding()
        create_cmd = ['reactive/designate_utils.py', 'domain-create',
                      '--domain-name', domain, '--email', email]
        subprocess.check_call(create_cmd)

    @classmethod
    def create_server(cls, nsname):
        """ create a nameserver entry with the supplied name

        @param nsname: Name of NameserverS record
        @returns None
        """
        cls.ensure_api_responding()
        create_cmd = ['reactive/designate_utils.py', 'server-create',
                      '--server-name', nsname]
        subprocess.check_call(create_cmd)

    def domain_init_done(self):
        """Query leader db to see if domain creation is donei

        @returns boolean"""
        return hookenv.leader_get(attribute='domain-init-done')

    @classmethod
    @decorators.retry_on_exception(
        10, base_delay=5, exc_type=subprocess.CalledProcessError)
    def ensure_api_responding(cls):
        """Check that the api service is responding.

        The retry_on_exception decorator will cause this method to be called
        until it succeeds or retry limit is exceeded"""
        hookenv.log('Checking API service is responding',
                    level=hookenv.WARNING)
        check_cmd = ['reactive/designate_utils.py', 'server-list']
        subprocess.check_call(check_cmd)

    @classmethod
    @contextlib.contextmanager
    def check_zone_ids(cls, nova_domain_name, neutron_domain_name):
        zone_org_ids = {
            'nova-domain-id': cls.get_domain_id(nova_domain_name),
            'neutron-domain-id': cls.get_domain_id(neutron_domain_name),
        }
        yield
        zone_ids = {
            'nova-domain-id': cls.get_domain_id(nova_domain_name),
            'neutron-domain-id': cls.get_domain_id(neutron_domain_name),
        }
        if zone_org_ids != zone_ids:
            # Update leader-db to trigger peers to rerender configs
            # as sink files will need updating with new domain ids
            # Use host ID and current time UUID to help with debugging
            hookenv.leader_set({'domain-init-done': uuid.uuid1()})

    @classmethod
    def create_initial_servers_and_domains(cls):
        """Create the nameserver entry and domains based on the charm user
        supplied config

        @returns None
        """
        if hookenv.is_leader():
            cls.ensure_api_responding()
            nova_domain_name = hookenv.config('nova-domain')
            neutron_domain_name = hookenv.config('neutron-domain')
            with cls.check_zone_ids(nova_domain_name, neutron_domain_name):
                if hookenv.config('nameservers'):
                    for ns in hookenv.config('nameservers').split():
                        cls.create_server(ns)
                else:
                    hookenv.log('No nameserver specified, skipping creation of'
                                'nova and neutron domains',
                                level=hookenv.WARNING)
                    return
                if nova_domain_name:
                    cls.create_domain(
                        nova_domain_name,
                        hookenv.config('nova-domain-email'))
                if neutron_domain_name:
                    cls.create_domain(
                        neutron_domain_name,
                        hookenv.config('neutron-domain-email'))

    def update_pools(self):
        # designate-manage communicates with designate via message bus so no
        # need to set OS_ vars
        if hookenv.is_leader():
            cmd = ['designate-manage', 'pool', 'update']
            subprocess.check_call(cmd)

    def custom_assess_status_check(self):
        if (not hookenv.config('nameservers') and
                (hookenv.config('nova-domain') or
                 hookenv.config('neutron-domain'))):
            return 'blocked', ('nameservers must be set when specifying'
                               ' nova-domain or neutron-domain')
        dns_backend_available = (reactive
                                 .RelationBase
                                 .from_state('dns-backend.available'))
        invalid_dns = self.options.invalid_pool_config()
        if invalid_dns:
            return 'blocked', invalid_dns
        if not (dns_backend_available or hookenv.config('dns-slaves')):
            return 'blocked', ('Need either a dns-backend relation or '
                               'config(dns-slaves) or both.')
        return None, None
