import os
import yaml
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    OpaqueFunction,
    RegisterEventHandler,
)
from launch.event_handlers import OnShutdown
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def launch_setup(context, *args, **kwargs):
    config_path = LaunchConfiguration('camera_config_file').perform(context)

    # Resolve relative filename against package's share config directory
    if not os.path.isabs(config_path):
        config_path = os.path.join(
            get_package_share_directory('camera_bringup'),
            'config',
            config_path
        )

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Camera YAML file not found at: {config_path}")

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    rs_launch_path = os.path.join(
        get_package_share_directory('realsense2_camera'),
        'launch',
        'rs_launch.py'
    )

    launch_nodes = []

    for cam in config.get('cameras', []):
        arm = cam.get('arm')
        cam_id = cam.get('id')

        # Combine arm and id into a unique namespace/camera_name
        if arm and str(arm).lower() not in ('none', 'null'):
            camera_name = f"{arm}_{cam_id}"
        else:
            camera_name = str(cam_id)

        hardware_id = str(cam.get('hardware_id'))
        serial_no = f"_{hardware_id}" if not hardware_id.startswith('_') else hardware_id

        fps = str(cam.get('fps', 30))
        depth = 'true' if cam.get('depth', True) else 'false'

        launch_args = {
            'camera_name': camera_name,
            'serial_no': serial_no,
            'enable_depth': depth,
            # 'initial_reset': 'true',
            'depth_module.profile': f"0x0x{fps}",
            'rgb_camera.profile': f"0x0x{fps}",
        }

        camera_instance = IncludeLaunchDescription(
            PythonLaunchDescriptionSource(rs_launch_path),
            launch_arguments=launch_args.items()
        )

        launch_nodes.append(camera_instance)

    # Automatically kill all realsense nodes on Ctrl+C to prevent hanging C++ hardware threads
    shutdown_handler = RegisterEventHandler(
        OnShutdown(
            on_shutdown=[
                ExecuteProcess(
                    cmd=['pkill', '-9', '-f', 'realsense2_camera_node'],
                    output='screen'
                )
            ]
        )
    )
    launch_nodes.append(shutdown_handler)

    return launch_nodes


def generate_launch_description():
    pkg_share_config = os.path.join(
        get_package_share_directory('camera_bringup'),
        'config',
        'cameras.yaml'
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'camera_config_file',
            default_value=pkg_share_config,
            description='Path or filename of the camera YAML configuration file in camera_bringup/config'
        ),
        OpaqueFunction(function=launch_setup)
    ])