from agents.bc import BCAgent
from helpers.trajectories import Trajectory, TrajectoryGenerator
from environment.start import start_env

from pathlib import Path
import os


if __name__ == "__main__":
    MINERL_ENVIRONMENT = 'MineRLBasaltFindCave-v0'
    os.environ['MINERL_ENVIRONMENT'] = MINERL_ENVIRONMENT
    env = start_env(debug_env=False)
    agent = BCAgent()
    saved_agent_path = Path('train') / '1630688204_bcx.pth'
    agent.load_parameters(saved_agent_path)
    generator = TrajectoryGenerator(env, agent)
    trajectory = generator.generate(max_episode_length=1000)
    trajectory.view()
    save_path = Path('data') / 'eval' / 'run_001'
    del trajectory
    env.close()
