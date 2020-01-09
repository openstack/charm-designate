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

## Policy Overrides

Policy overrides is an **advanced** feature that allows an operator to override
the default policy of an OpenStack service. The policies that the service
supports, the defaults it implements in its code, and the defaults that a charm
may include should all be clearly understood before proceeding.

> **Caution**: It is possible to break the system (for tenants and other
  services) if policies are incorrectly applied to the service.

Policy statements are placed in a YAML file. This file (or files) is then (ZIP)
compressed into a single file and used as an application resource. The override
is then enabled via a Boolean charm option.

Here are the essential commands (filenames are arbitrary):

    zip overrides.zip override-file.yaml
    juju attach-resource designate policyd-override=overrides.zip
    juju config designate use-policyd-override=true

See appendix [Policy Overrides][cdg-appendix-n] in the [OpenStack Charms
Deployment Guide][cdg] for a thorough treatment of this feature.

# Bugs

Please report bugs on [Launchpad][lp-bugs-charm-designate].

For general charm questions refer to the OpenStack [Charm Guide][cg].

<!-- LINKS -->

[cg]: https://docs.openstack.org/charm-guide
[cdg]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide
[cdg-appendix-n]: https://docs.openstack.org/project-deploy-guide/charm-deployment-guide/latest/app-policy-overrides.html
[lp-bugs-charm-designate]: https://bugs.launchpad.net/charm-designate/+filebug
