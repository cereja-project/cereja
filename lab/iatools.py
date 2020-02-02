from cereja.arraytools import array_gen, Matrix, array_randn


class Policy(object):
    def __init__(self, input_size: int, output_size: int):
        self.weights = Matrix(array_randn(shape=(output_size, input_size)))

    def evaluate(self, input_, delta=None, direction=None):
        return self.weights.dot(input_)  # Perceptron


if __name__ == '__main__':
    p = Policy(100,100)
    print(max(p.weights.flatten()))
