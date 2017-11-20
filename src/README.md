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

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-designate/+filebug).

For general questions please refer to the OpenStack [Charm Guide](http://docs.openstack.org/developer/charm-guide/).
