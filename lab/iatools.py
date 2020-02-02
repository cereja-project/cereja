from cereja.arraytools import array_gen, Matrix, array_randn


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
        self.env_name = ''


class Normalizer(object):
    def __init__(self, n_inputs):
        self.n = Matrix(array_gen((n_inputs,), 0.0))
        self.mean = Matrix(array_gen((n_inputs,), 0.0))
        self.mean_diff = Matrix(array_gen((n_inputs,), 0.0))
        self.var = Matrix(array_gen((n_inputs,), 0.0))

    def observe(self, state):
        self.n += 1.
        last_mean = self.mean


class Policy(object):
    def __init__(self, input_size: int, output_size: int):
        self.weights = Matrix(array_randn(shape=(output_size, input_size)))

    def evaluate(self, input_, delta=None, direction=None):
        return self.weights.dot(input_)  # Perceptron


if __name__ == '__main__':
    pass
