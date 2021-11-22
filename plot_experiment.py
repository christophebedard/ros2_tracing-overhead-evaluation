#!/usr/bin/env python3
# Copyright 2021 Christophe Bedard
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Helper script to plot the results of an experiment run with the run_experiment.sh script."""

import glob
import json
import math
import sys
from typing import List
from typing import Tuple

# Install apex_performance_plotter:
#   cd base_ws/src/performance_test/performance_test/helper_scripts/apex_performance_plotter
#   pip3 install .
from apex_performance_plotter.load_logfiles import load_logfile

# matplotlib>=3.4 is required for suptitle() and supxlabel()
import matplotlib.pyplot as plt

import pandas as pd


# Set experiment parameters
freqs = [100, 500, 1000, 2000]
msgs = [1, 32, 64, 256]
runtime_max = 60*60 + 10
runtime_ignore = 10

# If True, a special branch of performance_test must have been used: christophebedard/raw-data
# From: https://gitlab.com/christophebedard/performance_test
# Then we expect to be able to read the raw latency values
has_raw_latency_data = True
# Whether to include titles above plots
include_plot_title = False
# Whether to print out approximate frequencies to confirm that the target pub/sub frequency is hit
print_approximate_frequencies = True


experiment_dir = None


def get_frequency_ticks(
    freq_min: int = 0,
    freq_max: int = max(freqs),
    freq_step: int = 500,
) -> List[int]:
    """
    Get frequency ticks for plotting.

    :param freq_min: the min frequency
    :param freq_max: the max frequency (inclusive)
    :param freq_step: the tick step
    :return: the list of ticks
    """
    return list(range(freq_min, freq_max + freq_step, freq_step))


def load_logfile_raw(filename: str) -> pd.DataFrame:
    """
    Load JSON logfile containing raw latency values.

    Expects a simple JSON object that has a 'raw_latencies' key with an array of doubles
    representing latencies of every single received sample.

    :param filename: the file name
    :return: the raw latencies
    """
    assert has_raw_latency_data
    with open(filename) as f:
        d = json.load(f)
        return pd.DataFrame.from_dict({'raw_latencies': d['raw_latencies']})


def get_file_from_prefix(prefix: str) -> str:
    """
    Get existing file path corresponding to file name prefix.

    :param prefix: the file name prefix
    :return: the file path
    """
    exp_dir_prefix = f'./{experiment_dir}/{prefix}'
    matching_files = set(glob.glob(f'{exp_dir_prefix}')) - set(glob.glob(f'{exp_dir_prefix}*.pdf'))
    matching_files = list(matching_files)
    assert len(matching_files) == 1, \
        f'for {exp_dir_prefix}: len(matching_files) == {len(matching_files)}: {matching_files}'
    return matching_files[0]


def get_experiment_run_name(
    mode: str,
    msg: int,
    freq: int,
) -> str:
    """
    Get name of data file for a specific run.

    :param mode: the mode
    :param msg: the msg size
    :param freq: the publishing frequency
    :return: the file name for that specific run
    """
    assert mode in ('base', 'trace')
    # use '_s' suffix file because that's the one that contains the latency data (subscriber)
    return f'1-{mode}_Array{msg}k_{freq}hz_s'


def get_run_file(
    mode: str,
    msg: int,
    freq: int,
) -> str:
    """
    Get path to data file for a specific run.

    :param mode: the mode
    :param msg: the msg size
    :param freq: the publishing frequency
    :return: the path to the file for that specific run
    """
    assert mode in ('base', 'trace')
    name = get_experiment_run_name(mode, msg, freq)
    return get_file_from_prefix(name)


def get_experiment_runs() -> List[Tuple[int, int]]:
    """Get list of (msg size, frequency) combinations."""
    runs = []
    for msg in msgs:
        for freq in freqs:
            runs.append((msg, freq))
    return runs


def get_latency_data(run_file: str) -> float:
    """
    Get latency data.

    This is the default version, which gives a mean value.

    :param run_file: the data file
    :return: latency mean
    """
    _, dataframe = load_logfile(run_file)
    # Weighted mean using number of received messages
    # Not great, but we don't have the raw data
    received = dataframe['received']
    latency_mean = dataframe['latency_mean (ms)']
    return (received * latency_mean).sum() / received.sum()


def get_latency_data_raw(run_file: str) -> Tuple[float, float, pd.Series]:
    """
    Get latency data.

    This is the raw version, which gives  mean value.

    :param run_file: the data file
    :return: latency mean, standard deviation, raw latency values
    """
    assert has_raw_latency_data
    dataframe = load_logfile_raw(run_file)
    # Raw latencies are in seconds, so convert to milliseconds
    raw_latencies = 1000 * dataframe['raw_latencies']
    return raw_latencies.mean(), raw_latencies.std(), raw_latencies


def get_approximate_frequency(
    raw_latencies: pd.Series,
) -> float:
    """
    Get approximate pub/sub frequency.

    :param raw_latencies: the raw latency values
    :return: the approximate frequency
    """
    # Each individual experiment is run for runtime_max seconds, but the first runtime_ignore
    # seconds are ignored and we don't get latency values for those, so subtract it from the total
    total_runtime = runtime_max - runtime_ignore
    num_latencies = raw_latencies.size
    # frequency [Hz] = number of messages / total time [s]
    return float(num_latencies) / float(total_runtime)


def plot_mode(
    ax,
    mode: str,
) -> None:
    """
    Plot a given mode.

    :param ax: the axis to use for plotting
    :param mode: the mode ('base' or 'trace')
    """
    assert mode in ('base', 'trace')
    for msg in msgs:
        msg_freqs = []
        msg_latencies = []
        msg_latencies_stdev = []
        for freq in freqs:
            run_file = get_run_file(mode, msg, freq)

            latency_mean = None
            if has_raw_latency_data:
                latency_mean, latency_stdev, latencies_raw = get_latency_data_raw(run_file)
                msg_latencies_stdev.append(latency_stdev)
                if print_approximate_frequencies:
                    approx_freq = get_approximate_frequency(latencies_raw)
                    print(f'{mode:<5}: {msg:>3}, {freq:>4} Hz: ~ {approx_freq:>7.2f} Hz')
            else:
                latency_mean = get_latency_data(run_file)

            msg_latencies.append(latency_mean)
            msg_freqs.append(freq)

        label = f'{msg} KB'
        if has_raw_latency_data:
            ax.errorbar(
                msg_freqs, msg_latencies,
                yerr=msg_latencies_stdev,
                capsize=5, fmt='D-', label=label)
        else:
            ax.plot(msg_freqs, msg_latencies, 'D-', label=label)

    xticks = get_frequency_ticks()
    ax.set(xticks=xticks, xlim=(min(xticks), max(xticks)+75))
    ax.grid()


def plot_modes(
    title: str = 'Message latencies without (left) vs. with tracing (right)',
    xlabel: str = 'publishing frequency (Hz)',
    ylabel: str = 'mean latency (ms)',
    figure_filename: str = '6_results_latencies',
    legend_fontsize: int = 12,
) -> None:
    """
    Plot baseline and tracing latency results separately.

    :param title: plot title
    :param xlabel: x axis label
    :param ylabel: y axis label
    :param figure_filename: base file name for the figure (without file extension)
    :param legend_fontsize: the legend font size;
        a lower value than the default can help make it fit better into the plot
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, sharey=True, constrained_layout=True)

    plot_mode(ax1, 'base')
    plot_mode(ax2, 'trace')

    if include_plot_title:
        fig.suptitle(title, size=plt.rcParams['axes.titlesize'])
    fig.supxlabel(xlabel, size=plt.rcParams['font.size'])
    ax1.set(ylabel=ylabel)
    ax2.legend(fontsize=legend_fontsize)

    filename = f'./{experiment_dir}/{figure_filename}'
    fig.savefig(f'{filename}.png')
    fig.savefig(f'{filename}.svg')


def plot_diff_mode(
    same_plot: bool = True,
    title: str = 'Latency overhead of tracing for message publication',
    xlabel: str = 'publishing frequency (Hz)',
    ylabel_abs: str = 'mean latency overhead (ms)',
    ylabel_per: str = 'mean latency overhead (\%)',  # noqa: W605 (escape necessary for TeX)
    figure_filename: str = '6_results_overhead',
    legend_fontsize: int = 12,
) -> None:
    """
    Compute latency overhead and plot results.

    :param same_plot: whether to plot absolute and relative values (ms, %) in the same plot
    :param title: plot title
    :param xlabel: x axis label
    :param ylabel_abs: y axis label for the (sub)plot with absolute values
    :param ylabel_per: y axis label for the (sub)plot with relative values
    :param figure_filename: base file name for the figure (without file extension)
    :param legend_fontsize: the legend font size;
        a lower value than the default can help make it fit better into the plot
    """
    if same_plot:
        fig, (ax, ax2) = plt.subplots(1, 2, constrained_layout=True)
    else:
        fig, ax = plt.subplots(1, 1)
        fig2, ax2 = plt.subplots(1, 1)

    for msg in msgs:
        msg_freqs = []
        msg_latency_diff = []
        # msg_latency_diff_stdev = []
        msg_latency_diff_percent = []
        for freq in freqs:
            # print(f'{msg} KB, {freq} Hz')
            run_file_base = get_run_file('base', msg, freq)
            run_file_trace = get_run_file('trace', msg, freq)

            latency_mean_base = None
            latency_mean_trace = None
            if has_raw_latency_data:
                latency_mean_base, latency_stdev_base, raw_latencies_base = get_latency_data_raw(run_file_base)
                latency_mean_trace, latency_stdev_trace, raw_latencies_trace = get_latency_data_raw(run_file_trace)
                # Standard deviation of the difference between the two means
                # is too small (mostly by definition) to be significant
                if False:
                    # Compute standard deviation of the difference between the two means
                    # given the two standard deviations and sample size
                    #   SD_diff = sqrt((SD_base^2 / N_base) + (SD_trace^2 / N_trace))
                    # See: https://stats.stackexchange.com/a/87505
                    print('base size:', raw_latencies_base.size)
                    print('trace size:', raw_latencies_trace.size)
                    latency_diff_stdev = math.sqrt(
                        (math.pow(latency_stdev_base, 2) / float(raw_latencies_base.size)) +
                        (math.pow(latency_stdev_trace, 2) / float(raw_latencies_trace.size))
                    )
                    print('base stdev:', latency_stdev_base)
                    print('trace stdev:', latency_stdev_trace)
                    print('diff stdev:', latency_diff_stdev)
                    print()
                    msg_latency_diff_stdev.append(latency_diff_stdev)
            else:
                latency_mean_base = get_latency_data(run_file_base)
                latency_mean_trace = get_latency_data(run_file_trace)

            def overhead(latency_base: float, latency_trace: float) -> float:
                return 100.0 * (latency_trace - latency_base) / latency_base
            msg_latency_diff_percent.append(overhead(latency_mean_base, latency_mean_trace))
            latency_mean_diff = latency_mean_trace - latency_mean_base
            msg_latency_diff.append(latency_mean_diff)
            msg_freqs.append(freq)

        legend_label = f'{msg} KB'
        if has_raw_latency_data:
            # ax.errorbar(msg_freqs, msg_latency_diff, yerr=msg_latency_diff_stdev, capsize=5, fmt='-')
            ax.plot(msg_freqs, msg_latency_diff, 'o-', label=legend_label)
            ax2.plot(msg_freqs, msg_latency_diff_percent, 'o-', label=legend_label)
        else:
            ax.plot(msg_freqs, msg_latency_diff, 'D-', label=legend_label)

    if include_plot_title:
        if same_plot:
            fig.suptitle(title, size=plt.rcParams['axes.titlesize'])
        else:
            ax.set(title=title)
            ax2.set(title=title)
    ax.set(ylabel=ylabel_abs)
    ax2.set(ylabel=ylabel_per)
    xticks = get_frequency_ticks()
    for axis in (ax, ax2):
        axis.set(xticks=xticks, xlim=(min(xticks), max(xticks)+75))
    ax.grid()
    ax2.grid()
    if same_plot:
        ax2.yaxis.set_label_position('right')
        ax2.yaxis.tick_right()
        ax2.legend(fontsize=legend_fontsize)
        fig.supxlabel(xlabel, size=plt.rcParams['font.size'])
    else:
        ax.set(xlabel=xlabel)
        ax2.set(xlabel=xlabel)
        ax.legend(fontsize=legend_fontsize)
        fig.tight_layout()
        fig2.tight_layout()

    filename = f'./{experiment_dir}/{figure_filename}'
    if same_plot:
        fig.savefig(f'{filename}.png')
        fig.savefig(f'{filename}.svg')
    else:
        fig.savefig(f'{filename}_abs.png')
        fig.savefig(f'{filename}_abs.svg')
        fig2.savefig(f'{filename}_per.png')
        fig2.savefig(f'{filename}_per.svg')


def main(argv=sys.argv[1:]) -> int:
    """Plot experiment results for given experiment."""
    if len(argv) != 1:
        print('error: must provide only 1 argument: name of directory containing experiment data')
        return 1
    global experiment_dir
    experiment_dir = argv[0].strip('/')
    print(f'Experiment directory: {experiment_dir}')
    print(f'  frequencies    = {", ".join(str(f) for f in freqs)}')
    print(f'  messages       = {", ".join(str(m) for m in msgs)}')
    print(f'  runtime_max    = {runtime_max}')
    print(f'  runtime_ignore = {runtime_ignore}')

    plt.rc('text', usetex=True)
    plt.rc('font', family='serif', size=14)
    plt.rc('axes', titlesize=20)

    plot_modes()
    plot_diff_mode()
    plt.show()

    return 0


if __name__ == '__main__':
    sys.exit(main())
