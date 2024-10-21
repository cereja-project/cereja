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

import unittest
import math

from cereja.mathtools import (degrees_to_radian, 
                              distance_between_points, 
                              theta_angle, 
                              nth_fibonacci_number, 
                              imc, 
                              greatest_common_multiple, 
                              least_common_multiple, 
                              proportional, 
                              estimate, 
                              percent, 
                              theta_from_array)


class MathToolsTests(unittest.TestCase):
    def test_imc(self):
        _imc, _ver = imc(2, 3)
        self.assertAlmostEqual(_imc, 0.22222222)
        self.assertEqual(_ver, 'Underweight')
        
    def test_least_common_multiple(self):
        self.assertEqual(least_common_multiple([10, 15]), 30)
    
    def test_greatest_common_multiple(self):
        self.assertEqual(greatest_common_multiple([10, 15]), 5)
    
    def test_estimate(self):
        self.assertEqual(estimate(3, 6, 2), 2)
        
    def test_percent(self):
        self.assertEqual(percent(20, 10, 1), 200)
        
    def test_theta_from_array(self):
        _res = theta_from_array([10, 40], [30, 70])
        self.assertAlmostEqual(_res[0], 9.16234704572)
        
    def test_proportional(self):
        self.assertAlmostEqual(proportional(20, 30, 35), 23.333333333333)
        
    def test_degrees_to_radian(self):
        self.assertEqual(degrees_to_radian(30), math.pi / 6)
        self.assertEqual(degrees_to_radian(60), math.pi / 3)

    def test_distance_between_points(self):
        self.assertEqual(distance_between_points((1, 1), (1, 1)), 0)
        self.assertEqual(distance_between_points((2, 6), (5, 10)), 5)
        self.assertEqual(distance_between_points((1, 1), (6, 13)), 13)

    def test_theta_angle(self):
        u = (2, 2)
        v = (0, -2)
        self.assertEqual(theta_angle(u, v), 135.0)

    def test_nth_fibonacci_number(self):
        with self.assertRaises(ValueError):
            nth_fibonacci_number(-1)
        self.assertEqual(nth_fibonacci_number(1), 0)
        self.assertEqual(nth_fibonacci_number(2), 1)
        self.assertEqual(nth_fibonacci_number(3), 1)
        self.assertEqual(nth_fibonacci_number(4), 2)
        self.assertEqual(nth_fibonacci_number(5), 3)
        self.assertEqual(nth_fibonacci_number(10), 34)
        self.assertEqual(nth_fibonacci_number(12), 89)
        self.assertEqual(nth_fibonacci_number(20), 4181)

if __name__ == "__main__":
    unittest.main()
