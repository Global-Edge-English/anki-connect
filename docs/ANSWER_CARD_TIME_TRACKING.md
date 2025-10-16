# Answer Card Time Tracking

## Overview

The `answerCard` API has been updated to support accurate time tracking when answering cards programmatically. This allows you to record the actual time a user spent studying a card, ensuring your statistics remain accurate.

## API Changes

### Updated Method Signature

```python
answerCard(cardId, ease, timeTakenSeconds=None)
```

**Parameters:**

- `cardId` (int): ID of the card to answer
- `ease` (int): Difficulty rating (1=Again, 2=Hard, 3=Good, 4=Easy)
- `timeTakenSeconds` (float, optional): Time taken to answer the card in seconds

**Returns:**

- `bool`: True if successful

## Usage Examples

### Example 1: Basic Usage with Time Tracking

```python
import requests
import time

# Get the next card to review
response = requests.post('http://localhost:8765', json={
    'action': 'getNextReviewCard',
    'version': 6,
    'params': {
        'deckName': 'Spanish'
    }
})
card = response.json()['result']
card_id = card['cardId']

# Display card to user...
start_time = time.time()

# User studies the card and provides answer...
# (your UI code here)

# Calculate elapsed time
elapsed_time = time.time() - start_time

# Answer the card with actual time taken
response = requests.post('http://localhost:8765', json={
    'action': 'answerCard',
    'version': 6,
    'params': {
        'cardId': card_id,
        'ease': 3,  # User clicked "Good"
        'timeTakenSeconds': elapsed_time  # e.g., 15.7 seconds
    }
})
```

### Example 2: Batch Processing with Consistent Time

```python
import requests

# If you're programmatically answering cards with a fixed time
cards = [1234567890, 1234567891, 1234567892]

for card_id in cards:
    response = requests.post('http://localhost:8765', json={
        'action': 'answerCard',
        'version': 6,
        'params': {
            'cardId': card_id,
            'ease': 3,
            'timeTakenSeconds': 10.0  # 10 seconds per card
        }
    })
```

### Example 3: Using multi Action for Batch Operations

```python
import requests

# Answer multiple cards with different times
actions = []
for card_id, elapsed_time in [(1234, 12.5), (5678, 8.3), (9012, 15.7)]:
    actions.append({
        'action': 'answerCard',
        'params': {
            'cardId': card_id,
            'ease': 3,
            'timeTakenSeconds': elapsed_time
        }
    })

response = requests.post('http://localhost:8765', json={
    'action': 'multi',
    'version': 6,
    'params': {
        'actions': actions
    }
})
```

### Example 4: Backward Compatibility (No Time Tracking)

```python
import requests

# If you omit timeTakenSeconds, it defaults to ~0 seconds (old behavior)
response = requests.post('http://localhost:8765', json={
    'action': 'answerCard',
    'version': 6,
    'params': {
        'cardId': 1234567890,
        'ease': 3
        # No timeTakenSeconds - will record ~0 seconds
    }
})
```

## How It Works

When you provide `timeTakenSeconds`:

1. The value is converted from seconds to milliseconds (Anki's internal format)
2. It's stored in the card's `timeTaken` property
3. Anki records this time in the review log (`revlog` table)
4. Statistics like average time per card are calculated from this data

## Verifying Time Statistics

After answering cards, you can verify the time was recorded correctly:

```python
import requests

# Get deck time statistics
response = requests.post('http://localhost:8765', json={
    'action': 'getDeckTimeStats',
    'version': 6,
    'params': {
        'deckName': 'Spanish',
        'period': 'today'  # or 'last7days', 'last30days', 'allTime'
    }
})

stats = response.json()['result']
print(f"Total reviews: {stats['totalReviews']}")
print(f"Total time: {stats['totalTimeSeconds']} seconds")
print(f"Average time per card: {stats['averageTimePerCardSeconds']} seconds")
```

## Best Practices

1. **Always track actual user time**: If you're building a custom study interface, measure the actual time from when the card is shown until the user answers.

2. **Use reasonable values**: Time should typically be between 1-60 seconds for most cards. Values outside this range may indicate timing issues.

3. **Handle errors gracefully**: If time tracking fails, you can still answer the card without the time parameter.

4. **Batch operations**: Use the `multi` action to answer multiple cards efficiently while still tracking individual times.

## Migration Guide

If you have existing code that uses `answerCard`, no changes are required! The new parameter is optional and maintains backward compatibility:

```python
# Old code - still works
answerCard(cardId, ease)

# New code - with time tracking
answerCard(cardId, ease, timeTakenSeconds=15.5)
```

## Technical Details

- **Internal format**: Time is stored in milliseconds in Anki's database
- **Precision**: You can provide fractional seconds (e.g., 12.5 seconds)
- **Database table**: Times are recorded in the `revlog` table's `time` column
- **Statistics**: Anki uses these times to calculate study statistics and graphs

## Related API Methods

- `getNextReviewCard()` - Get the next card to review
- `getDeckTimeStats()` - Get time statistics for a deck
- `getStudyStats()` - Get general study statistics
- `multi()` - Batch multiple operations including answerCard
