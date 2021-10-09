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
import sys
from typing import List
from typing import Tuple

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

include_plot_title = False
# If True, a special branch of performance_test must have been used: christophebedard/raw-data
# Then we expect to be able to read the raw latency values
use_raw_latency_data = True


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


def compute_latency_mean(run_dataframe: pd.DataFrame) -> float:
    # return run_dataframe['latency_mean (ms)'].mean()
    # Weighted mean using number of received messages
    received = run_dataframe['received']
    latency_mean = run_dataframe['latency_mean (ms)']
    return (received * latency_mean).sum() / received.sum()


def compute_latency_mean_raw(run_dataframe: pd.DataFrame) -> float:
    # Latencies are in seconds, so convert to milliseconds
    return (1000 * run_dataframe['raw_latencies']).mean()


def get_latency_mean(run_file: str) -> float:
    if use_raw_latency_data:
        raw_latencies = load_logfile_raw(run_file)
        return compute_latency_mean_raw(raw_latencies)

    _, dataframe = load_logfile(run_file)
    return compute_latency_mean(dataframe)


def plot_mode(mode: str) -> None:
    fig, ax = plt.subplots(1, 1)

    legends = []
    for msg in msgs:
        msg_freqs = []
        msg_latency_means = []
        for freq in freqs:
            # print(f'{mode}: {msg}k, {freq} Hz')
            run_file = get_run_file(mode, msg, freq)
            latency_mean = get_latency_mean(run_file)
            # print(f'\t{latency_mean}')
            msg_freqs.append(freq)
            msg_latency_means.append(latency_mean)
        ax.plot(msg_freqs, msg_latency_means, 'D-')
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


def plot_diff_mode() -> None:
    fig, ax = plt.subplots(1, 1)

    legends = []
    for msg in msgs:
        msg_freqs = []
        msg_latency_means_diff = []
        for freq in freqs:
            run_file_base = get_run_file('base', msg, freq)
            latency_mean_base = get_latency_mean(run_file_base)

            run_file_trace = get_run_file('trace', msg, freq)
            latency_mean_trace = get_latency_mean(run_file_trace)

            msg_freqs.append(freq)
            msg_latency_means_diff.append(latency_mean_trace - latency_mean_base)
        ax.plot(msg_freqs, msg_latency_means_diff, 'D-')
        legends.append(f'{msg} KB')

    # xticks = {0}
    # xticks.update(set(msg_freqs).difference({10}))
    # xticks = sorted(list(xticks))
    xticks = [0, 500, 1000, 1500, 2000]

    if include_plot_title:
        ax.set(title='Latency overhead of tracing for message publication')
    ax.set(xlabel='publishing frequency (Hz)')
    ax.set(ylabel='mean latency overhead (ms)')
    ax.set(xticks=xticks, xlim=(min(xticks)-25, max(xticks)+50))
    ax.legend(legends)
    ax.grid()
    fig.tight_layout()

    filename = f'./{experiment_dir}/figure_2'
    fig.savefig(f'{filename}.png')
    fig.savefig(f'{filename}.svg')


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
