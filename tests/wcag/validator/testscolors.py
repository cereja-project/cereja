import unittest
from cereja.utils.colors import Color
from cereja.wcag.validator import contrast_checker

class TestContrastChecker(unittest.TestCase):

    def test_contrast_checker_small_text(self):
        """
        Test the contrast checker for small text with AA and AAA compliance.
        """
        result = contrast_checker("#FFFFFF", "#000000", "12pt")
        self.assertEqual(result['Element Type']['Small Text']['AA'], 'Pass')
        self.assertEqual(result['Element Type']['Small Text']['AAA'], 'Pass')
        self.assertEqual(result['Element Type']['Large Text']['AA'], 'Pass')
        self.assertEqual(result['Element Type']['Large Text']['AAA'], 'Pass')
        self.assertEqual(result['contrast_ratio'], '21.0:1')

    def test_contrast_checker_large_text(self):
        """
        Test the contrast checker for large text with AA and AAA compliance.
        """
        result = contrast_checker("#FFFFFF", "#777777", "18pt")
        self.assertEqual(result['Element Type']['Small Text']['AA'], 'Fail')
        self.assertEqual(result['Element Type']['Small Text']['AAA'], 'Fail')
        self.assertEqual(result['Element Type']['Large Text']['AA'], 'Pass')
        self.assertEqual(result['Element Type']['Large Text']['AAA'], 'Fail')
        self.assertEqual(result['contrast_ratio'], '4.48:1')

    def test_contrast_checker_bold_large_text(self):
        """
        Test the contrast checker for large bold text with AA and AAA compliance.
        """
        result = contrast_checker("#FFFFFF", "#777777", "14pt", is_bold=True)
        self.assertEqual(result['Element Type']['Small Text']['AA'], 'Fail')
        self.assertEqual(result['Element Type']['Small Text']['AAA'], 'Fail')
        self.assertEqual(result['Element Type']['Large Text']['AA'], 'Pass')
        self.assertEqual(result['Element Type']['Large Text']['AAA'], 'Fail')
        self.assertEqual(result['contrast_ratio'], '4.48:1')

    def test_contrast_checker_fail(self):
        """
        Test a case where both small and large text fail AA and AAA compliance.
        """
        result = contrast_checker("#FFFFFF", "#AAAAAA", "16px")
        self.assertEqual(result['Element Type']['Small Text']['AA'], 'Fail')
        self.assertEqual(result['Element Type']['Small Text']['AAA'], 'Fail')
        self.assertEqual(result['Element Type']['Large Text']['AA'], 'Fail')
        self.assertEqual(result['Element Type']['Large Text']['AAA'], 'Fail')
        self.assertEqual(result['contrast_ratio'], '2.32:1')

    def test_contrast_checker_high_contrast(self):
        """
        Test a case with a very high contrast ratio.
        """
        result = contrast_checker("#FFFFFF", "#00008B", "16px")
        self.assertEqual(result['Element Type']['Small Text']['AA'], 'Pass')
        self.assertEqual(result['Element Type']['Small Text']['AAA'], 'Pass')
        self.assertEqual(result['Element Type']['Large Text']['AA'], 'Pass')
        self.assertEqual(result['Element Type']['Large Text']['AAA'], 'Pass')
        self.assertEqual(result['contrast_ratio'], '15.3:1')

if __name__ == '__main__':
    unittest.main()
