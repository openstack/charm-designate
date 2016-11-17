# Overview

This charm provides Designate (DNSaaS) for an OpenStack Cloud.


# Usage

Designate relies on services from the mysql, rabbitmq-server and keystone
charms:

    juju deploy designate
    juju deploy mysql
    juju deploy rabbitmq-server
    juju deploy keystone
    juju add-relation designate mysql
    juju add-relation designate rabbitmq-server
    juju add-relation designate keystone

To add support for auto-generated records when guests are booted the charm 
needs a relation with nova-compute:

    juju deploy nova-compute
    juju add-relation designate nova-compute

The charm needs to store DNS records. This can be achieved  by setting the
dns-slave config option or by relating to the designate-bind charm:

    juju deploy designate-bind
    juju add-relation designate designate-bind

# Bugs

Please report bugs on [Launchpad](https://bugs.launchpad.net/charm-designate/+filebug).

For general questions please refer to the OpenStack [Charm Guide](http://docs.openstack.org/developer/charm-guide/).
