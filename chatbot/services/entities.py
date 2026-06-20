import re
from decimal import Decimal


UNDER_WORDS = [
    'under', 'below', 'less', 'within', 'cheap', 'budget', 'low',
    'kom', 'niche', 'moddhe', 'মধ্যে', 'কম', 'নিচে', 'সস্তা'
]

OVER_WORDS = [
    'over', 'above', 'more', 'greater', 'premium', 'luxury', 'high',
    'upor', 'beshi', 'উপর', 'বেশি', 'প্রিমিয়াম'
]

BETWEEN_WORDS = [
    'between', 'range', 'to', 'theke', 'থেকে', 'মধ্যে', '-'
]


def extract_numbers(text):
    text = str(text or '')
    numbers = re.findall(r'\d+', text)
    return [int(number) for number in numbers]


def extract_price_filter(text, default_mode=None):
    text_lower = str(text or '').lower()
    numbers = extract_numbers(text_lower)

    if not numbers:
        return {
            'mode': default_mode,
            'amount': None,
            'low': None,
            'high': None
        }

    has_between = any(word in text_lower for word in BETWEEN_WORDS) and len(numbers) >= 2
    has_under = any(word in text_lower for word in UNDER_WORDS)
    has_over = any(word in text_lower for word in OVER_WORDS)

    if has_between and len(numbers) >= 2:
        low = min(numbers[0], numbers[1])
        high = max(numbers[0], numbers[1])

        return {
            'mode': 'between',
            'amount': None,
            'low': Decimal(low),
            'high': Decimal(high)
        }

    if has_over:
        return {
            'mode': 'over',
            'amount': Decimal(numbers[0]),
            'low': None,
            'high': None
        }

    if has_under:
        return {
            'mode': 'under',
            'amount': Decimal(numbers[0]),
            'low': None,
            'high': None
        }

    return {
        'mode': default_mode or 'under',
        'amount': Decimal(numbers[0]),
        'low': None,
        'high': None
    }


def detect_destination_type(text):
    text_lower = str(text or '').lower()

    if any(word in text_lower for word in ['beach', 'sea', 'cox', 'kuakata', 'somudro', 'সমুদ্র', 'বিচ']):
        return 'beach'

    if any(word in text_lower for word in ['hill', 'mountain', 'pahar', 'bandarban', 'rangamati', 'sajek', 'পাহাড়']):
        return 'hill'

    if any(word in text_lower for word in ['forest', 'jungle', 'sundarban', 'bon', 'বন']):
        return 'forest'

    if any(word in text_lower for word in ['historical', 'heritage', 'history', 'fort', 'museum', 'ঐতিহাসিক']):
        return 'historical'

    return None


def detect_booking_status(text):
    text_lower = str(text or '').lower()

    if any(word in text_lower for word in ['pending', 'waiting', 'unconfirmed']):
        return 'pending'

    if any(word in text_lower for word in ['confirmed', 'approved', 'accepted']):
        return 'confirmed'

    if any(word in text_lower for word in ['completed', 'past', 'old', 'history']):
        return 'completed'

    if any(word in text_lower for word in ['cancelled', 'canceled', 'cancel']):
        return 'cancelled'

    return None


def extract_booking_id(text):
    text_lower = str(text or '').lower()

    patterns = [
        r'booking\s*#?\s*(\d+)',
        r'booking id\s*#?\s*(\d+)',
        r'id\s*#?\s*(\d+)',
        r'#\s*(\d+)'
    ]

    for pattern in patterns:
        match = re.search(pattern, text_lower)

        if match:
            return int(match.group(1))

    numbers = extract_numbers(text_lower)

    if numbers:
        return numbers[0]

    return None


def extract_limit(text, default=6, maximum=10):
    numbers = extract_numbers(text)

    if not numbers:
        return default

    value = numbers[0]

    if value <= 0:
        return default

    return min(value, maximum)