# `ros2_tracing` paper experiment

`ros2_tracing` latency overhead experiment.

## Experiment

1. Setup real-time system
    * or set `c_is_realtime` to `0` in `run_experiment.sh`
1. Setup system to build ROS 2 and enable tracing
    * https://docs.ros.org/en/rolling/Installation/Ubuntu-Development-Setup.html
    * https://gitlab.com/ros-tracing/ros2_tracing
1. Setup code workspaces and build
    ```sh
    ./setup_workspace.sh
    ```
1. Run [performance_test](https://gitlab.com/ApexAI/performance_test) experiments using [`run_experiment.sh`](./run_experiment.sh)
    * modify the configuration if needed (`c_*` variables at the top of the file)
    * experiment data will be written to `exp-YYYYMMDDTHHMMSS-ABCD`
    ```sh
    ./run_experiment.sh
    ```
1. Plot results by providing name of directory containing the experiment data using [`plot_experiment.py`](./plot_experiment.py)
    * make sure the `freqs` and `msgs` arrays match the ones defined in `run_experiment.sh`
    ```sh
    python3 plot_experiment.py exp-YYYYMMDDTHHMMSS-ABCD
    ```
