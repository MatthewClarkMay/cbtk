#!/usr/bin/env python3

import argparse,ipaddress,logging,os,pathlib,re,sys,time
#import glob,configparser,json
from cbapi.live_response_api import LiveResponseError
from cbapi.response import *
from pprint import pprint


def get_args():
    parser = argparse.ArgumentParser(description="Download entire directories from sensors using Carbon Black Response API")
    parser.add_argument("-hn","--hostname", help="Sensor hostname", required=False)
    parser.add_argument("-hl","--hostlist", help="Hostlist of sensors separated by newlines. Can contain hostnames, IPs or CIDR ranges.", required=False)
    parser.add_argument("-gd","--get_directory", help="Pull down every file in directory [C:/Windows/Prefetch]", required=False)
    parser.add_argument("-dst","--dstpath", help="Destination directory path for storing retrieved files", required=False)
    parser.add_argument("-r","--recurse", help="Recursive flag for use with --get_directory", action="store_true", required=False)
    parser.add_argument("-lf","--logfile", help="Destination log file (defaults to cwd/get_dir.log) (does not truncate automatically with each program execution)", required=False)
    return vars(parser.parse_args())


# accepts string
# prints string as banner
def print_banner(banner):
    print("----------")
    print(banner)
    print("----------")


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


# accepts raw path, and os_type
# returns
def translate_path(path,os_type="windows",new_dir=None):
    if os_type.lower() in ["linux","mac"]:
        if new_dir:
            pure_path = "{}/{}/".format(pathlib.PurePosixPath(path),new_dir)
        else:
            pure_path = "{}/".format(pathlib.PurePosixPath(path))
    elif os_type.lower() == "windows":
        try:
            if new_dir:
                pure_path = "{}\\{}\\".format(pathlib.PureWindowsPath(path),new_dir)
            else:
                pure_path = "{}\\".format(pathlib.PureWindowsPath(path))
        except NotImplementedError as e:
            print("ERROR: Broke while translating path {} for os_type {} - {}".format(path,os_type,e))
            return None
    else:
        print("ERROR: Broke while translating path {} for os_type {}".format(path,os_type))
        return None
    return pure_path


class GetDirectory:
    """Job for listing and downloading directory contents from an endpoint"""

    def __init__(self, srcpath, dstpath, recurse=False):
        self.srcpath = srcpath
        self.dstpath = dstpath
        self.recurse = recurse


    def run(self, session):
        self.get_contents(session, self.srcpath, self.dstpath, self.recurse)


    # accepts live session and srcpath
    # returns list of dictionaries (files) with metadata
    def get_listing(self, session, srcpath):
        try:
            query = session.list_directory(srcpath)
        except LiveResponseError as e:
            print("ERROR: {} - {} - {}".format(e,srcpath,session.session_data["hostname"]))
            logging.error("{} - {} - {}".format(e,srcpath,session.session_data["hostname"]))
            return None
        return query


    def get_contents(self, session, srcpath, dstpath, recurse=False):
        query = self.get_listing(session, srcpath)
        if not query:
            return

        if not os.path.isdir(dstpath):
            print("ERROR: --dstpath does not exist! - building {} now...".format(dstpath))
            d = pathlib.Path(dstpath)
            d.mkdir(parents=True,exist_ok=False)

        for f in query:
            if "DIRECTORY" in f["attributes"]:
                if recurse:
                    if not (f["filename"]=="." or f["filename"]==".."):
                        print("BUILDING DIRECTORY AND RECURSING - {}".format(f["filename"]))
                        p = pathlib.Path(dstpath).joinpath(f["filename"])
                        p.mkdir(exist_ok=True)
                        contents = self.get_contents(session,"{}{}{}".format(srcpath,f["filename"],srcpath[-1]),str(p),recurse=recurse)
                        continue
                else:
                    print("GET FAILED - Directory: {} - Add with trailing backslash to get contents".format(f["filename"]))
                    continue
            else:
                print("Getting: {}".format(f["filename"]))
                pure_dst_file = pathlib.Path(dstpath).joinpath(f["filename"])
                with open(str(pure_dst_file), mode="wb") as dstfile:
                    dstfile.write(session.get_file(r"{}{}".format(srcpath,f["filename"])))


def main():
    args = get_args()
    cb = CbResponseAPI()

    if not args["logfile"]:
        logging.basicConfig(filename="get_dir.log",level=logging.ERROR)
    else:
        logpath = translate_path(args["logfile"],os_type=sys.platform)
        if logpath:
            logging.basicConfig(filename=logpath,level=logging.ERROR)
        else:
            logging.basicConfig(filename="get_dir.log",level=logging.ERROR)


    if args["get_directory"] and args["dstpath"] and args["hostname"]:
        sensor = cb.select(Sensor).where("hostname:{}".format(args["hostname"])).first()
        if not sensor:
            print("Sensor query did not return any results - Exiting now")
            logging.error("ERROR: Sensor query did not return any results - hostname:{}".format(args["hostname"]))
            sys.exit(0)
        if sensor.status.lower() != "online":
            print("Sensor is offline - Exiting now")
            logging.error("ERROR: Sensor is offline - {} derived from hostname:{}".format(sensor.computer_name, args["hostname"]))
            sys.exit(0)

        os_type=sensor.os_environment_display_string.split(" ")[0] # returns mac, linux, or windows
        pure_src_path = translate_path(args["get_directory"],os_type=os_type)
        pure_dst_path = translate_path(args["dstpath"],os_type=sys.platform,new_dir=sensor.computer_name)
        print("Downloading Directory Contents - {}: {}".format(sensor.computer_name,pure_src_path))

        # Check if pure_src_path and pure_dst_path exist before continuing (because translate_path() will no longer sys.exit(0)
        if not pure_src_path:
            print("pure_src_path returned None for os_type {} - Exiting now".format(os_type))
            logging.error("pure_src_path returned None for query hostname:{} + os_type:{} - hostname query translated to {}".format(args["hostname"],os_type,sensor.computer_name))
            sys.exit(0)
        if not pure_dst_path:
            print("pure_src_path or pure_dst_path returned None for os_type {} - Exiting now".format(os_type))
            logging.error("pure_dst_path returned None for query hostname:{} + os_type:{} - hostname query translated to {}".format(args["hostname"],os_type,sensor.computer_name))
            sys.exit(0)

        job = GetDirectory(pure_src_path, pure_dst_path, recurse=args["recurse"])
        get_directory_job = cb.live_response.submit_job(job.run, sensor.id)

        try:
            while True:
                if get_directory_job._state.lower() == "finished":
                    print("Job finished - Exiting now")
                    sys.exit(0)
                time.sleep(5)
        except KeyboardInterrupt:
            print("\rInterrupted!")
            sys.exit(0)


    if args["get_directory"] and args["dstpath"] and args["hostlist"]:
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
                    logging.error("Sensor query did not return any results - {}:{}".format(hostdict[host], host))
                    continue
                if sensor.status.lower() != "online":
                    print("Sensor is offline - {} derived from {}:{}".format(sensor.computer_name, hostdict[host], host))
                    logging.error("Sensor is offline - {} derived from {}:{}".format(sensor.computer_name, hostdict[host], host))
                    continue
                else:
                    os_type=sensor.os_environment_display_string.split(" ")[0] # returns mac, linux, or windows
                    pure_src_path = translate_path(args["get_directory"],os_type=os_type)
                    pure_dst_path = translate_path(args["dstpath"],os_type=sys.platform,new_dir=sensor.computer_name)
                    print("Downloading Directory Contents - {}: {}".format(sensor.computer_name,pure_src_path))

                    # Check if pure_src_path and pure_dst_path exist before continuing (because translate_path() will no longer sys.exit(0)
                    if not pure_src_path:
                        print("pure_src_path returned None for os_type {} - Exiting now".format(os_type))
                        logging.error("pure_src_path returned None for query hostname:{} + os_type:{} - hostname query translated to {}".format(args["hostname"],os_type,sensor.computer_name))
                    if not pure_dst_path:
                        print("pure_src_path or pure_dst_path returned None for os_type {} - Exiting now".format(os_type))
                        logging.error("pure_dst_path returned None for query hostname:{} + os_type:{} - hostname query translated to {}".format(args["hostname"],os_type,sensor.computer_name))

                    job = GetDirectory(pure_src_path, pure_dst_path, recurse=args["recurse"])
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
