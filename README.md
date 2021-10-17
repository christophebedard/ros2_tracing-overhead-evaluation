# `ros2_tracing` paper experiment

`ros2_tracing` latency overhead experiment.

## Experiment

1. Set up and tune real-time system
    * (or set `c_is_realtime` to `0` in `run_experiment.sh`)
    * to build & set up a real-time kernel, see:
        * https://stackoverflow.com/a/51709420
        * https://github.com/ros-realtime/rt-kernel-docker-builder
    * increase UDP socket buffers from 25 MB (default) to 64 MB
        * by running:
        ```sh
        sudo sysctl -w net.core.rmem_max=67108864
        sudo sysctl -w net.core.rmem_default=67108864
        ```
        * or by adding these lines to your `/etc/sysctl.conf` file and then rebooting:
        ```sh
        net.core.rmem_max=67108864
        net.core.rmem_default=67108864
        ```
    * disable SMT
        * by adding `nosmt` to `GRUB_CMDLINE_LINUX` in /etc/default/grub, then running:
        ```sh
        sudo update-grub && sudo reboot -h now
        ```
        * or by running:
        ```sh
        sudo bash -c 'echo off > /sys/devices/system/cpu/smt/control'
        ```
    * disable performance governor
        ```sh
        sudo systemctl disable ondemand
        ```
    * set scaling governor to `performance`
        ```sh
        echo performance | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor >/dev/null
        ```
    * set constant CPU frequency by setting min frequency to max frequency
        * get max CPU frequency by running:
        ```sh
        cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_max_freq
        ```
        * then set set min CPU frequency to that value by running:
        ```sh
        echo $MAX_FREQ | sudo tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_min_freq > /dev/null
        ```
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
    * in general, results are better if the experiment is run right after a system reboot
1. Plot results by providing name of directory containing the experiment data using [`plot_experiment.py`](./plot_experiment.py)
    * make sure the `freqs` and `msgs` arrays match the ones defined in `run_experiment.sh`
    ```sh
    python3 plot_experiment.py exp-YYYYMMDDTHHMMSS-ABCD
    ```

## Useful commands

* For running experiments on a separate real-time system
    * Change ownership of directories/file from `root` to user
        ```sh
        sudo chown -R $USER:$USER exp-*
        ```
    * Copy experiment directories from remote to local
        ```sh
        scp -P $PORT -r $USER@server:/home/$USER/ros2_tracing_paper_experiment/exp-* .
        ```

## References

* tuning UDP buffer size and Cyclone DDS
    * https://github.com/ros2/rmw_cyclonedds/issues/346#issuecomment-944346030
    * https://discourse.ros.org/t/ros2-speed/20162/21
