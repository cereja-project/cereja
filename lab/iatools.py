from cereja.arraytools import array_gen, Matrix, array_randn


class Policy(object):
    def __init__(self, input_size: int, output_size: int):
        self.weights = Matrix(array_randn(shape=(output_size, input_size)))

    def evaluate(self, input_, delta=None, direction=None):
        return self.weights.dot(input_)  # Perceptron


if __name__ == '__main__':
    X = Matrix([[1, 2, 3],
         [4, 5, 6],
         [7, 8, 9]])
    Y = [[9, 8, 7],
         [6, 5, 4],
         [3, 2, 1]]
    print(X + Y)
