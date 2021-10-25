from algorithms.loss_functions.iqlearn import IQLearnLoss, IQLearnLossDRQ
from algorithms.loss_functions.sqil import SQILLoss
from algorithms.online import OnlineTraining
from core.datasets import MixedReplayBuffer, MixedSequenceReplayBuffer
from modules.alpha_tuning import AlphaTuner
from modules.curriculum import CurriculumScheduler

import torch as th


class OnlineImitation(OnlineTraining):
    def __init__(self, expert_dataset, agent, config,
                 initial_replay_buffer=None, **kwargs):
        super().__init__(config, expert_dataset=expert_dataset,
                         initial_replay_buffer=initial_replay_buffer, **kwargs)
        self.agent = agent

        self.drq = config.method.drq
        if config.method.loss_function == 'sqil':
            self.loss_function = SQILLoss(agent, config)
        elif config.method.loss_function == 'iqlearn' and self.drq:
            self.loss_function = IQLearnLossDRQ(agent, config)
        elif config.method.loss_function == 'iqlearn':
            self.loss_function = IQLearnLoss(agent, config)

        self.optimizer = th.optim.AdamW(agent.parameters(), lr=self.lr)

        self.cyclic_learning_rate = config.cyclic_learning_rate
        if self.cyclic_learning_rate:
            decay_factor = .25**(1/(self.training_steps/4))
            self.scheduler = th.optim.lr_scheduler.CyclicLR(self.optimizer,
                                                            base_lr=self.lr,
                                                            max_lr=self.lr*10,
                                                            mode='exp_range',
                                                            gamma=decay_factor,
                                                            step_size_up=2000,
                                                            cycle_momentum=False)

        self.alpha_tuner = AlphaTuner([self.agent], config, self.context)

        self.curriculum_training = config.curriculum_training
        self.curriculum_scheduler = CurriculumScheduler(config) \
            if self.curriculum_training else None

    def initialize_replay_buffer(self, expert_dataset, initial_replay_buffer=None):
        if initial_replay_buffer is not None:
            print((f'Using initial replay buffer'
                   f' with {len(initial_replay_buffer)} steps'))
        kwargs = dict(
            expert_dataset=expert_dataset,
            config=self.config,
            batch_size=self.batch_size,
            initial_replay_buffer=initial_replay_buffer
        )
        if self.config.lstm_layers == 0:
            replay_buffer = MixedReplayBuffer(**kwargs)
        else:
            replay_buffer = MixedSequenceReplayBuffer(**kwargs)
        return replay_buffer

    def pre_train_step_modules(self, step):
        metrics = {}
        if self.curriculum_scheduler:
            metrics['Curriculum/inclusion_fraction'] = \
                self.curriculum_scheduler.update_replay_buffer(self,
                                                               self.replay_buffer, step)

        if self.alpha_tuner:
            self.alpha_tuner.update_model_alpha(step)
            metrics['alpha'] = agent.alpha
        return metrics

    def train_one_batch(self, batch):
        (expert_batch, expert_idx), (replay_batch, replay_idx) = batch
        expert_batch = self.gpu_loader.transitions_to_device(expert_batch)
        replay_batch = self.gpu_loader.transitions_to_device(replay_batch)
        aug_expert_batch = self.augmentation(expert_batch)
        aug_replay_batch = self.augmentation(replay_batch)

        loss, metrics, final_hidden = self.loss_function(aug_expert_batch,
                                                         aug_replay_batch,
                                                         expert_batch,
                                                         replay_batch)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

        if final_hidden.size()[0] != 0:
            final_hidden_expert, final_hidden_replay = final_hidden.chunk(2, dim=0)
            self.replay_buffer.update_hidden(replay_idx, final_hidden_replay,
                                             expert_idx, final_hidden_expert)

        return metrics

    def post_train_step_modules(self, step):
        metrics = {}
        if self.cyclic_learning_rate:
            self.scheduler.step()
            metrics['learning_rate'] = self.scheduler.get_last_lr()[0]

        if self.alpha_tuner and self.alpha_tuner.entropy_tuning:
            alpha_metrics = self.alpha_tuner.update_alpha(metrics['entropy'])
            metrics = {**metrics, **alpha_metrics}
        return metrics
