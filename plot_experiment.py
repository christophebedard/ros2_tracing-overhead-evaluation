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

"""Helper script to plot the results of an experiment."""

import glob
import json
import math
import sys
from typing import List
from typing import Tuple
from typing import Union

# Install apex_performance_plotter:
#   cd base_ws/src/performance_test/performance_test/helper_scripts/apex_performance_plotter
#   pip3 install .
from apex_performance_plotter.load_logfiles import load_logfile

import matplotlib.pyplot as plt

import pandas as pd


freqs = [100, 500, 1000, 2000]
msgs = [1, 32, 64, 256]
# freqs = [500]
# msgs = [256]

include_plot_title = True
# If True, a special branch of performance_test must have been used: christophebedard/raw-data
# Then we expect to be able to read the raw latency values
has_raw_latency_data = True


experiment_dir = None


def load_logfile_raw(filename: str) -> pd.DataFrame:
    """
    Load JSON logfile containing raw latency values.

    Expects a simple JSON object that has a 'raw_latencies' key with an array of doubles
    representing latencies of every single received sample.
    """
    with open(filename) as f:
        d = json.load(f)
        return pd.DataFrame.from_dict({'raw_latencies': d['raw_latencies']})


def get_file_from_prefix(prefix: str) -> str:
    # global experiment_dir
    exp_dir_prefix = f'./{experiment_dir}/{prefix}'
    matching_files = set(glob.glob(f'{exp_dir_prefix}')) - set(glob.glob(f'{exp_dir_prefix}*.pdf'))
    matching_files = list(matching_files)
    assert len(matching_files) == 1, \
        f'for {exp_dir_prefix}: len(matching_files) == {len(matching_files)}: {matching_files}'
    return matching_files[0]


def get_experiment_run_name(mode: str, msg: int, freq: int) -> str:
    # use '_s' suffix file because that's the one that contains the latency data (subscriber)
    return f'1-{mode}_Array{msg}k_{freq}hz_s'


def get_run_file(mode: str, msg: int, freq: int) -> str:
    name = get_experiment_run_name(mode, msg, freq)
    return get_file_from_prefix(name)


def get_experiment_runs() -> List[Tuple[int, int]]:
    runs = []
    for msg in msgs:
        for freq in freqs:
            runs.append((msg, freq))
    return runs


def get_latency_data(run_file: str) -> Union[float, Tuple[float, float, pd.Series]]:
    if has_raw_latency_data:
        dataframe = load_logfile_raw(run_file)
        # Raw latencies are in seconds, so convert to milliseconds
        raw_latencies = 1000 * dataframe['raw_latencies']
        return raw_latencies.mean(), raw_latencies.std(), raw_latencies
    else:
        _, dataframe = load_logfile(run_file)
        # Weighted mean using number of received messages because we don't have the raw data
        received = dataframe['received']
        latency_mean = dataframe['latency_mean (ms)']
        return (received * latency_mean).sum() / received.sum()


def plot_mode(mode: str) -> None:
    fig, ax = plt.subplots(1, 1)

    legends = []
    for msg in msgs:
        msg_freqs = []
        msg_latencies = []
        msg_latencies_stdev = []
        for freq in freqs:
            run_file = get_run_file(mode, msg, freq)

            latency_mean = None
            if has_raw_latency_data:
                latency_mean, latency_stdev, _ = get_latency_data(run_file)
                msg_latencies_stdev.append(latency_stdev)
            else:
                latency_mean = get_latency_data(run_file)

            msg_latencies.append(latency_mean)
            msg_freqs.append(freq)

        if has_raw_latency_data:
            ax.errorbar(msg_freqs, msg_latencies, yerr=msg_latencies_stdev, capsize=5, fmt='D-')
        else:
            ax.plot(msg_freqs, msg_latencies, 'D-')
        legends.append(f'{msg} KB')

    # xticks = {0}
    # xticks.update(set(msg_freqs).difference({10}))
    # xticks = sorted(list(xticks))
    xticks = [0, 500, 1000, 1500, 2000]

    title = {
        'base': 'Reference message latencies (no tracing)',
        'trace': 'Message latencies with tracing',
    }[mode]
    if include_plot_title:
        ax.set(title=title)
    ax.set(xlabel='publishing frequency (Hz)')
    ax.set(ylabel='mean latency (ms)')
    ax.set(xticks=xticks, xlim=(min(xticks)-25, max(xticks)+50))
    ax.legend(legends)
    ax.grid()
    fig.tight_layout()

    filename = f'./{experiment_dir}/figure_1-{mode}'
    fig.savefig(f'{filename}.png')
    fig.savefig(f'{filename}.svg')


def compute_percent_yerr(func, base: float, base_std: float, trace: float, trace_std: float) -> Tuple[float, float]:
    func_results = []
    func_results.append(func(base + base_std, trace + trace_std))
    func_results.append(func(base - base_std, trace + trace_std))
    func_results.append(func(base + base_std, trace - trace_std))
    func_results.append(func(base - base_std, trace - trace_std))
    result_min = min(func_results)
    result_max = max(func_results)
    return base - result_min, result_max - base

def plot_diff_mode() -> None:
    same_plot = False
    if same_plot:
        fig, ax = plt.subplots(1, 1)
        ax2 = ax.twinx()
    else:
        fig, ax = plt.subplots(1, 1)
        fig2, ax2 = plt.subplots(1, 1)

    for msg in msgs:
        msg_freqs = []
        msg_latency_diff = []
        # msg_latency_diff_stdev = []
        msg_latency_diff_percent = []
        # msg_latency_diff_percent_stdev = [[], []]
        for freq in freqs:
            # print(f'{msg} KB, {freq} Hz')
            run_file_base = get_run_file('base', msg, freq)
            run_file_trace = get_run_file('trace', msg, freq)

            latency_mean_base = None
            latency_mean_trace = None
            if has_raw_latency_data:
                latency_mean_base, latency_stdev_base, raw_latencies_base = get_latency_data(run_file_base)
                latency_mean_trace, latency_stdev_trace, raw_latencies_trace = get_latency_data(run_file_trace)
                # # Compute standard deviation of the difference between the two means
                # # given the two standard deviations and sample size
                # #   SD_diff = sqrt((SD_base^2 / N_base) + (SD_trace^2 / N_trace))
                # # See: https://stats.stackexchange.com/a/87505
                # print('base size:', raw_latencies_base.size)
                # print('trace size:', raw_latencies_trace.size)
                # latency_diff_stdev = math.sqrt(
                #     (math.pow(latency_stdev_base, 2) / float(raw_latencies_base.size)) +
                #     (math.pow(latency_stdev_trace, 2) / float(raw_latencies_trace.size))
                # )
                # print('base stdev:', latency_stdev_base)
                # print('trace stdev:', latency_stdev_trace)
                # print('diff stdev:', latency_diff_stdev)
                # print()
                # msg_latency_diff_stdev.append(latency_diff_stdev)
            else:
                latency_mean_base = get_latency_data(run_file_base)
                latency_mean_trace = get_latency_data(run_file_trace)

            def overhead(latency_base: float, latency_trace: float) -> float:
                return 100.0 * (latency_trace - latency_base) / latency_base
            msg_latency_diff_percent.append(overhead(latency_mean_base, latency_mean_trace))
            latency_mean_diff = latency_mean_trace - latency_mean_base
            msg_latency_diff.append(latency_mean_diff)
            msg_freqs.append(freq)

            # yerr_percent_minus, yerr_percent_plus = compute_percent_yerr(overhead, latency_mean_base, latency_stdev_base, latency_mean_trace, latency_stdev_trace)
            # print(yerr_percent_minus, yerr_percent_plus)
            # print()
            # msg_latency_diff_percent_stdev[0].append(yerr_percent_minus)
            # msg_latency_diff_percent_stdev[1].append(yerr_percent_plus)

        legend_label = f'{msg} KB'
        if has_raw_latency_data:
            # ax.errorbar(msg_freqs, msg_latency_diff, yerr=msg_latency_diff_stdev, capsize=5, fmt='-')
            ax.plot(msg_freqs, msg_latency_diff, 'o-', label=legend_label)
            # ax2.errorbar(msg_freqs, msg_latency_diff_percent, yerr=msg_latency_diff_percent_stdev, capsize=5, fmt='P--')
            ax2.plot(msg_freqs, msg_latency_diff_percent, 'o-', label=legend_label)
            # legends.append(f'{msg} KB')
        else:
            ax.plot(msg_freqs, msg_latency_diff, 'D-', label=legend_label)

    # xticks = {0}
    # xticks.update(set(msg_freqs).difference({10}))
    # xticks = sorted(list(xticks))
    xticks = [0, 500, 1000, 1500, 2000]

    if include_plot_title:
        ax.set(title='Latency overhead of tracing for message publication')
        if not same_plot:
            ax2.set(title='Latency overhead of tracing for message publication')
    ax.set(xlabel='publishing frequency (Hz)')
    ax.set(ylabel='mean latency overhead (ms)')
    ax.set(xticks=xticks, xlim=(min(xticks)-25, max(xticks)+50))
    ax.legend(fontsize=12)
    ax.grid()
    fig.tight_layout()
    if same_plot:
        ax2.set(ylabel='mean latency overhead (\%)')
    else:
        ax2.set(xlabel='publishing frequency (Hz)')
        ax2.set(ylabel='mean latency overhead (\%)')
        ax2.set(xticks=xticks, xlim=(min(xticks)-25, max(xticks)+50))
        ax2.legend(fontsize=12)
        ax2.grid()
        fig2.tight_layout()

    filename = f'./{experiment_dir}/figure_2'
    if same_plot:
        fig.savefig(f'{filename}.png')
        fig.savefig(f'{filename}.svg')
    else:
        fig.savefig(f'{filename}_abs.png')
        fig.savefig(f'{filename}_abs.svg')
        fig2.savefig(f'{filename}_per.png')
        fig2.savefig(f'{filename}_per.svg')


def main(argv=sys.argv[1:]) -> int:
    if len(argv) != 1:
        print('error: must provide name of directory containing experiment data')
        return 1
    global experiment_dir
    experiment_dir = argv[0].strip('/')
    print(f'Experiment directory: {experiment_dir}')
    print(f'  frequencies = {", ".join(str(f) for f in freqs)}')
    print(f'  messages    = {", ".join(str(m) for m in msgs)}')

    plt.rc('text', usetex=True)
    plt.rc('font', family='serif', size=14)
    plt.rc('axes', titlesize=20)

    plot_mode('base')
    plot_mode('trace')

    plot_diff_mode()

    plt.show()

    return 0


if __name__ == '__main__':
    sys.exit(main())
