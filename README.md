# `ros2_tracing` overhead evaluation

[`ros2_tracing`](https://gitlab.com/ros-tracing/ros2_tracing) latency overhead evaluation experiment.

This is part of the [`ros2_tracing` paper](https://arxiv.org/abs/2201.00393).
If you use or refer to `ros2_tracing` or this repository, please cite:
<!-- TODO replace with early access/published version when available -->
* C. Bédard, I. Lütkebohle, and M. Dagenais, "ros2_tracing: Multipurpose Low-Overhead Framework for Real-Time Tracing of ROS 2," *arXiv preprint arXiv:2201.00393*, 2022.

BibTeX:

```bibtex
@article{bedard2022ros2tracing,
  title={ros2\_tracing: Multipurpose Low-Overhead Framework for Real-Time Tracing of ROS 2},
  author={B{\'e}dard, Christophe and L{\"u}tkebohle, Ingo and Dagenais, Michel},
  journal={arXiv preprint arXiv:2201.00393},
  year={2022}
}
```

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
    * disable power-saving features
        * note: this assumes an Intel processor is used
        * BIOS
            * Performance > HyperThread Control: select disabled
            * Performance > C-States Control: deselect to disable
            * Performance > Intel SpeedStep: deselect to disable
            * note: the exact locations and names of these options might be different depending on your BIOS, but disabling any and all power-saving features significantly improves performance and lowers jitter
        * kernel
            * add following parameters (space-separated) to `GRUB_CMDLINE_LINUX` in `/etc/default/grub`
                * disable SMT: add `nosmt`
                * disbale C-states: add `processor.max_cstate=0 intel_idle.max_cstate=0`
            * then run:
                ```sh
                sudo update-grub && sudo reboot -h now
                ```
            * note: these might be redundant when setting BIOS parameters
1. Setup system to build ROS 2 and enable tracing
    * https://docs.ros.org/en/rolling/Installation/Ubuntu-Development-Setup.html
    * https://gitlab.com/ros-tracing/ros2_tracing
1. Setup code workspaces and build
    ```sh
    ./setup_workspace.sh
    ```
    * this creates two workspaces, one without tracing and one with tracing, and builds them in release mode
1. Run [performance_test](https://gitlab.com/ApexAI/performance_test) experiments using [`run_experiment.sh`](./run_experiment.sh)
    * modify the configuration if needed (`c_*` variables at the top of the file)
    * experiment data will be written to `exp-YYYYMMDDTHHMMSS-ABCD`
    ```sh
    ./run_experiment.sh
    ```
    * in general, results are better if the experiment is run right after a system reboot
    * experiment parameters are printed at the beginning and are written to `experiment_params.log` under the experiment directory
    * LTTng is [configured and optimized for real-time applications](https://gitlab.com/ros-tracing/ros2_tracing#real-time)
1. Plot results by providing name of directory containing the experiment data using [`plot_experiment.py`](./plot_experiment.py)
    * make sure the `freqs` & `msgs` arrays and `runtime_max` & `runtime_ignore` values match the ones defined in `run_experiment.sh` when running the experiment and written to `exp-YYYYMMDDTHHMMSS-ABCD/experiment_params.log`
    ```sh
    python3 plot_experiment.py exp-YYYYMMDDTHHMMSS-ABCD
    ```
    * see comments at the top of the file for dependencies
    * see other options at the top of the file to:
        * print out approximate frequencies (to confirm that the target pub/sub frequency is hit)
        * include titles in plot

## Useful commands

* For running experiments on a separate system
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
