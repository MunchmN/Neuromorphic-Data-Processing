import csv
from itertools import islice
import matplotlib
import matplotlib.pyplot as plt
from plotting_utils import filename_regex
import argparse
import os
import math
from plotting_utils.plotting_helper import path_arg, file_arg, int_arg_not_negative, int_arg_positive_nonzero


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("aedat_csv_file", help="CSV with AEDAT data to plot", type=file_arg)

    parser.add_argument(
        "--pixel_x", "-x", help="x coordinate of desired pixel", type=int_arg_not_negative, required=True
    )
    parser.add_argument(
        "--pixel_y", "-y", help="y coordinate of desired pixel", type=int_arg_not_negative, required=True
    )
    parser.add_argument(
        "--area_size", "-a", help="size of box around pixel to observe", type=int_arg_positive_nonzero, required=True
    )
    parser.add_argument(
        "--max_plot_points",
        "-m",
        help="max number of points to plot",
        default=math.inf,
        type=int_arg_positive_nonzero,
    )
    parser.add_argument("--save_directory", "-d", help="Save file to directory", default=".", type=path_arg)

    return parser.parse_args()


def main(args: argparse.Namespace):
    matplotlib.use("Qt5Agg")

    last_pixel_state = None
    redundancies = 0  # TODO: do redundancies for all pixels

    change_timestamps = []  # The times when the pixel changed state
    time_between = []  # The times between the state changes

    with open(args.aedat_csv_file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")

        for row in islice(csv_reader, 1, None):  # Skip the header
            x_row = int(row[1])
            y_row = int(row[2])

            check_x = abs(x_row - args.pixel_x)
            check_y = abs(y_row - args.pixel_y)

            if check_x < args.area_size and check_y < args.area_size:
                pixel_state = (row[0] == "True") or (row[0] == "1")

                if pixel_state != last_pixel_state:
                    last_pixel_state = pixel_state
                    change_timestamps.append(float(row[3]))
                    if len(change_timestamps) > args.max_plot_points:
                        break
                else:
                    redundancies += 1

    print(f"Redundancies: {redundancies}")

    # Normalize timestamps & convert to mS
    change_timestamps = [(x - change_timestamps[0]) / 1000 for x in change_timestamps]

    # Get the time between timestamps
    for i in range(len(change_timestamps) - 1):
        time_between.append(change_timestamps[i + 1] - change_timestamps[i])

    # Add lines to plot
    for stamp in change_timestamps:
        plt.plot([stamp, stamp], [0, 1], "b")

    plt.ylim(0, 1.2)
    plt.yticks([])
    plt.title("Temporal Resoltion")
    plt.xlabel("Time(mS)")

    hz = filename_regex.parse_frequency(args.aedat_csv_file, "Hz_")
    voltage = filename_regex.parse_voltage(args.aedat_csv_file, "V_")
    waveform_type = filename_regex.parse_waveform(args.aedat_csv_file, "_")
    degrees = filename_regex.parse_degrees(args.aedat_csv_file, "_DegreesPolarized")

    # TODO: what if the file is specified as polarized but no angle is given?

    if hz == "" and degrees == "":
        print("WARNING: Could not infer polarizer angle or frequency from file name")

    plt.savefig(os.path.join(args.save_directory, f"{hz}{voltage}{waveform_type}{degrees}_event_density.png"))

    if len(time_between) != 0:
        print(f"Average time between: {round(sum(time_between) / len(time_between), 2)}mS")


if __name__ == "__main__":
    args = get_args()
    main(args)
