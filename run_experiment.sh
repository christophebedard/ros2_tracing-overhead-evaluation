#!/usr/bin/env bash
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

# performance_test experiment and comparison for ros2_tracing
#
# This script runs a set of performance_test experiments for 2 different configurations:
#   1. no tracepoints at all (base)
#   2. tracing enabled (tracing)
# The set of experiments is made up of 1 experiment for each combination of message size and
# publishing frequency values, which means that each combination is used twice.
# See README for the full instructions.
# Notes:
#   * run with 'sudo' if using realtime mode (using '--use-rt-prio' or '--use-rt-cpus')
#     $ sudo chrt --fifo 99 ./run_experiment.sh
#     * when running with sudo, you may need to manually pass *PATH environment variables for shared libraries to be found
#       $ sudo env PATH="$PATH" LD_LIBRARY_PATH="$LD_LIBRARY_PATH" ./run_experiment.sh
#       * see https://unix.stackexchange.com/a/251374

# Configuration
declare -a c_freqs=("100" "500" "1000" "2000")
declare -a c_msgs=("1" "32" "64" "256")
# declare -a c_freqs=("500")
# declare -a c_msgs=("256")
c_max_runtime=1205
# c_max_runtime=15
c_ignore=5
c_comm="rclcpp-single-threaded-executor"
c_rmw_impl="rmw_cyclonedds_cpp"
c_params_file="experiment_params.log"

c_is_realtime=1
# c_is_realtime=0
# # Use 3rd and 4th CPUs
# cpu_0=2
# cpu_1=3


SCRIPT_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
base_path="${SCRIPT_DIR}"
base_ws="${base_path}/base_ws"
tracing_ws="${base_path}/tracing_ws"
cyclonedds_config_file="$PWD/cyclonedds.xml"
timestamp=`date +%Y%m%dT%H%M%S%z`
experiment_dir="exp-${timestamp}"


if [[ "${c_rmw_impl}" == "rmw_cyclonedds_cpp" ]]; then
  # Make sure the Cyclone DDS config exists and then set environment variable
  if [ ! -f ${cyclonedds_config_file} ]; then
    echo "Cyclone DDS config file not found: ${cyclonedds_config_file}"
    exit 1
  fi
  export CYCLONEDDS_URI=file://${cyclonedds_config_file}
fi
export RMW_IMPLEMENTATION="${c_rmw_impl}"

# Get root status
as_root=0
if [ "$EUID" -eq 0 ]; then
  as_root=1
fi

# Perform RT status/config checks
rt_run_options_p=""
rt_run_options_s=""
rmem_default="$(sysctl net.core.rmem_default -n)"
rmem_max="$(sysctl net.core.rmem_max -n)"
ondemand="$(systemctl is-enabled ondemand)"
if [ ${c_is_realtime} -eq 1 ]; then
  # Make sure SMT is disabled
  smt_active=$(cat /sys/devices/system/cpu/smt/active)
  if [[ "$smt_active" -eq 1 ]]; then
    echo "SMT is active!"
    echo "  Disable it by running:"
    echo "    sudo bash -c 'echo off > /sys/devices/system/cpu/smt/control'"
    echo "  Or by adding 'nosmt' to GRUB_CMDLINE_LINUX in /etc/default/grub, then running:"
    echo "    sudo update-grub && sudo reboot -h now"
    exit 1
  fi

  # Make sure CPUs are correctly isolated
  # Note: currently skipping this step, since the benchmark has many threads
  #       and isolating+pinning CPUs leads to bad performance
  # isolated_cpus=$(cat /sys/devices/system/cpu/isolated)
  # # This file uses a dash between the consecutive CPU numbers even if we used a comma in the grub config
  # if [[ "$isolated_cpus" != "$cpu_0-$cpu_1" ]]; then
  #   echo "CPUs ${cpu_0},${cpu_1} are not isolated!"
  #   echo "  Isolate them by adding 'isolcpus=${cpu_0},${cpu_1}' to GRUB_CMDLINE_LINUX in /etc/default/grub, then running:"
  #   echo "    sudo update-grub && sudo reboot -h now"
  #   exit 1
  # fi

  # Make sure the UDP socket buffer size was increased
  if [ "${rmem_default}" -lt "67108864" ] || [ "${rmem_max}" -lt "67108864" ]; then
    echo "Please increase UDP socket buffer size"
    echo "  By running:"
    echo "    sudo sysctl -w net.core.rmem_max=67108864"
    echo "    sudo sysctl -w net.core.rmem_default=67108864"
    echo "  Or by adding these lines to your /etc/sysctl.conf file and then rebooting:"
    echo "    net.core.rmem_max=67108864"
    echo "    net.core.rmem_default=67108864"
    exit 1
  fi

  # Make sure the ondemand performance governor is disabled
  if [[ "${ondemand}" == "enabled" ]]; then
    echo "ondemand performance governor enabled"
    echo "  Disable by running:"
    echo "    sudo systemctl disable ondemand"
    exit 1
  fi

  # Make sure there is no scaling governor (otherwise SpeedStep is not disabled)
  if [ -f "/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor" ]; then
    echo "Scaling not disable"
    echo "  See README"
    exit 1
  fi

  # Make sure the script is run as root
  if [ ${as_root} -ne 1 ]; then
    echo "Please run as root to use RT settings"
    echo "  sudo ./run_experiment.sh"
    echo "You may also need to manually pass *PATH environment variables, see: https://unix.stackexchange.com/a/251374"
    echo "  sudo env PATH="$PATH" LD_LIBRARY_PATH="$LD_LIBRARY_PATH" ./run_experiment.sh"
    exit 1
  fi
  
  # Masks:
  #   CPUs 0-1: 3
  #   CPUs 2-3: 12
  # Priority:
  #   highest RT priority: 99
  #     https://stackoverflow.com/a/52501811
  #     also: sudo chrt --fifo 99 ./perf_test.sh
  # rt_run_options_p="--use-rt-prio 99 --use-rt-cpus 3"
  # rt_run_options_s="--use-rt-prio 99 --use-rt-cpus 12"
  rt_run_options_p="--use-rt-prio 99"
  rt_run_options_s="--use-rt-prio 99"
fi

function print_params() {
  # Print params and write to file so that they are kept alongside the results
  local host=`hostname -s`
  local policy=`chrt -p $$`
  local cpu_freqs=`cat /proc/cpuinfo | awk '/cpu MHz/{print $4}' | awk 'ORS=", "' | sed 's/, $//'`
  local uname_a=`uname -a`
  local params="\
Params: ${experiment_dir}
frequencies     = ${c_freqs[@]}
messages        = ${c_msgs[@]}
max_runtime     = ${c_max_runtime}
ignore          = ${c_ignore}
perf_test comm  = ${c_comm}
rmw_impl        = ${c_rmw_impl}
is_realtime     = ${c_is_realtime}
base path       = ${base_path}
cyclonedds_uri  = ${CYCLONEDDS_URI}
cmd             = $0 $*
host            = ${host}
as_root         = ${as_root}
policy          = ${policy}
rt_run_options  = ${rt_run_options_p}, ${rt_run_options_s}
rmem_default    = ${rmem_default}
rmem_max        = ${rmem_max}
ondemand        = ${ondemand}
cpu_freqs       = ${cpu_freqs}
uname_a         = ${uname_a}
"
  echo -e "${params}"
  echo -e "${params}" > ${c_params_file}
  echo ""
  # Also include exact repo hashes
  echo "$(cd ${base_ws} && vcs export src/ --exact)" >> ${c_params_file}
  # Also include Cyclone DDS config file if applicable
  if [[ "${c_rmw_impl}" == "rmw_cyclonedds_cpp" ]]; then
    echo "$(cat ${cyclonedds_config_file})" >> ${c_params_file}
  fi
}

function run() {
  local exp_name=$1
  local msg=$2
  local freq=$3
  local do_trace=$4
  local perf_test_path=$5

  local msg_name="Array${msg}k"
  local logfile_name="${exp_name}_${msg_name}_${freq}hz"
  local logfile_name_pub="${logfile_name}_p"
  local logfile_name_sub="${logfile_name}_s"

  echo "log: ${logfile_name}"

  local session_name="${logfile_name}"
  if [[ "$do_trace" -eq 1 ]]; then
    # Setup and start tracing
    lttng create "${session_name}" --output="trace-${session_name}"
    lttng enable-channel -u ros2 --discard --num-subbuf=2 --subbuf-size=2M --buffers-pid --read-timer 200000 --monitor-timer 0
    lttng enable-event -c ros2 -u 'ros2:*'
    lttng start
  fi

  run_cmd_0="${perf_test_path} -c ${c_comm} -p 1 -s 0 -r ${freq} -m ${msg_name} --reliable --max-runtime ${c_max_runtime} --ignore ${c_ignore} -o json-raw --json-logfile ${logfile_name_pub} ${rt_run_options_p}"
  run_cmd_1="${perf_test_path} -c ${c_comm} -p 0 -s 1 -r ${freq} -m ${msg_name} --reliable --max-runtime ${c_max_runtime} --ignore ${c_ignore} -o json-raw --json-logfile ${logfile_name_sub} ${rt_run_options_s}"
  echo -e "  running:\n    ${run_cmd_0} &\n    ${run_cmd_1}"
  ${run_cmd_0} &
  pid_0=$!
  ${run_cmd_1} &
  pid_1=$!
  # taskset -a -pc ${cpu_0}-${cpu_1} ${pid_0}
  # taskset -a -pc ${cpu_0}-${cpu_1} ${pid_1}
  wait ${pid_0}
  wait ${pid_1}

  if [[ "$do_trace" -eq 1 ]]; then
    # Stop tracing
    lttng stop "${session_name}"
    lttng destroy
  fi
}

function run_single_exp() {
  local exp_num=$1
  local mode=$2
  local msg=$3
  local freq=$4

  local exp_name="${exp_num}-${mode}"

  local ws_path=""
  local do_trace=0
  if [[ "${mode}" == "trace" ]]; then
    do_trace=1
    ws_path="${tracing_ws}"
    echo "Mode: tracing"
  else
    ws_path="${base_ws}"
    echo "Mode: base, not tracing"
  fi

  local perf_test_path="${ws_path}/install/performance_test/lib/performance_test/perf_test"
  local source_path="${ws_path}/install/setup.bash"
  echo "perf_test: ${perf_test_path}"
  echo "Sourcing: ${source_path}"
  source "${source_path}"

  if [[ "${mode}" != "base" && "${mode}" != "trace" ]]; then
    echo "MODE: either 'base' or 'trace'"
    exit 1
  fi

  run ${exp_name} ${msg} ${freq} ${do_trace} ${perf_test_path}

  echo
}

function run_full_exp() {
  local exp_num=$1

  for m in "${c_msgs[@]}"
  do
    for f in "${c_freqs[@]}"
    do
      echo "msg=${m}, freq=${f}"
      echo
      run_single_exp ${exp_num} "base" ${m} ${f}
      run_single_exp ${exp_num} "trace" ${m} ${f}
      echo
    done
  done
}

mkdir ${experiment_dir}
cd ${experiment_dir}

print_params

run_full_exp 1
