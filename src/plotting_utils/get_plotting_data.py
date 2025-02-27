import csv
import os
import json
import itertools
from typing import Callable, List
import sys
from enum import Enum


class EventChunkConfig:
    graphType: str
    """hist, wavelets, kmeans, smooth buts lets be honest. its just hist """

    saveFigures: bool
    """ Saves the figures if set to True, Shows the figures if False """

    dataFolder: str
    """The folder where the data is"""
    plotVariance: bool
    """If true will calculate the variance values """
    plotFWHM: bool
    """If true will calculate the FWHM """

    FWHMMultiplier: float
    """ Used to change FHWM(2.355) to standard deviation(1)"""

    logValues: bool
    """Logs all the values if true """

    dataSetType: str
    """ waveforms, frequency, waveformsAndFrequency, or backgrounds"""

    plotConstant: str
    """ The variable that is constant on the graph """

    maxEventCount: int
    """ The max event count to read from the file """

    reconstructionWindow: int
    """ The settings used to generate the csv files"""

    gaussianMinY: float

    gaussianMaxY: float

    def __init__(
        self,
        graph_type="hist",
        data_folder="",
        save_figures=False,
        plot_variance=False,
        fwhm_multiplier=2.355,
        log_values=False,
        plot_fwhm=False,
        data_set_type="waveformsAndFrequency",
        plot_constant="waveforms",
        max_event_count=-1,
        reconstruction_window=500,
        gaussian_min_y=0,
        gaussian_max_y=1,
    ):
        self.graphType = graph_type
        self.dataFolder = data_folder
        self.saveFigures = save_figures
        self.plotVariance = plot_variance
        self.FWHMMultiplier = fwhm_multiplier
        self.logValues = log_values
        self.plotFWHM = plot_fwhm
        self.dataSetType = data_set_type
        self.plotConstant = plot_constant
        self.maxEventCount = max_event_count
        self.reconstructionWindow = reconstruction_window
        self.gaussianMinY = gaussian_min_y
        self.gaussianMaxY = gaussian_max_y


# TODO: rename to CsvChunkData
class CsvData:
    file_name: str
    time_windows: List[float]
    y_on: List[int]
    y_off: List[int]
    y_all: List[int]

    def __init__(self, file_name: str, time_windows: List[float], y_on: List[int], y_off: List[int], y_all: List[int]):
        self.file_name = file_name
        self.time_windows = time_windows
        self.y_on = y_on
        self.y_off = y_off
        self.y_all = y_all


class DataStorage(Enum):
    BOOL = 1
    COLOR = 2
    BOOL_AND_COLOR = 3
    NONE = 4


class SpatialCsvData:
    def __init__(self, polarity_as_bool: bool, polarity_as_color: bool):
        self.polarities: List[bool] = []
        self.polarities_color: List[str] = []
        self.x_positions: List[int] = []
        self.y_positions: List[int] = []
        self.timestamps: List[int] = []

        self.__polarity_storage_callbacks: List[Callable[[bool], None]] = []

        if polarity_as_color:
            self.__polarity_storage_callbacks.append(self.__store_polarity_color)

        if polarity_as_bool:
            self.__polarity_storage_callbacks.append(self.__store_polarity_bool)

    def __store_polarity_bool(self, polarity: bool):
        self.polarities.append(polarity)

    def __store_polarity_color(self, polarity: bool):
        self.polarities_color.append("g" if polarity == 1 else "r")

    @staticmethod
    def from_csv(csv_file: str, data_storage: DataStorage, time_limit: int = sys.maxsize, skip_rows: int = 0):
        """Creates a SpatialCsvData object and appends data to it from a CSV file

        Parameters
        ----------
        csv_file : str
            CSV file containing data to be read into the created object
        data_storage : DataStorage
            How data should be stored in the created object
        time_limit : int, optional
            Legnth of data to be included in the created object (seconds), by default sys.maxsize
        skip_rows : int, optional
            Length of data to be skipped from the start of the CSV file, by default 0.
            Use to avoid data corruption that tends to occur at the beginning of a recording.

        Returns
        -------
        SpatialCsvData
            SpatialCsvData containing data from csv_file

        Raises
        ------
        ValueError
            Raised when the CSV file is of an incorrect format, as defined by the header
        ValueError
            Raised when the CSV file has a header but contains no data
        """
        first_timestamp = 0
        if time_limit != sys.maxsize:
            time_limit = int(time_limit * 1000000)  # Convert to microseconds

        polarity_as_bool = data_storage in [DataStorage.BOOL, DataStorage.BOOL_AND_COLOR]
        polarity_as_color = data_storage in [DataStorage.COLOR, DataStorage.BOOL_AND_COLOR]

        spatial_csv_data = SpatialCsvData(polarity_as_bool, polarity_as_color)

        with open(csv_file, "r") as csvfile:
            reader = csv.reader(csvfile, delimiter=",")
            header = next(reader, None)  # Grab header
            expected_header = ["On/Off", "X", "Y", "Timestamp"]

            # Make sure CSV is the correct format
            if header != expected_header:
                raise ValueError(f"Found header: {header}\nExpected: {expected_header}")

            # Skip N rows as specified by skip_rows
            [next(reader, None) for _ in range(skip_rows)]

            first_row = next(reader, None)

            if first_row is None:
                raise ValueError(f"CSV file '{csv_file}' seems to be empty")

            first_timestamp = int(first_row[3])

            # Determine if polarity is stored as True/False or 1/-1
            polarity_true = "True" if first_row[0] in ("True", "False") else "1"

            for row in itertools.chain([first_row], reader):
                timestamp = int(row[3]) - first_timestamp

                if timestamp > time_limit:
                    break

                polarity = row[0] == polarity_true
                x_pos = int(row[1])
                y_pos = 128 - int(row[2])

                spatial_csv_data.append_row(polarity, x_pos, y_pos, timestamp)

        return spatial_csv_data

    def append_row(self, polarity: bool, x: int, y: int, timestamp: int):
        self.x_positions.append(x)
        self.y_positions.append(y)
        self.timestamps.append(timestamp)

        for polarity_func in self.__polarity_storage_callbacks:
            polarity_func(polarity)


# TODO: indicate that this is for chunk CSVs
def read_aedat_csv(csv_path: str, timeWindow: int, maxSize: int = -1) -> CsvData:
    x: List[float] = []
    y_on: List[int] = []
    y_off: List[int] = []
    y_all: List[int] = []

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV file could not be found: {csv_path}")

    with open(csv_path, "r") as csvfile:
        reader = csv.reader(csvfile, delimiter=",")
        header = next(reader, None)  # Grab header

        if header is None:
            raise ValueError(f"CSV file '{csv_path}' seems to be empty")

        # Make sure CSV is the correct format
        for entry in header:
            if "count" not in entry.lower():
                raise ValueError(
                    "CSV may not be the correct format.\n"
                    "Header entries should indicate that the columns contain event counts"
                )

        for i, row in enumerate(reader):
            x.append((i - 1) * timeWindow * 0.000001)
            # TODO: If timewindow is large this will not work
            # also machineLearning Get data might need this fix for outliers
            if int(row[2]) > 8000:  # If camera bugs out and registers too many events, use like data instead
                y_on.append(sum(y_on) // len(y_on))
                y_off.append(sum(y_off) // len(y_off))
                y_all.append(sum(y_all) // len(y_all))
            else:
                y_on.append(int(row[0]))
                y_off.append(int(row[1]))
                y_all.append(int(row[2]))
            if i == maxSize:
                break

    return CsvData(csv_path, x, y_on, y_off, y_all)


def parseConfig(location: str = "plotting/config.json", data_folder=None) -> EventChunkConfig:
    config_json = json.loads(open(location).read())
    config = EventChunkConfig()
    for key in config_json:
        setattr(config, key, config_json[key])  # Assign all properties in json to config object

    # HACK
    if data_folder:
        setattr(config, "dataFolder", data_folder)

    return config
