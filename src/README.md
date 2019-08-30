# Overview

This charm provides Designate (DNSaaS) for an OpenStack Cloud.


# Usage

Designate relies on services from the mysql, rabbitmq-server and keystone
charms:

    juju deploy designate
    juju deploy mysql
    juju deploy rabbitmq-server
    juju deploy keystone
    juju deploy memcached
    juju add-relation designate memcached
    juju add-relation designate mysql
    juju add-relation designate rabbitmq-server
    juju add-relation designate keystone

To add support for DNS record auto-generation when Neutron ports and
floating IPs are created the charm needs a relation with neutron-api charm:

    juju deploy neutron-api
    juju add-relation designate neutron-api

The charm needs to store DNS records. This can be achieved by setting the
dns-slave config option or by relating to the designate-bind charm:

    juju deploy designate-bind
    juju add-relation designate designate-bind

For Queens and later, the nameservers config value must be set:

    juju config designate nameservers="ns1.example.com. ns2.example.com."

# Policy Overrides

This feature allows for policy overrides using the `policy.d` directory.  This
is an **advanced** feature and the policies that the OpenStack service supports
should be clearly and unambiguously understood before trying to override, or
add to, the default policies that the service uses.  The charm also has some
policy defaults.  They should also be understood before being overridden.

> **Caution**: It is possible to break the system (for tenants and other
  services) if policies are incorrectly applied to the service.

Policy overrides are YAML files that contain rules that will add to, or
override, existing policy rules in the service.  The `policy.d` directory is
a place to put the YAML override files.  This charm owns the
`/etc/keystone/policy.d` directory, and as such, any manual changes to it will
be overwritten on charm upgrades.

Overrides are provided to the charm using a Juju resource called
`policyd-override`.  The resource is a ZIP file.  This file, say
`overrides.zip`, is attached to the charm by:


    juju attach-resource designate policyd-override=overrides.zip

The policy override is enabled in the charm using:

    juju config designate use-policyd-override=true

When `use-policyd-override` is `True` the status line of the charm will be
prefixed with `PO:` indicating that policies have been overridden.  If the
installation of the policy override YAML files failed for any reason then the
status line will be prefixed with `PO (broken):`.  The log file for the charm
will indicate the reason.  No policy override files are installed if the `PO
(broken):` is shown.  The status line indicates that the overrides are broken,
not that the policy for the service has failed. The policy will be the defaults
for the charm and service.

Policy overrides on one service may affect the functionality of another
service. Therefore, it may be necessary to provide policy overrides for
multiple service charms to achieve a consistent set of policies across the
OpenStack system.  The charms for the other services that may need overrides
should be checked to ensure that they support overrides before proceeding.

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-designate/+filebug).

For general questions please refer to the OpenStack [Charm Guide](http://docs.openstack.org/developer/charm-guide/).
