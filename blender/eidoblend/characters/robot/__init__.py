"""eidoblend.characters.robot: my robot body (claude_robot.vrm) in Blender: its runtime, the example scene, the embodied
robot that senses, remembers, plans and walks, and its hands (tools-guides/robot-body.md, tools-guides/navigation.md).

    from eidoblend.characters.robot import RobotRig, perform_robot, claude_robot_example
    from eidoblend.characters.robot import VRMRobotBody, EidoverseRobotController, RobotDebug
    from eidoblend.characters.robot import hands

Modules:
    rig         RobotRig (the DOF records made at load; frame(): examples/claude_robot.js's frame order on one pose;
                rest_feet: both feet on the floor), perform_robot (that order over a clip, keyed), key_robot (every
                bone and stage in one action)
    example     claude_robot_example: eidoverse/examples/claude_robot.js, the whole scene
    controller  EidoverseRobotController (robot_controller.js: the waypoint contract over the legs), RobotLegs (the
                legs it drives at build time: a kinematic walker that turns on the spot, and the moves (vault, jump,
                climb_ledge, climb_ladder) played by the controller family's VRMCharacterController), CollisionWorld
                (the JS's colliders: a box per mesh, or its triangles), build_route
    bake        the legs' record keyed: walks through round one's walk_path, runs and moves through the controller
                family's VRMCharacterController, standing clips through the frame order, turns stepped on the spot
    body        VRMRobotBody (robot_body.js: sensing, memory, A*, the embodied action API, the head's gaze; wait and
                until for scripts), Pending. It drives any VRM, as the JS does: on a VRM that is not my body RobotRig
                is a plain rig (the clips as they are, the gaze on the head bone, no hardware passes)
    debug       RobotDebug (robot_debug.js: the sensor rays, the map, the path and the landmarks as keyed geometry)
    hands       reaching on my arm's hardware, grasping with the fingers' and the thumb's real pins, holding,
                carrying, setting down to contact, letting go (my hands' work)
The sensors, the memory and the planner are eidoblend.harness.navigation (RobotSensors, RobotMemory, RobotPlanner).
"""

from .rig import RobotRig, face_track, key_robot, look_weights, perform_robot, stage_constraints  # noqa: F401
from .example import claude_robot_example  # noqa: F401
from .controller import CollisionWorld, EidoverseRobotController, RobotLegs, build_route  # noqa: F401
from .body import Pending, VRMRobotBody  # noqa: F401
from .debug import RobotDebug  # noqa: F401
