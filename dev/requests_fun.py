#!/usr/bin/env python3

import cbapi,argparse,configparser,json,requests,sys

def get_args():
    parser = argparse.ArgumentParser(description="Interact with Carbon Black Response API")
    parser.add_argument("-i","--id", help="sensor_id", required=False)
    parser.add_argument("-hts","--hostname_to_sensor", help="Lookup sensor_id by hostname", required=False)
    parser.add_argument("-its","--ip_to_sensor", help="Lookup sensor_id by IP address", required=False)
    parser.add_argument("-sth","--sensor_to_hostname", help="Lookup hostname by IP address", required=False)
    parser.add_argument("-s","--server", help="Carbon Black Server FQDN", required=False)
    parser.add_argument("--no_check_ssl", help="Ignore SSL certificate errors", required=False, action="store_true")
    return vars(parser.parse_args())


def get_config(config_path):
    config = configparser.ConfigParser()
    config.read("cbtk.cfg")


# Queries list of all sensors and attributes in JSON
# Accepts api_token, api_url_base, and ssl_check flag
# Returns deserialized JSON object - python object (list of dicts) 
def get_all_sensors(api_token, api_url_base, ssl_check):
    headers = {"X-Auth-Token": api_token}
    api_url = "{}sensor".format(api_url_base)

    try:
        response = requests.get(api_url, headers=headers, verify=ssl_check)
        if response.status_code == 200:
            deserialized_json = json.loads(response.content.decode("utf-8"))
            return deserialized_json
        else:
            print("{}: Try again!".format(response.status_code))
            sys.exit()
    except requests.exceptions.SSLError as request_error:
        print("ERROR: {} - check your certificate, or use the --no_check_ssl flag to ignore this warning".format(request_error))
        sys.exit()


def main():

    api_token = ""
    api_url_base = "https://carbonblack.yourdomain.com/api/v1/"

    args = get_args()

    if args["no_check_ssl"]:
        ssl_check = False
    else:
        ssl_check = True

    sensors = get_all_sensors(api_token, api_url_base, ssl_check)

    #print(json.dumps(sensors, indent=4, sort_keys=False))

    if args["hostname_to_sensor"]:
        for sensor in sensors:
            if sensor["computer_name"].lower() == args["hostname_to_sensor"].lower():
                print(sensor["id"])
            else:
                continue
    else:
        pass

    if args["ip_to_sensor"]:
        pass
    else:
        pass


if __name__ == "__main__":
    main()
