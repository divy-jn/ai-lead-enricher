import unittest
from src.preprocessing import clean_html

class TestPreprocessing(unittest.TestCase):
    def test_basic_retention(self):
        html = """
        <html>
        <body>
            <nav>Nav content here</nav>
            <h1>My Header</h1>
            <p>This is a very useful paragraph that contains lots of good information about our company.</p>
            <footer>Footer content here</footer>
        </body>
        </html>
        """
        text = clean_html(html)
        print("RESULT:")
        print(repr(text))
        self.assertIn("useful paragraph", text)

    def test_dedup(self):
        html = """
        <html>
        <body>
            <p>Unique content 1</p>
            <p>Boilerplate line that repeats</p>
            <p>Unique content 2</p>
            <p>Boilerplate line that repeats</p>
            <p>Unique content 3</p>
            <p>Boilerplate line that repeats</p>
        </body>
        </html>
        """
        text = clean_html(html)
        print("RESULT DEDUP:")
        print(repr(text))
        self.assertNotIn("Boilerplate line that repeats", text)
        self.assertIn("Unique content 1", text)

if __name__ == "__main__":
    unittest.main()
