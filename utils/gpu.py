from utils.environment import ActionSpace, ObservationSpace

import torch as th


def cat_states(tuple_of_states):
    state_lengths = [states[0].size()[0] for states in tuple_of_states]
    all_states = [th.cat(state_component, dim=0) for state_component
                  in zip(*tuple_of_states)]
    return all_states, state_lengths


def cat_batches(tuple_of_batches):
    states, actions, next_states, done, reward = zip(*tuple_of_batches)
    states, _ = cat_states(states)
    actions = th.cat(actions, dim=0)
    next_states, _ = cat_states(next_states)
    done = th.cat(done, dim=0)
    reward = th.cat(reward, dim=0)
    return states, actions, next_states, done, reward


def disable_gradients(network):
    for param in network.parameters():
        param.requires_grad = False


class GPULoader:
    def __init__(self):
        self.device = th.device("cuda:0" if th.cuda.is_available() else "cpu")
        starting_count = th.FloatTensor(
            list(ObservationSpace.starting_inventory().values())).reshape(1, -1)
        ones = th.ones(starting_count.size())
        self.item_normalization = th.cat((starting_count, ones), dim=1).to(self.device)

    def normalize_state(self, state):
        state = list(state)
        state[0] /= 255.0
        state[1] /= self.item_normalization
        return tuple(state)

    def state_to_device(self, state):
        state = [state_component.unsqueeze(0).to(self.device, dtype=th.float)
                 for state_component in state]
        state = self.normalize_state(state)
        return state

    def states_to_device(self, tuple_of_states):
        # # this is slower, but may be better for larger batch sizes?
        # state_lengths = [states[0].size()[0] for states in tuple_of_states]
        # all_states = [th.cat(state_component, dim=0).to(device) for state_component
        #               in zip(*tuple_of_states)]
        # list_of_states = zip(*[th.split(state_component, state_lengths, dim=0)
        #                        for state_component in all_states])
        # return tuple(list_of_states)
        states = []
        for state in tuple_of_states:
            if len(state) != 0:
                state = [state_component.to(self.device, dtype=th.float)
                         for state_component in state]
                state = self.normalize_state(state)
            states.append(state)
        return tuple(states)

    def expert_batch_to_device(self, batch):
        states, actions, next_states, done, rewards = batch
        states, next_states = self.states_to_device((states, next_states))
        actions = actions.unsqueeze(1).to(self.device)
        done = th.as_tensor(done).unsqueeze(1).float().to(self.device)
        rewards = rewards.float().unsqueeze(1).to(self.device)
        return states, actions, next_states, done, rewards

    def batch_to_device(self, batch):
        states, actions, next_states, done, rewards = batch
        states, next_states = self.states_to_device((states, next_states))
        actions = actions.unsqueeze(1).to(self.device)
        done = th.as_tensor(done).unsqueeze(1).float().to(self.device)
        rewards = rewards.float().unsqueeze(1).to(self.device)
        return states, actions, next_states, done, rewards

    def batches_to_device(self, expert_batch, replay_batch):
        expert_states, expert_actions, expert_next_states, \
            expert_done, _expert_rewards = expert_batch
        replay_states, replay_actions, replay_next_states, \
            replay_done, replay_rewards = replay_batch

        expert_actions = expert_actions.unsqueeze(1).to(self.device)
        replay_actions = replay_actions.unsqueeze(1).to(self.device)

        expert_states, replay_states, expert_next_states, replay_next_states = \
            self.states_to_device((expert_states, replay_states,
                                   expert_next_states, replay_next_states))

        expert_done = th.as_tensor(expert_done).float().unsqueeze(1).to(self.device)
        replay_done = th.as_tensor(replay_done).float().unsqueeze(1).to(self.device)
        replay_rewards = replay_rewards.float().unsqueeze(1).to(self.device)

        expert_batch = expert_states, expert_actions, expert_next_states, \
            expert_done, _expert_rewards
        replay_batch = replay_states, replay_actions, replay_next_states, \
            replay_done, replay_rewards
        return expert_batch, replay_batch