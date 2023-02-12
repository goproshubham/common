import drivers
import time
import os
import speedtest
import datetime
import subprocess
import schedule
import multiprocessing
import json

# DEFAULTS ---------------------------------------------------------------------

INTERVAL_SHIFT = 5  # seconds
json_file_name = "pi_monitor.json"
INTERNET_DOWN_STRING = "----NET DOWN----"  # 16 characters
dict_default = {
    "INTERNET": {"IP": "8.8.8.8", "PORT": "80", "STATUS": "DOWN"},
    "NAS_GOPI": {"IP": "8.8.8.8", "PORT": "80", "STATUS": "DOWN"},
    "NAS_GOKU": {"IP": "8.8.8.8", "PORT": "80", "STATUS": "DOWN"},
    "PLEX": {"IP": "8.8.8.8", "PORT": "80", "STATUS": "DOWN"},
    "INTERNET_SPEED": {"DOWNLOAD_SPEED": 0, "UPLOAD_SPEED": 0},
}

# --------------------------------------------------------------------------------


# if host responds to a ping request within the timeout interval
def ping(ip, timeout=3):
    if (
        subprocess.call(
            ["ping", "-c", "1", "-W", str(timeout), str(ip)],
            stdout=open(os.devnull, "w"),
            stderr=open(os.devnull, "w"),
        )
        == 0
    ):
        return "UP"
    else:
        return "DOWN"


# if host has given port open
def netcat(ip, port, timeout=3):
    if (
        subprocess.call(
            ["nc", "-z", "-w", str(timeout), str(ip), str(port)],
            stderr=open(os.devnull, "w"),
        )
        == 0
    ):
        return "UP"
    else:
        return "DOWN"


# returns speedtest results
def do_speedtest():

    try:
        s = speedtest.Speedtest()
        s.get_best_server()
        s.download()
        s.upload()
        return s.results.dict()

    except Exception as e:
        print("ERROR __speedtest: ", e)
        return {}


def do_all_tasks():

    with open(json_file_name, "r") as json_file:

        # try reading file
        try:
            dict_common = json.load(json_file)
        # if file not found, use default
        except:
            dict_common = dict_default

        # use ping for hosts
        dict_common["INTERNET"]["STATUS"] = ping(dict_common["INTERNET"]["IP"])

        # use netcat for services
        dict_common["NAS_GOPI"]["STATUS"] = netcat(
            dict_common["NAS_GOPI"]["IP"],
            dict_common["NAS_GOPI"]["PORT"],
        )
        dict_common["NAS_GOKU"]["STATUS"] = netcat(
            dict_common["NAS_GOKU"]["IP"],
            dict_common["NAS_GOKU"]["PORT"],
        )
        dict_common["PLEX"]["STATUS"] = netcat(
            dict_common["PLEX"]["IP"],
            dict_common["PLEX"]["PORT"],
        )

        # get speedtest results
        result = do_speedtest()

        if result:
            # convert bits to megabytes appropriately
            dict_common["INTERNET_SPEED"]["UPLOAD_SPEED"] = round(
                result["upload"] / 8000000, 2
            )
            dict_common["INTERNET_SPEED"]["DOWNLOAD_SPEED"] = round(
                result["download"] / 8000000, 2
            )

    with open(json_file_name, "w") as json_file:

        # Serializing json
        json_object = json.dumps(dict_common, indent=4)

        # updating status file
        json_file.write(json_object)


def do_all_tasks__in_background():

    multiprocessing.Process(target=do_all_tasks).start()


if __name__ == "__main__":

    # Load the driver and set it to "display"
    # If you use something from the driver library use the "display." prefix first
    display = drivers.Lcd()

    # initial status check -----------------------------------------------------
    do_all_tasks()

    # schedule status check ----------------------------------------------------
    schedule.every(30).seconds.do(do_all_tasks__in_background)

    # set initial timestamp for status change before loop
    timestamp = time.time()
    STATUS_INDEX = 0

    try:

        # LOOP ---------------------------------------------------------------------
        while True:

            # Checks whether a scheduled task is pending to run or not
            schedule.run_pending()

            dt = datetime.datetime.now()

            # FIRST LINE ========================================

            # Format datetime string for 16 characters
            time_string = dt.strftime("%I:%M:%S, %a %d")

            display.lcd_display_string(time_string, 1)
            # print(time_string, len(time_string))

            # SECOND LINE ========================================
            # Internet Up or Down === Constant
            #    If ONLINE
            #       Display SPEED CONSTANT
            #       and Cycle through the hosts
            #           1) NAS_GOPI up or down
            #           2) NAS_GOKU up or down
            #           3) PLEX up or down
            #    If OFFLINE
            #       Display "INTERNET DOWN"

            with open(json_file_name, "r") as json_file:

                dict_common = json.load(json_file)

                if dict_common["INTERNET"]["STATUS"] == "UP":

                    # change the status after the interval
                    if time.time() - timestamp > INTERVAL_SHIFT:
                        timestamp = time.time()
                        STATUS_INDEX += 1

                        # if reached end of dict, reset
                        if STATUS_INDEX == len(dict_common):
                            STATUS_INDEX = 0

                    # if INTERNET, skip
                    if list(dict_common.keys())[STATUS_INDEX] == "INTERNET":
                        STATUS_INDEX += 1

                    # FORMAT info_string based on STATUS_INDEX
                    if list(dict_common.keys())[STATUS_INDEX] == "INTERNET_SPEED":
                        info_string = "\u25B2{} \u25BC{} MB".format(
                            dict_common["INTERNET_SPEED"]["DOWNLOAD_SPEED"],
                            dict_common["INTERNET_SPEED"]["UPLOAD_SPEED"],
                        )

                    else:
                        info_string = list(dict_common.keys())[STATUS_INDEX]

                        info_string += " 🡆  "

                        info_string += dict_common[
                            list(dict_common.keys())[STATUS_INDEX]
                        ]["STATUS"]

                else:
                    info_string = INTERNET_DOWN_STRING

                display.lcd_display_string(info_string, 2)
                # print(info_string, len(info_string))

                time.sleep(0.5)

    except KeyboardInterrupt:

        # If there is a KeyboardInterrupt (when you press ctrl+c), exit the program and cleanup
        # print("Cleaning up!")
        display.lcd_clear()

    except (RuntimeError, IOError):
        # print("I2C bus error", 1)
        display.lcd_clear()
