#!/usr/bin/env python3

import argparse,ipaddress,logging,os,pathlib,re,sys,time
#import glob,configparser,json
from cbapi.live_response_api import LiveResponseError
from cbapi.response import *
from pprint import pprint


def get_args():
    parser = argparse.ArgumentParser(description="Run processes on sensors using Carbon Black Response API (In Development / PoC)")
    parser.add_argument("-hn","--hostname", help="Sensor hostname", required=False)
    parser.add_argument("-hl","--hostlist", help="Hostlist of sensors separated by newlines. Can contain hostnames, IPs or CIDR ranges.", required=False)
    parser.add_argument("-cp","--create_proc", help="Command line argument to run on host", required=False, action="store_true")
    return vars(parser.parse_args())


# accepts string
# determines whether that string is an ip, cidr range, or hostname - returns verdict as a string
def translate_host(host):
    ip = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])$"
    cidr = "^(([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])\.){3}([0-9]|[1-9][0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5])(\/(3[0-2]|[1-2][0-9]|[0-9]))$"
    if re.match(ip, host):
        return "ip"
    if re.match(cidr, host):
        return "cidr"
    else:
        return "hostname"


class CreateProc:
    """Job for listing and downloading directory contents from an endpoint"""

    def __init__(self):
        pass


    def run(self, session):
        print(session.create_process(r'netstat -at'))



def main():
    args = get_args()
    cb = CbResponseAPI()

    if args["create_proc"] and args["hostname"]:
        sensor = cb.select(Sensor).where("hostname:{}".format(args["hostname"])).first()
        if not sensor:
            print("Sensor query did not return any results - Exiting now")
            sys.exit(0)
        if sensor.status.lower() != "online":
            print("Sensor is offline - Exiting now")
            sys.exit(0)

        os_type=sensor.os_environment_display_string.split(" ")[0] # returns mac, linux, or windows
        print("Running Command on {}".format(sensor.computer_name))

        job = CreateProc()
        create_proc_job = cb.live_response.submit_job(job.run, sensor.id)

        try:
            while True:
                pprint(vars(create_proc_job)) #here to show how create_proc_job._state works
                if create_proc_job._state.lower() == "finished":
                    print("Job finished - Exiting now")
                    sys.exit(0)
                time.sleep(5)
        except KeyboardInterrupt:
            print("\rInterrupted!")
            sys.exit(0)


    if args["create_proc"] and args["hostlist"]:
        job_dict = {}
        p = pathlib.Path.cwd().joinpath(args["hostlist"])
        with open(str(p), mode="r") as f:
            rawlist = (line.rstrip() for line in f)
            hostdict = {}

            for host in rawlist:
                if translate_host(host) == "ip":
                    hostdict[host] = "ip"
                elif translate_host(host) == "cidr":
                    net = ipaddress.ip_network(host)
                    for n in net:
                        hostdict[str(n)] = "ip"
                else:
                    hostdict[host] = "hostname"

            for host in hostdict:
                if hostdict[host] == "hostname":
                    sensor = cb.select(Sensor).where("hostname:{}".format(host.strip("\n\r"))).first()
                if hostdict[host] == "ip":
                    sensor = cb.select(Sensor).where("ip:{}".format(host.strip("\n\r"))).first()

                if not sensor:
                    print("Sensor query did not return any results - {}:{}".format(hostdict[host], host))
                    continue
                if sensor.status.lower() != "online":
                    print("Sensor is offline - {} derived from {}:{}".format(sensor.computer_name, hostdict[host], host))
                    continue
                else:
                    os_type=sensor.os_environment_display_string.split(" ")[0] # returns mac, linux, or windows
                    print("Running Command on {}".format(sensor.computer_name))

                    job = CreateProc()
                    job_dict[sensor.computer_name] = cb.live_response.submit_job(job.run, sensor.id)

        try:
            while True:
                counter = 0
                for job in job_dict:
                    if job_dict[job]._state.lower() == "finished":
                        counter += 1
                if len(job_dict) == counter:
                    print("All jobs finished - Exiting now")
                    sys.exit(0)
                time.sleep(5)
        except KeyboardInterrupt:
            print("\rInterrupted!")
            sys.exit(0)


    elif args["get_directory"] and not (args["dstpath"] and (args["hostname"] or args["hostlist"])):
        print("--hostname and --dstpath required with --get_directory")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\rInterrupted!")
        sys.exit(0)
