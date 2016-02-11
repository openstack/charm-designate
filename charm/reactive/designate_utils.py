#!/usr/bin/python3

import subprocess
import argparse
import os


def run_command(cmd):
    os_env = get_environment()
    p = subprocess.Popen(cmd, env=os_env, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    out, err = p.communicate()
    return out, err


def get_environment():
    env = os.environ
    with open("/root/novarc", "r") as ins:
        for line in ins:
            k, v = line.replace('export', '').replace(" ", "").split('=')
            env[k] = v.strip()
    return env


def get_server_id(args, server_name):
    servers = get_servers()
    if servers.get(server_name):
        return servers[server_name]['id']


def get_domain_id(args, domain_name):
    domains = get_domains()
    if domains.get(domain_name):
        return domains[domain_name]['id']


def create_server(args):
    server_name = args.command[1]
    server_id = get_server_id(args, server_name)
    if server_id:
        return server_id
    cmd = [
        'designate', 'server-create',
        '--name', server_name,
        '-f', 'value',
    ]
    out, err = run_command(cmd)
    return get_server_id(args, server_name)


def create_domain(args):
    domain_name = args.command[1]
    domain_email = args.command[2]
    domain_id = get_domain_id(args, domain_name)
    if domain_id:
        return domain_id
    cmd = [
        'designate', 'domain-create',
        '--name', domain_name,
        '--email', domain_email,
        '-f', 'value',
    ]
    out, err = run_command(cmd)
    return get_domain_id(args, domain_name)


def delete_domain(args, domain_id):
    cmd = ['domain-delete', domain_id]
    out, err = run_command(cmd)


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

if __name__ == '__main__':
    get_environment()
    parser = argparse.ArgumentParser(description='Manage designate.')
    parser.add_argument('command', nargs='*', help='designate command')
    args = parser.parse_args()
    if args.command[0] == 'domain-create':
        print(create_domain(args))
    elif args.command[0] == 'server-create':
        print(create_server(args))
    elif args.command[0] == 'domain-get':
        domain_id = get_domain_id(args, args.command[1])
        if domain_id:
            print(domain_id)
    elif args.command[0] == 'server-get':
        server_id = get_server_id(args, args.command[1])
        if server_id:
            print(server_id)
    elif args.command[0] == 'domain-delete':
        domain_id = get_domain_id(args, args.command[1])
        delete_domain(args, domain_id)
    elif args.command[0] == 'domain-list':
        print(get_domains())
