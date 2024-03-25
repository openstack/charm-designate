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
import charmhelpers.contrib.charmsupport.nrpe as nrpe
import charms_openstack.adapters as openstack_adapters
import charms_openstack.charm as openstack_charm
import charms_openstack.ip as os_ip
import charms_openstack.plugins as ch_plugins
import charmhelpers.core.decorators as decorators
import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host
import charms.reactive.relations as relations

from charmhelpers.contrib.network import ip as ch_ip

DESIGNATE_DIR = '/etc/designate'
DESIGNATE_DEFAULT = '/etc/default/openstack'
DESIGNATE_CONF = DESIGNATE_DIR + '/designate.conf'
POOLS_YAML = DESIGNATE_DIR + '/pools.yaml'
RNDC_KEY_CONF = DESIGNATE_DIR + '/rndc.key'
NOVA_SINK_FILE = DESIGNATE_DIR + '/conf.d/nova_sink.cfg'
NEUTRON_SINK_FILE = DESIGNATE_DIR + '/conf.d/neutron_sink.cfg'
RC_FILE = '/root/novarc'
openstack_charm.use_defaults(
    'charm.default-select-release',
    'upgrade-charm',
)


class DesignateDBAdapter(openstack_adapters.DatabaseRelationAdapter):
    """Get database URIs for the two designate databases"""

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
            application_name = slave['unit'].split('/')[0].replace('-', '_')
            pconfig.append({
                'nameserver': 'nameserver_{}'.format(application_name),
                'pool_target': 'nameserver_{}'.format(application_name),
                'address': slave['address'],
                'rndc_key_file': '/etc/designate/rndc_{}.key'.format(
                    application_name),
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
    def notification_handlers(self):
        handlers = []
        if os.path.exists(NOVA_SINK_FILE):
            handlers.append('nova_fixed')
        if os.path.exists(NEUTRON_SINK_FILE):
            handlers.append('neutron_floatingip')
        return ','.join(handlers)

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

    @property
    def rndc_master_ips(self):
        rndc_master_ips = []
        rndc_master_ip = ch_ip.get_relation_ip('dns-backend')
        rndc_master_ips.append(rndc_master_ip)
        cluster_relid = hookenv.relation_ids('cluster')[0]
        if hookenv.related_units(relid=cluster_relid):
            for unit in hookenv.related_units(relid=cluster_relid):
                rndc_master_ip = hookenv.relation_get('rndc-address',
                                                      rid=cluster_relid,
                                                      unit=unit)
                if rndc_master_ip is not None:
                    rndc_master_ips.append(rndc_master_ip)
        return rndc_master_ips

    @property
    def ns_records(self):
        """List of NS records

        @returns [] List of NS records
        """
        return self.nameservers.split()

    @property
    def also_notifies_hosts(self):
        also_notifies_hosts = []
        if hookenv.config('also-notifies'):
            for entry in hookenv.config('also-notifies').split():
                address, port = entry.split(':')
                also_notifies_hosts.append({'address': address, 'port': port})
        return also_notifies_hosts


class DesignateAdapters(openstack_adapters.OpenStackAPIRelationAdapters):
    """
    Adapters class for the Designate charm.
    """
    relation_adapters = {
        'shared_db': DesignateDBAdapter,
        'cluster': openstack_adapters.PeerHARelationAdapter,
        'dns_backend': BindRNDCRelationAdapter,
        'coordinator_memcached': openstack_adapters.MemcacheRelationAdapter,
    }


# note plugin comes first to override the config_changed method as a mixin
class DesignateCharm(ch_plugins.PolicydOverridePlugin,
                     openstack_charm.HAOpenStackCharm):
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

    healthcheck = {
        'option': 'httpchk GET /healthcheck',
        'http-check': 'expect status 200',
    }

    required_relations = ['shared-db', 'amqp', 'identity-service',
                          'coordinator-memcached']

    restart_map = {
        '/etc/default/openstack': services,
        '/etc/designate/designate.conf': services,
        '/etc/designate/rndc.key': services,
        '/etc/designate/conf.d/nova_sink.cfg': services,
        '/etc/designate/conf.d/neutron_sink.cfg': services,
        POOLS_YAML: ['designate-pool-manager'],
        RC_FILE: [''],
    }
    service_type = 'designate'
    default_service = 'designate-api'
    sync_cmd = ['designate-manage', 'database', 'sync']
    adapters_class = DesignateAdapters
    configuration_class = DesignateConfigurationAdapter

    ha_resources = ['vips', 'haproxy', 'dnsha']
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
            ('8', 'stein'),
            ('9', 'train'),
            ('10', 'ussuri'),
            ('11', 'victoria'),
            ('12', 'wallaby'),
        ]),
    }

    group = 'designate'

    # policyd override constants
    policyd_service_name = 'designate'

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

    def render_relation_rndc_keys(self):
        """Render the rndc keys for each application in the dns-backend
        relation

        @returns None
        """
        try:
            applications = []
            dns_backend = relations.endpoint_from_flag(
                'dns-backend.available').conversations()
            for conversation in dns_backend:
                application_name = conversation.scope.split(
                    '/')[0].replace('-', '_')
                if application_name not in applications:
                    applications.append(application_name)
                    rndckey = conversation.get_remote('rndckey')
                    self.write_key_file(application_name, rndckey)

        except ValueError as e:
            hookenv.log("problem writing relation_rndc_keys: {}"
                        .format(str(e)), level=hookenv.ERROR)

    def configure_sink(self):
        cmp_os_release = ch_utils.CompareOpenStackReleases(
            self.release
        )
        return cmp_os_release < 'queens'

    @classmethod
    @decorators.retry_on_exception(
        40, base_delay=5, exc_type=subprocess.CalledProcessError)
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
    @decorators.retry_on_exception(
        40, base_delay=5, exc_type=subprocess.CalledProcessError)
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
    @decorators.retry_on_exception(
        40, base_delay=5, exc_type=subprocess.CalledProcessError)
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
        40, base_delay=5, exc_type=subprocess.CalledProcessError)
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

        NOTE(AJK): This only wants to be done ONCE and by the leader, so we use
        leader settings to store that we've done it, after it's successfully
        completed.

        @returns None
        """
        KEY = 'create_initial_servers_and_domains'
        if hookenv.is_leader() and not hookenv.leader_get(KEY):
            nova_domain_name = hookenv.config('nova-domain')
            neutron_domain_name = hookenv.config('neutron-domain')
            with cls.check_zone_ids(nova_domain_name, neutron_domain_name):
                if hookenv.config('nameservers'):
                    for ns in hookenv.config('nameservers').split():
                        ns_ = ns
                        if not ns.endswith('.'):
                            ns_ = ns + '.'
                            hookenv.log(("Missing dot (.) at the end of '%s', "
                                         "adding it automatically." % ns),
                                        level=hookenv.WARNING)
                        cls.create_server(ns_)
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
            # if this fails, we weren't the leader any more; another unit may
            # attempt to do this too.
            hookenv.leader_set({KEY: 'done'})

    def update_pools(self):
        # designate-manage communicates with designate via message bus so no
        # need to set OS_ vars
        # NOTE(AJK) this runs with every hook (once most relations are up) and
        # so if it fails it will be picked up by the next relation change or
        # update-status.  i.e. it will heal eventually.
        if hookenv.is_leader():
            try:
                cmd = "designate-manage pool update"
                # Note(tinwood) that this command may fail if the pools.yaml
                # doesn't actually contain any pools.  This happens when the
                # relation is broken, which errors out the charm.  This stops
                # this happening and logs the error.
                subprocess.check_call(cmd.split(), timeout=60)
                # Update leader db to trigger restarts
                hookenv.leader_set(
                    {'pool-yaml-hash': host.file_hash(POOLS_YAML)})
            except subprocess.CalledProcessError as e:
                hookenv.log("designate-manage pool update failed: {}"
                            .format(str(e)))
            except subprocess.TimeoutExpired as e:
                # the timeout is if the rabbitmq server has gone away; it just
                # retries continuously; this lets the hook complete.
                hookenv.log("designate-manage pool command timed out: {}".
                            format(str(e)))

    def custom_assess_status_check(self):
        if self.configure_sink():
            if (not hookenv.config('nameservers') and
                    (hookenv.config('nova-domain') or
                     hookenv.config('neutron-domain'))):
                return 'blocked', ('nameservers must be set when specifying'
                                   ' nova-domain or neutron-domain')
        invalid_dns = self.options.invalid_pool_config()
        if invalid_dns:
            return 'blocked', invalid_dns
        dns_backend_available = (relations
                                 .endpoint_from_flag('dns-backend.available'))
        if not (dns_backend_available or hookenv.config('dns-slaves')):
            return 'blocked', ('Need either a dns-backend relation or '
                               'config(dns-slaves) or both.')
        return None, None

    def pool_manager_cache_sync_done(self):
        return hookenv.leader_get(attribute='pool-manager-cache-sync-done')

    def pool_manager_cache_sync(self):
        if not self.pool_manager_cache_sync_done() and hookenv.is_leader():
            sync_cmd = "designate-manage pool-manager-cache sync"
            subprocess.check_call(sync_cmd.split(), timeout=60)
            hookenv.leader_set({'pool-manager-cache-sync-done': True})
            self.restart_all()

    def render_nrpe(self):
        """Configure Nagios NRPE checks."""
        hostname = nrpe.get_nagios_hostname()
        current_unit = nrpe.get_nagios_unit_name()
        charm_nrpe = nrpe.NRPE(hostname=hostname)
        nrpe.add_init_service_checks(
            charm_nrpe, self.services, current_unit)
        charm_nrpe.write()

    def add_nrpe_nameserver_checks(self):
        """Add NRPE service checks for upstream nameservers."""
        config = hookenv.config()
        hostname = nrpe.get_nagios_hostname()
        charm_nrpe = nrpe.NRPE(hostname=hostname)
        if 'nameservers' in config:
            nameservers = config['nameservers'].split()
            for nameserver in nameservers:
                if nameserver[-1] == '.':
                    nameserver = nameserver[:-1]
                charm_nrpe.add_check(
                    "nameserver-{}".format(nameserver),
                    'Check the upstream DNS server.',
                    "check_dns -H canonical.com -s {}".format(nameserver),
                )
        charm_nrpe.write()

    def remove_nrpe_nameserver_checks(self):
        """Remove NRPE service checks for previous nameservers."""
        config = hookenv.config()
        hostname = nrpe.get_nagios_hostname()
        charm_nrpe = nrpe.NRPE(hostname=hostname)

        if config.changed('nameservers'):
            for nameserver in config.previous('nameservers').split():
                if nameserver[-1] == '.':
                    nameserver = nameserver[:-1]
                charm_nrpe.remove_check(
                    shortname="nameserver-{}".format(nameserver)
                )
        charm_nrpe.write()


class DesignateCharmQueens(DesignateCharm):

    # This charms support Queens and onward
    release = 'queens'

    services = ['designate-mdns', 'designate-zone-manager',
                'designate-agent', 'designate-pool-manager',
                'designate-central', 'designate-sink',
                'designate-api']

    restart_map = {
        '/etc/default/openstack': services,
        '/etc/designate/designate.conf': services,
        '/etc/designate/rndc.key': services,
        '/etc/designate/pools.yaml': [''],
        RC_FILE: [''],
    }

    def custom_assess_status_check(self):
        if not hookenv.config('nameservers'):
            return 'blocked', ('nameservers must be set')
        invalid_dns = self.options.invalid_pool_config()
        if invalid_dns:
            return 'blocked', invalid_dns
        dns_backend_available = (relations
                                 .endpoint_from_flag('dns-backend.available'))
        if not (dns_backend_available or hookenv.config('dns-slaves')):
            return 'blocked', ('Need either a dns-backend relation or '
                               'config(dns-slaves) or both.')
        return None, None

    def run_upgrade(self, interfaces_list=None):
        """Upgrade OpenStack if an upgrade is available and action-managed
           upgrades is not enabled.
        :param interfaces_list: List of instances of interface classes
        :returns: None
        """
        super(DesignateCharmQueens, self).run_upgrade(
            interfaces_list=interfaces_list)
        memcached = relations.endpoint_from_flag(
            'coordinator-memcached.available')
        memcached.request_restart()


# Inheriting from DesignateCharmQueens allows to keep
# enforcing nameservers' assignment while changing
# appropriate packages and services
class DesignateCharmRocky(DesignateCharmQueens):

    release = 'rocky'
    packages = ['designate-agent', 'designate-api', 'designate-central',
                'designate-common', 'designate-mdns',
                'designate-worker', 'designate-sink',
                'designate-producer', 'bind9utils',
                'python3-designate',
                'python-apt']

    services = ['designate-mdns', 'designate-producer',
                'designate-agent', 'designate-worker',
                'designate-central', 'designate-sink',
                'designate-api']

    restart_map = {
        '/etc/default/openstack': services,
        '/etc/designate/designate.conf': services,
        '/etc/designate/rndc.key': services,
        '/etc/designate/pools.yaml': [''],
        RC_FILE: [''],
    }

    purge_packages = [
        'python-designate',
        'python-memcache',
        'designate-zone-manager',
        'designate-pool-manager',
    ]

    python_version = 3

    def pool_manager_cache_sync(self):
        # NOTE(jamespage):
        # As the pool manager is no longer in use don't actually
        # sync it - just set the  done flag and move on.
        if not self.pool_manager_cache_sync_done() and hookenv.is_leader():
            hookenv.leader_set({'pool-manager-cache-sync-done': True})


class DesignateCharmVictoria(DesignateCharmRocky):

    release = 'victoria'
    packages = ['designate-agent', 'designate-api', 'designate-central',
                'designate-common', 'designate-mdns',
                'designate-worker', 'designate-sink',
                'designate-producer', 'bind9utils',
                'python3-designate',
                'python3-apt']
