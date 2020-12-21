"""

Copyright (c) 2019 The Cereja Project

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import random

import cereja.mathtools
from cereja.array import array_gen, Matrix, array_randn


class HyperParam(object):
    def __init__(self):
        self.n_steps = 1000
        self.episode_length = 1000
        self.learning_rate = 0.02
        self.n_directions = 16
        self.n_best_directions = 16
        assert self.n_best_directions <= self.n_directions, "n_best_directions > n_directions"
        self.noise = 0.03
        self.seed = 1
        self.env_name = 'HalfCheetahBulletEnv-v0'


hp = HyperParam()


class Normalizer(object):
    def __init__(self, n_inputs):
        self.n = Matrix(array_gen((n_inputs,), 0.0))
        self.mean = Matrix(array_gen((n_inputs,), 0.0))
        self.mean_diff = Matrix(array_gen((n_inputs,), 0.0))
        self.var = Matrix(array_gen((n_inputs,), 0.0))

    def observe(self, state):
        self.n += 1.
        last_mean = self.mean.copy()
        self.mean += (state - self.mean) / self.n
        self.mean_diff += (state - last_mean) * (state - self.mean)
        self.var = (self.mean_diff / self.n)  # 1e-2 need clip

    def normalize(self, inputs):
        observe_mean = self.mean
        obs_std = self.var.sqrt()
        return (inputs - observe_mean) / obs_std


class Policy(object):
    def __init__(self, input_size: int, output_size: int):
        self.weights = Matrix(array_gen((output_size, input_size), 0.0))

    def evaluate(self, input_, delta=None, direction=None):
        if direction is None:
            return self.weights.dot(input_)
        elif direction == 'posittive':
            return cereja.mathtools.dot(input_)
        else:
            return cereja.mathtools.dot(input_)

    def sample_deltas(self):
        return [Matrix(array_randn(self.weights.shape)) for _ in range(hp.n_directions)]

    def update(self, rollouts, sigma_r):
        step = Matrix(array_gen(self.weights.shape, 0.0))
        for r_pos, r_neg, d in rollouts:
            step += (r_pos - r_neg) * d
        self.weights += hp.learning_rate / (hp.n_best_directions * sigma_r) * step


def explore(env, normalizer, policy, direction=None, delta=None):
    state = env.reset()
    done = False
    num_plays = 0.
    sum_rewards = 0
    while not done and num_plays < hp.episode_length:
        normalizer.observe(state)
        state = normalizer.normalize(state)
        action = policy.evaluate(state, delta, direction)
        state, reward, done, _ = env.step(action)
        reward = max(min(reward, 1), -1)
        sum_rewards += reward
        num_plays += 1
    return sum_rewards


def train(env, policy: Policy, normalizer, hp: HyperParam):
    for step in range(hp.n_steps):
        deltas = policy.sample_deltas()
        positive_rewards = [0] * hp.n_directions
        negative_rewards = [0] * hp.n_directions
        for k in range(hp.n_directions):
            positive_rewards[k] = explore(env, normalizer, policy, direction='positive', delta=deltas[k])

        for k in range(hp.n_directions):
            negative_rewards[k] = explore(env, normalizer, policy, direction='negattive', delta=deltas[k])

        all_rewards = Matrix((positive_rewards + negative_rewards))
        sigma_r = all_rewards.std()
        score = {k: max(r_pos, r_neg) for k, (r_pos, r_neg) in enumerate(zip(positive_rewards, negative_rewards))}
        order = sorted(score.keys(), key=lambda x: score[x], reverse=True)[:hp.n_best_directions]
        rollouts = [(positive_rewards[k], negative_rewards[k], deltas[k]) for k in order]
        policy.update(rollouts, sigma_r)
        reward_evaluation = explore(env, normalizer, policy)
        print(f'Step: {step} - Reward: {reward_evaluation}')


random.seed(hp.seed)
