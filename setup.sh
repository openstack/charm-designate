#!/bin/bash
export http_proxy=http://squid.internal:3128                                                              
export https_proxy=http://squid.internal:3128
export JUJU_REPOSITORY="$(pwd)/build"
export INTERFACE_PATH=interfaces
export LAYER_PATH=layers
rm -rf $JUJU_REPOSITORY
mkdir -p $JUJU_REPOSITORY
if [[ ! -d $INTERFACE_PATH ]]; then
    mkdir $INTERFACE_PATH
    ( cd $INTERFACE_PATH;
	git clone git+ssh://git.launchpad.net/~gnuoy/charms/+source/interface-bind-rndc bind-rndc; )
fi
if [[ ! -d $LAYER_PATH ]]; then
    mkdir $LAYER_PATH
    ( cd $LAYER_PATH;
      git clone git+ssh://git.launchpad.net/~openstack-charmers-layers/charms/+source/reactive-openstack-api-layer openstack-api;
      git clone git+ssh://git.launchpad.net/~openstack-charmers-layers/charms/+source/reactive-openstack-principle-layer openstack-principle;
      git clone git+ssh://git.launchpad.net/~gnuoy/charms/+source/reactive-openstack-layer openstack; )
fi
make clean
make generate
# ./kill_charms.sh designate
#juju-deployer -c barbican.yaml
echo $JUJU_REPOSITORY
