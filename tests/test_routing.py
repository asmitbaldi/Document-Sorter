from pathlib import Path
import unittest

from smartsort.classifier import Classification, FilenameRouter


class FilenameRouterTests(unittest.TestCase):
    def test_clear_filename_routes(self) -> None:
        cases = [
            ("CampusX Machine Learning Notes.pdf", "ML"),
            ("Operating Systems Unit 3.pdf", "OS"),
            ("Image Processing slides.pptx", "IVP"),
            ("Software Engineering UML.docx", "SWE"),
            ("Solar Energy Notes.txt", "SET"),
            ("Flutter Mobile App Development.pptx", "MAD"),
            ("Artificial Intelligence Unit 2.pdf", "AI"),
        ]
        for filename, expected in cases:
            with self.subTest(filename=filename):
                result = FilenameRouter().route(Path(filename))
                self.assertIsNotNone(result)
                self.assertEqual(result.destination, expected)
                self.assertEqual(result.confidence, 1.0)

    def test_ambiguous_filename_requires_ai(self) -> None:
        self.assertIsNone(FilenameRouter().route(Path("lecture-notes.pdf")))

    def test_classification_rejects_invalid_destination(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported"):
            Classification("Finance", 0.95, "not allowed")
