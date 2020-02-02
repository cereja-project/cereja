from cereja.arraytools import array_gen, Matrix, array_randn


class Policy(object):
    def __init__(self, input_size: int, output_size: int):
        self.weights = Matrix(array_randn(shape=(output_size, input_size)))

    def evaluate(self, input_, delta=None, direction=None):
        return self.weights.dot(input_)  # Perceptron


if __name__ == '__main__':
    X = Matrix([[5, 7, -1],
                [6, 0, -3],
                [-4, 3, 0]])
    Y = [[0, 3, -5],
         [2, 0, 0],
         [-1, -5, 3]]
    print(X - Y)
