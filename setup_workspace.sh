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

# Workspace setup script for ros2_tracing performance_test comparison experiment
#
# See README for the full instructions.

base_ws="base_ws"
tracing_ws="tracing_ws"

# base
mkdir -p ${base_ws}/src
cd ${base_ws}
vcs import src --input https://raw.githubusercontent.com/ros2/ros2/master/ros2.repos
cd src/
git clone https://gitlab.com/christophebedard/performance_test.git --branch christophebedard/raw-data
cd ../
colcon build --packages-up-to performance_test --mixin release --cmake-args -DPERFORMANCE_TEST_RCLCPP_ENABLED=ON -DTRACETOOLS_DISABLED=ON

cd ../

# tracing
mkdir -p ${tracing_ws}/src
cd ${tracing_ws}
vcs import src --input https://raw.githubusercontent.com/ros2/ros2/master/ros2.repos
cd src/
git clone https://gitlab.com/christophebedard/performance_test.git --branch christophebedard/raw-data
cd ../
colcon build --packages-up-to performance_test --mixin release --cmake-args -DPERFORMANCE_TEST_RCLCPP_ENABLED=ON

cd ../
