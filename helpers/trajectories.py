from helpers.environment import EnvironmentHelper, ObservationSpace

import math
import os
import shutil

import numpy as np
import torch as th

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Slider


class Trajectory:
    def __init__(self):
        self.obs = []
        self.actions = []
        self.done = False
        self.number_of_frames = ObservationSpace.number_of_frames

    def __len__(self):
        return len(self.obs)

    def __getitem__(self, idx):
        done = idx + 1 == len(self) and self.done
        return(self.obs[idx], self.actions[idx], done)

    def current_state(self):
        current_step = len(self)
        frame_sequence = self.spaced_frames(current_step)
        current_pov = ObservationSpace.obs_to_pov(self.obs[-1])
        current_inventory = ObservationSpace.obs_to_inventory(self.obs[-1])
        current_equipped = ObservationSpace.obs_to_equipped_item(self.obs[-1])
        return current_pov, current_inventory, current_equipped, frame_sequence

    def append_step(self, action):
        self.obs.append(current_obs)
        self.current_obs = None
        self.actions.append(action)

    def load(self, path):
        self.obs = np.load(self.trajectory_path / 'obs.npy', allow_pickle=True)
        self.actions = np.load(self.trajectory_path / 'actions.npy', allow_pickle=True)
        self.done = True

    def save(self, path):
        path.mkdir(exist_ok=True)
        np.save(file=path / 'actions.npy', arr=np.array(self.actions))
        np.save(file=path / 'obs.npy', arr=np.array(self.observations))
        steps_path = path / 'steps'
        shutil.rmtree(steps_path, ignore_errors=True)
        steps_path.mkdir()
        for step in range(len(self)):
            obs, action, done = self[step]
            step_name = f'step{str(step).zfill(5)}.npy'
            step_dict = {'step': step, 'obs': obs, 'action': action, 'done': done}
            np.save(file=steps_path / step_name, arr=step_dict)

    def spaced_frames(self, current_step):
        frame_indices = [int(math.floor(current_step *
                                        frame_number / (self.number_of_frames - 1)))
                         for frame_number in range(self.number_of_frames - 1)]
        frames = th.cat([ObservationSpace.obs_to_pov(self.obs[frame_idx])
                        for frame_idx in frame_indices])
        return frames

    def view(self):
        viewer = TrajectoryViewer(self).view()


class TrajectoryGenerator:
    def __init__(self, env, agent):
        self.env = env
        self.agent = agent
        self.max_episode_length = EnvironmentHelper.max_episode_length

    def generate(self):
        trajectory = Trajectory()
        obs = self.env.reset()

        while not trajectory.done and len(trajectory) < self.max_episode_length:
            trajectory.obs.append(obs)
            action = self.agent.get_action(trajectory)
            trajectory.actions.append(action)
            obs, _, done, _ = self.env.step(action)
            trajectory.done = done
        return trajectory


class TrajectoryViewer:
    def __init__(self, trajectory):
        self.trajectory = trajectory
        self.current_step = 0
        self.manual_control = False

    def view(self):
        def play():
            if len(self.trajectory) > 1:
                slider.set_val(self.current_frame)
                slider.on_changed(update_slider)
                fig.canvas.mpl_connect('button_press_event', on_click)
                ani = animation.FuncAnimation(
                    fig, update_plot, animation_data_gen, interval=2, blit=True)
            fig.canvas.mpl_connect('key_press_event', on_keypress)
            plt.show()

        def animation_data_gen():
            for step, _ in enumerate(self.trajectory):
                yield step

        def update_plot(step):
            if self.manual_control:
                return animated_elements
            step = slider.val + 1
            if step >= len(self.trajectory):
                step = len(self.trajectory) - 1
                slider.set_val(step)
                return lines
            slider.set_val(step)
            self.manual_control = False
            return animated_elements

        def update_slider(step):
            step = math.floor(step)
            self.current_frame = step
            self.manual_control = True
            render_frame(step)

        def render_frame(step):
            frame = self.trajectory.obs[step]["pov"]
            l2.set_xdata(step)
            l3.set_xdata(step)
            action_name = ActionSpace.action_name(self.trajectory.actions[step])
            txt_action.set_text(f'Action: {action_name}')
            img.set_array(frame)
            fig.canvas.flush_events()
            fig.canvas.draw_idle()

        def on_click(event):
            (sxm, sym), (sxM, syM) = slider.label.clipbox.get_points()
            if sxm < event.x < sxM and sym < event.y < syM:
                return
            self.manual_control = False if self.manual_control else True

        def on_keypress(event):
            if event.key == 'enter':
                plt.close('all')
            if len(self.trajectory) < 2:
                return
            if event.key == ' ':
                self.manual_control = False if self.manual_control else True
            else:
                self.manual_control = True
                if event.key == 'right':
                    if self.current_frame < len(self.trajectory) - 1:
                        self.current_frame += 1
                elif event.key == 'left':
                    if self.current_frame > 0:
                        self.current_frame -= 1
                slider.set_val(self.current_frame)

        fig = plt.figure(figsize=(9, 8))
        ax_pov = plt.subplot2grid((9, 8), (0, 0), colspan=5, rowspan=5)
        img = ax_pov.imshow(self.trajectory.obs[self.current_frame]["pov"], animated=True)
        txt_action = ax4.text(.1, 1.35, 'Action:')
        animated_elements = [img, txt_action]

        if len(self.trajectory) > 0:
            ax_steps = plt.axes([0.2, 0.15, 0.65, 0.03])
            slider = Slider(ax_steps, 'Step', 0, len(self.trajectory) - 1, valinit=0)

        play()
