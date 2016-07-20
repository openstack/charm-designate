#!/usr/bin/python3

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

import argparse
import os
import subprocess


def display(msg):
    print(msg)


def run_command(cmd):
    os_env = get_environment(os.environ.copy())
    p = subprocess.Popen(cmd, env=os_env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError(
            "{} failed, status code {} stdout {} stderr {}".format(
                cmd, p.returncode, out, err))
    return out, err


def get_environment(env):
    with open("/root/novarc", "r") as ins:
        for line in ins:
            k, v = line.replace('export', '').replace(" ", "").split('=')
            env[k] = v.strip()
    return env


def get_server_id(server_name):
    servers = get_servers()
    if servers.get(server_name):
        return servers[server_name]['id']


def display_server_id(server_name):
    server_id = get_server_id(server_name)
    if server_id:
        display(server_id)


def get_domain_id(domain_name):
    domains = get_domains()
    if domains.get(domain_name):
        return domains[domain_name]['id']


def display_domain_id(domain_name):
    domain_id = get_domain_id(domain_name)
    if domain_id:
        display(domain_id)


def create_server(server_name):
    server_id = get_server_id(server_name)
    if server_id:
        return server_id
    cmd = [
        'designate', 'server-create',
        '--name', server_name,
        '-f', 'value',
    ]
    out, err = run_command(cmd)
    display(get_server_id(server_name))


def create_domain(domain_name, domain_email):
    domain_id = get_domain_id(domain_name)
    if domain_id:
        return domain_id
    cmd = [
        'designate', 'domain-create',
        '--name', domain_name,
        '--email', domain_email,
        '-f', 'value',
    ]
    out, err = run_command(cmd)
    display(get_domain_id(domain_name))


def delete_domain(domain_name):
    domain_id = get_domain_id(domain_name)
    if domain_id:
        cmd = ['domain-delete', domain_id]
        run_command(cmd)


def get_domains():
    domains = {}
    cmd = ['designate', 'domain-list', '-f', 'value']
    out, err = run_command(cmd)
    for line in out.decode('utf8').split('\n'):
        values = line.split()
        if values:
            domains[values[1]] = {
                'id': values[0],
                'serial': values[2],
            }
    return domains


def get_servers():
    servers = {}
    cmd = ['designate', 'server-list', '-f', 'value']
    out, err = run_command(cmd)
    for line in out.decode('utf8').split('\n'):
        values = line.split()
        if values:
            servers[values[1]] = {
                'id': values[0],
            }
    return servers


def display_domains():
    for domain in get_domains():
        display(domain)


def display_servers():
    for server in get_servers():
        display(server)


if __name__ == '__main__':
    commands = {
        'domain-create': create_domain,
        'server-create': create_server,
        'domain-get': display_domain_id,
        'server-get': display_server_id,
        'domain-delete': delete_domain,
        'domain-list': display_domains,
        'server-list': display_servers,
    }
    cmd_args = []
    parser = argparse.ArgumentParser(description='Manage designate.')
    parser.add_argument('command',
                        help='One of: {}'.format(', '.join(commands.keys())))
    parser.add_argument('--domain-name', help='Domain Name')
    parser.add_argument('--server-name', help='Server Name')
    parser.add_argument('--email', help='Email Address')
    args = parser.parse_args()
    if args.domain_name:
        cmd_args.append(args.domain_name)
    if args.server_name:
        cmd_args.append(args.server_name)
    if args.email:
        cmd_args.append(args.email)

    if cmd_args:
        commands[args.command](*cmd_args)
    else:
        commands[args.command]()
