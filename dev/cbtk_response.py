#!/usr/bin/env python3

import argparse,configparser,glob,json,os,pathlib,sys
from cbapi.live_response_api import LiveResponseError
from cbapi.response import *


def get_args():
    parser = argparse.ArgumentParser(description="Interact with Carbon Black Response API")
    #parser.add_argument("-ith","--ip_to_hostname", help="Lookup sensor_id by IP address", required=False)
    #parser.add_argument("-sth","--sensor_to_hostname", help="Lookup hostname by sensor_id", required=False)
    parser.add_argument("-htsl","--hostname_to_sensor_list", help="Lookup sensor_id list by full or partial hostname", required=False)
    parser.add_argument("-hn","--hostname", help="hostname", required=False)
    parser.add_argument("-hl","--hostlist", help="hostlis", required=False)
    parser.add_argument("-d","--details", help="Print sensor details", action="store_true", required=False)
    parser.add_argument("-ld","--list_directory", help="List every file in directory (can be used with --verbose flag) (backslashes in filepath must be escaped, and directories must end in a backslash) [C:\\\Windows\\\]", required=False)
    parser.add_argument("-gd","--get_directory", help="Pull down every file in directory (backslashes in filepath must be escaped, and directories must end in a backslash) [C:\\\Windows\\\]", required=False)
    parser.add_argument("-dst","--dstpath", help="Destination directory path for storing retrieved files", required=False)
    parser.add_argument("-r","--recurse", help="Recursive flag for use with --list_direcrory and --get_directory", action="store_true", required=False)
    parser.add_argument("-v","--verbose", help="Verbose output", action="store_true", required=False)
    return vars(parser.parse_args())


# accepts list of dictionaries
# returns single dictionary of specific {"key":"value"} pairs for each dictionary
def dict_list_to_kv_dict(dict_array,k,v):
    kv_dict = {}
    for dictionary in dict_array:
        kv_dict[getattr(dictionary,k)] = getattr(dictionary,v)
    return kv_dict# recurse through files in 


# accepts live session, srcpath, and dstpath - recurse optional
# srcpath and dstpath should be generated using translate_path() ...
# because if paths dont have trailing slashes this will break
# downloads all files in remote srcpath to local dstpath
def get_directory_contents(session,srcpath,dstpath,recurse=False):
    if not os.path.isdir(dstpath):
        print("ERROR: --dstpath does not exist! - building {} now...".format(dstpath))
        d = pathlib.Path(dstpath)
        d.mkdir(exist_ok=False)

    query = get_directory_listing(session,srcpath)
    if not query:
        return None

    for f in query:
        if "DIRECTORY" in f["attributes"]:
            if recurse:
                if not (f["filename"]=="." or f["filename"]==".."):
                    print("BUILDING DIRECTORY AND RECURSING - {}".format(f["filename"]))
                    p = pathlib.Path(dstpath).joinpath(f["filename"])
                    # @NOTE: uncomment to not recurse into subdirs, assuming they exist
                           # exist_ok acts like mkdir -p --> recurses into subdirs, and 
                           # overwrites all files --> ideal if data could be changing
                           # frequently
                    #try:
                    p.mkdir(exist_ok=True)
                    #except FileExistsError as e:
                    #    print("ERROR: {}".format(e))
                    #    continue
                    get_directory_contents(session,"{}{}{}".format(srcpath,f["filename"],srcpath[-1]),str(p),recurse=recurse)
                    continue
            else:
                print("GET FAILED - Directory: {} - Add with trailing backslash to get contents".format(f["filename"]))
                continue
        else:
            print("Getting: {}".format(f["filename"]))
            #with open("{}/{}".format(dstpath,f["filename"]), "wb") as dstfile:
            pure_dst_file = pathlib.Path(dstpath).joinpath(f["filename"])
            with open(str(pure_dst_file), mode="wb") as dstfile:
                dstfile.write(session.get_file(r"{}{}".format(srcpath,f["filename"])))


# accepts live session and srcpath
# returns list of dictionaries (files) with metadata
def get_directory_listing(session,srcpath):
    try:
        query = session.list_directory(srcpath)
    except LiveResponseError as e:
        # @TODO - add logging for this exception
        print("ERROR: {}".format(e))
        return None
    return query


# accepts directory_listing (get_directory_listing() output) - verbose optional
# formats, and prints content
# @TODO reformat output so each file outputs to a single line
def print_directory_listing(directory_listing, verbose=False):
    for f in directory_listing:
        if verbose:
            print_dict(f)
            print()
        else:
            if "DIRECTORY" in f["attributes"]:
                print("Directory: {}".format(f["filename"]))
            else:
                print("File: {}".format(f["filename"]))


# accepts string
# prints string as banner
def print_banner(banner):
    print("----------")
    print(banner)
    print("----------")


# accepts dictionary
# prints keys/values in alphabetical order
def print_dict(dictionary):
    for k, v in sorted(dictionary.items()):
        print("{}: {}".format(k,v))


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
                pure_path = "{}\\{}\\".format(pathlib.PureWindowsPath(path))
            else:
                pure_path = "{}\\".format(pathlib.PureWindowsPath(path))
        except NotImplementedError as e:
            print("ERROR: Broke while translating path {} for os_type {} - {}".format(path,os_type,e))
            sys.exit(0)
    else:
        print("ERROR: Broke while translating path {} for os_type {}".format(path,os_type))
        sys.exit(0)
    return pure_path


def main():
    args = get_args()
    cb = CbResponseAPI()

# get_directory_listing() AND print_directory_listing()
    if args["list_directory"] and args["hostname"]:
        sensor = cb.select(Sensor).where("hostname:{}".format(args["hostname"])).first()
        os_type=sensor.os_environment_display_string.split(" ")[0] # returns mac, linux, or windows
        pure_path = translate_path(args["list_directory"],os_type=os_type)
        print_banner("Listing Directory Contents - {}: {}".format(sensor.computer_name,pure_path))

        with sensor.lr_session() as session:
            directory_listing = get_directory_listing(session,pure_path)
            if directory_listing:
                print_directory_listing(directory_listing, verbose=args["verbose"])

    elif args["list_directory"] and not args["hostname"]:
        print("--hostname required with --list_directory")
        sys.exit(0)


# get_directory()
    if args["get_directory"] and args["dstpath"] and args["hostname"]:
        sensor = cb.select(Sensor).where("hostname:{}".format(args["hostname"])).first()
        os_type=sensor.os_environment_display_string.split(" ")[0] # returns mac, linux, or windows
        pure_src_path = translate_path(args["get_directory"],os_type=os_type)
        pure_dst_path = translate_path(args["dstpath"],os_type=sys.platform)
        print_banner("Downloading Directory Contents - {}: {}".format(sensor.computer_name,pure_src_path))

        with sensor.lr_session() as session:
            if args["recurse"]:
                get_directory_contents(session,pure_src_path,pure_dst_path,recurse=True)
            else:
                get_directory_contents(session,pure_src_path,pure_dst_path)

    if args["get_directory"] and args["dstpath"] and args["hostlist"]:
        p = pathlib.Path.cwd().joinpath(args["hostlist"])
        with open(str(p), mode="r") as f:
            hostlist = f.readlines()
            for host in hostlist:
                sensor = cb.select(Sensor).where("hostname:{}".format(host.strip("\n\r"))).first()
                os_type=sensor.os_environment_display_string.split(" ")[0] # returns mac, linux, or windows
                pure_src_path = translate_path(args["get_directory"],os_type=os_type)
                pure_dst_path = translate_path(args["dstpath"],os_type=sys.platform,new_dir=sensor.computer_name)
                print_banner("Downloading Directory Contents - {}: {}".format(sensor.computer_name,pure_src_path))
                if args["recurse"]:
                    get_directory_job = cb.live_response.submit_job(
                        get_directory_contents(session,pure_src_path,pure_dst_path,recurse=True),
                        sensor.id
                    )
                else:
                    get_directory_job = cb.live_response.submit_job(
                        get_directory_contents(session,pure_src_path,pure_dst_path),
                        sensor.id
                    )

    elif args["get_directory"] and not (args["dstpath"] and (args["hostname"] or args["hostlist"])):
        print("--hostname and --dstpath required with --get_directory")
        sys.exit(0)


# hostname_to_sensor_list()
    if args["hostname_to_sensor_list"]:
        query = cb.select(Sensor).where("hostname:{}".format(args["hostname_to_sensor_list"]))
        hostname_sensor_id_dict = dict_list_to_kv_dict(query, "hostname", "id")
        print_banner("Printing [HOSTNAME: SENSOR_ID] - Alphabetical Order")
        print_dict(hostname_sensor_id_dict)


# print sensor details
    if args["details"] and args["hostname"]:
        sensor = cb.select(Sensor).where("hostname:{}".format(args["hostname"])).first()
        print(sensor)

    elif args["details"] and not args["hostname"]:
        print("--hostname required with --details")
        sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\rInterrupted!")
        sys.exit(0)
