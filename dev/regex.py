#!/usr/bin/env python3

import argparse,pathlib,re


def get_args():
    parser = argparse.ArgumentParser(description="Accepts a list and determines which lines are IP addresses, CIDR address ranges, or hostnames.")
    parser.add_argument("-hl","--hostlist", help="hostlist", required=False)
    return vars(parser.parse_args())


def main():
    args = get_args()
    p = pathlib.Path.cwd().joinpath(args["hostlist"])

    ip_regex = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
    cidr_regex = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])(\/(3[0-2]|[1-2][0-9]|[0-9]))$"
    hostname_regex = "^(([a-zA-Z]|[a-zA-Z][a-zA-Z0-9-]*[a-zA-Z0-9])\.)*([A-Za-z]|[A-Za-z][A-Za-z0-9-]*[A-Za-z0-9])$"

    with open(str(p), mode="r") as f:
        hostlist = (line.rstrip() for line in f)
        hostlist = list(set(line for line in hostlist if line))
        for host in hostlist:
            if re.match(ip_regex, host):
                print("IP Address: {}".format(host))
            elif re.match(cidr_regex, host):
                print("CIDR: {}".format(host))
            elif re.match(hostname_regex, host):
                print("Hostname: {}".format(host))
            else:
                print("Something else was detected: {}".format(host))

if __name__ == "__main__":
    main()
