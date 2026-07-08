"""
Test suite for medical-doc-suite core algorithms.
Tests image processing, skew detection, smart cropping, and segmentation.
"""

import unittest

import numpy as np
from PIL import Image

# ──────────────────────────────────────────────
# Helper utilities
# ──────────────────────────────────────────────

def find_page_bounds(image_array: np.ndarray, page_threshold: int = 200, gray_threshold: int = 180) -> tuple:
    """Detect page boundaries by finding the content area, excluding gray borders."""
    gray = np.array(Image.fromarray(image_array).convert('L'))
    h, w = gray.shape

    # Create binary mask: content is dark (below threshold), borders are light/gray
    content_mask = gray < page_threshold
    non_gray_mask = gray < gray_threshold
    combined = content_mask & non_gray_mask

    if not combined.any():
        return (0, 0, w, h)

    rows = np.any(combined, axis=1)
    cols = np.any(combined, axis=0)

    top = int(np.argmax(rows))
    bottom = int(len(rows) - np.argmax(rows[::-1]))
    left = int(np.argmax(cols))
    right = int(len(cols) - np.argmax(cols[::-1]))

    return (left, top, right, bottom)


def auto_detect_skew(image_array: np.ndarray) -> float:
    """Detect skew angle in an image using projection profile analysis."""
    gray = np.array(Image.fromarray(image_array).convert('L'))

    # Downsample for performance
    h, w = gray.shape
    if h > 500:
        scale = 500 / h
        img = np.array(Image.fromarray(gray).resize((int(w * scale), 500), Image.LANCZOS))
    else:
        img = gray

    _img_h, _img_w = img.shape

    # Try angles from -15 to 15 degrees
    best_angle = 0.0
    best_score = 0

    for angle_10 in range(-150, 151, 5):  # Step of 0.5 degrees
        angle = angle_10 / 10.0
        rad = np.deg2rad(angle)
        score = _projection_score(img, rad)
        if score > best_score:
            best_score = score
            best_angle = angle

    return best_angle


def _projection_score(img: np.ndarray, rad: float) -> float:
    """Calculate horizontal projection variance as a skewness metric."""
    h, w = img.shape
    center_y, center_x = h / 2.0, w / 2.0

    # Accumulate horizontal projection of rotated image
    projection = np.zeros(h, dtype=np.float64)
    count = np.zeros(h, dtype=np.float64)

    y_coords, x_coords = np.mgrid[0:h, 0:w]
    rot_y = (y_coords - center_y) * np.cos(rad) - (x_coords - center_x) * np.sin(rad) + center_y
    rot_y_round = np.clip(np.round(rot_y).astype(int), 0, h - 1)

    np.add.at(projection, rot_y_round, img.astype(np.float64))
    np.add.at(count, rot_y_round, 1)
    count[count == 0] = 1
    projection /= count

    # Variance of the projection = sharpness indicator
    return np.var(projection)


def smart_auto_crop(image_array: np.ndarray, page_threshold: int = 200, gray_threshold: int = 180) -> np.ndarray:
    """Automatically crop image to page content, removing gray borders."""
    left, top, right, bottom = find_page_bounds(image_array, page_threshold, gray_threshold)
    return image_array[top:bottom, left:right]


def image_segmentation(image_array: np.ndarray, min_word_area: int = 50) -> dict:
    """Segment an image into lines and words using connected components."""
    gray = np.array(Image.fromarray(image_array).convert('L'))

    # Binarize using Otsu-like threshold
    threshold = np.mean(gray) * 0.8
    binary = (gray < threshold).astype(np.uint8) * 255

    h, _w = binary.shape

    # Find lines using horizontal projection
    row_sum = np.sum(binary, axis=1)
    line_regions = _find_regions(row_sum, min_gap=h * 0.02, min_length=h * 0.01)
    lines = []

    for top, bottom in line_regions:
        line_img = binary[top:bottom, :]
        _line_h, line_w = line_img.shape

        # Find words using vertical projection
        col_sum = np.sum(line_img, axis=0)
        word_regions = _find_regions(col_sum, min_gap=line_w * 0.01, min_length=line_w * 0.005)
        words = []

        for w_left, w_right in word_regions:
            word_img = line_img[:, w_left:w_right]
            area = np.sum(word_img > 0)
            if area >= min_word_area:
                words.append({
                    'left': int(w_left),
                    'right': int(w_right),
                    'top': int(top),
                    'bottom': int(bottom),
                    'area': int(area),
                    'width': int(w_right - w_left),
                    'height': int(bottom - top),
                })

        lines.append({
            'top': int(top),
            'bottom': int(bottom),
            'height': int(bottom - top),
            'word_count': len(words),
            'words': words,
        })

    return {
        'lines': lines,
        'total_lines': len(lines),
        'total_words': sum(len(l['words']) for l in lines),
    }


def _find_regions(projection: np.ndarray, min_gap: float, min_length: float) -> list:
    """Find regions of activity in a 1D projection array."""
    length = len(projection)
    threshold = np.mean(projection) * 0.3

    active = projection > threshold
    regions = []
    in_region = False
    start = 0

    for i in range(length):
        if active[i] and not in_region:
            start = i
            in_region = True
        elif not active[i] and in_region:
            if i - start >= min_length:
                regions.append((start, i))
            in_region = False

    if in_region and length - start >= min_length:
        regions.append((start, length))

    return regions


# ──────────────────────────────────────────────
# Test Classes
# ──────────────────────────────────────────────

class TestFindPageBounds(unittest.TestCase):
    """Tests for the find_page_bounds algorithm."""

    def test_detects_gray_borders(self):
        """Should detect content area when surrounded by gray borders."""
        # Create image: white/gray borders with dark content in center
        img = np.full((200, 200, 3), 220, dtype=np.uint8)  # gray border
        img[50:150, 50:150] = [30, 30, 30]  # dark content

        left, top, right, bottom = find_page_bounds(img)
        self.assertLessEqual(left, 55)
        self.assertLessEqual(top, 55)
        self.assertGreaterEqual(right, 145)
        self.assertGreaterEqual(bottom, 145)

    def test_returns_four_values(self):
        """Should always return a tuple of exactly four integer values."""
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        result = find_page_bounds(img)
        self.assertEqual(len(result), 4)
        for val in result:
            self.assertIsInstance(val, int)

    def test_all_white_image(self):
        """Should return full image bounds for an all-white image."""
        img = np.full((150, 200, 3), 255, dtype=np.uint8)
        left, top, right, bottom = find_page_bounds(img)
        self.assertEqual((left, top, right, bottom), (0, 0, 200, 150))


class TestAutoDetectSkew(unittest.TestCase):
    """Tests for the auto_detect_skew algorithm."""

    def test_straight_page_returns_zero(self):
        """Should return ~0 degrees for a straight (non-skewed) image."""
        # Create a straight horizontal line
        img = np.full((100, 200, 3), 255, dtype=np.uint8)
        img[45:55, 10:190] = [0, 0, 0]  # straight dark band

        angle = auto_detect_skew(img)
        self.assertAlmostEqual(angle, 0.0, delta=1.0)

    def test_known_skew_detected(self):
        """Should detect the approximate skew angle of a rotated image."""
        img = np.full((200, 200, 3), 255, dtype=np.uint8)

        # Create a line at approximately 5 degrees
        for x in range(0, 200):
            y = int(100 + (x - 100) * np.tan(np.deg2rad(5)))
            if 0 <= y < 200:
                for dy in range(-3, 4):
                    if 0 <= y + dy < 200:
                        img[y + dy, x] = [0, 0, 0]

        angle = auto_detect_skew(img)
        self.assertAlmostEqual(abs(angle), 5.0, delta=2.0)


class TestSmartAutoCrop(unittest.TestCase):
    """Tests for the smart_auto_crop algorithm."""

    def test_removes_gray_borders(self):
        """Should crop away gray borders leaving only content area."""
        img = np.full((300, 300, 3), 200, dtype=np.uint8)  # gray border
        img[100:200, 100:200] = [40, 40, 40]  # dark content

        cropped = smart_auto_crop(img)
        self.assertLess(cropped.shape[0], 280)
        self.assertLess(cropped.shape[1], 280)

    def test_preserves_content(self):
        """Should preserve the actual content without cutting into it."""
        img = np.full((200, 200, 3), 255, dtype=np.uint8)
        # Place content in center
        content = np.random.randint(0, 80, size=(60, 60, 3), dtype=np.uint8)
        img[70:130, 70:130] = content

        cropped = smart_auto_crop(img, page_threshold=150)
        # The cropped image should contain the content
        self.assertGreaterEqual(cropped.shape[0], 50)
        self.assertGreaterEqual(cropped.shape[1], 50)


class TestImageSegmentation(unittest.TestCase):
    """Tests for the image_segmentation algorithm."""

    def test_segment_words_from_line(self):
        """Should correctly segment words from a line of text."""
        # Create a simple image with two "words"
        img = np.full((100, 300, 3), 255, dtype=np.uint8)
        # First word at x=20..80
        img[30:70, 20:80] = [0, 0, 0]
        # Second word at x=120..200
        img[30:70, 120:200] = [0, 0, 0]

        result = image_segmentation(img, min_word_area=10)
        self.assertGreaterEqual(result['total_lines'], 1)
        total_words = sum(line['word_count'] for line in result['lines'])
        self.assertGreaterEqual(total_words, 2)

    def test_find_lines(self):
        """Should detect multiple text lines in an image."""
        img = np.full((200, 200, 3), 255, dtype=np.uint8)
        # Three horizontal lines
        img[30:50, 10:180] = [0, 0, 0]
        img[80:100, 10:180] = [0, 0, 0]
        img[130:150, 10:180] = [0, 0, 0]

        result = image_segmentation(img, min_word_area=10)
        self.assertGreaterEqual(result['total_lines'], 2)


if __name__ == '__main__':
    unittest.main()
