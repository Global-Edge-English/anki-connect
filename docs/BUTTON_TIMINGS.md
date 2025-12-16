# Button Timings Feature

## Overview

The `getNextReviewCard` API now includes timing information for each answer button, showing when the card will be shown again based on the button clicked. This matches the behavior of Anki desktop's reviewer interface.

## Response Format

When calling `getNextReviewCard`, the response now includes enhanced button information:

```json
{
  "cardId": 1234567890,
  "fields": { ... },
  "question": "...",
  "answer": "...",
  "buttons": [
    {
      "ease": 1,
      "label": "Again",
      "timing": "10m"
    },
    {
      "ease": 2,
      "label": "Hard",
      "timing": "4d"
    },
    {
      "ease": 3,
      "label": "Good",
      "timing": "1mo"
    },
    {
      "ease": 4,
      "label": "Easy",
      "timing": "4mo"
    }
  ],
  ...
}
```

## Button Fields

Each button in the `buttons` array contains:

- **`ease`** (int): The ease value (1-4) to pass to `answerCard`

  - 1 = Again
  - 2 = Hard
  - 3 = Good
  - 4 = Easy

- **`label`** (string): Human-readable label for the button

  - For 2-button cards: "Again", "Good"
  - For 3-button cards: "Again", "Good", "Easy"
  - For 4-button cards: "Again", "Hard", "Good", "Easy"

- **`timing`** (string): Next interval prediction in human-readable format
  - Examples: "10m" (10 minutes), "4d" (4 days), "1mo" (1 month), "4mo" (4 months)
  - Empty string if timing cannot be determined (older Anki versions)

## Timing Format

The timing strings use Anki's standard interval format:

- **Seconds**: "Xs" (e.g., "30s")
- **Minutes**: "Xm" (e.g., "10m", "45m")
- **Hours**: "Xh" (e.g., "2h", "12h")
- **Days**: "Xd" (e.g., "1d", "15d")
- **Months**: "Xmo" (e.g., "1mo", "6mo")
- **Years**: "Xy" (e.g., "1y", "3y")

## Example Usage

### Python Example

```python
import requests

response = requests.post('http://localhost:8765', json={
    'action': 'getNextReviewCard',
    'version': 6,
    'params': {
        'deckName': 'English Vocabulary'
    }
})

result = response.json()
if result['error'] is None:
    card = result['result']

    print(f"Question: {card['question']}")
    print("\nAnswer buttons:")

    for button in card['buttons']:
        print(f"  [{button['ease']}] {button['label']}: {button['timing']}")

    # Output:
    # Question: What is the capital of France?
    #
    # Answer buttons:
    #   [1] Again: 10m
    #   [2] Hard: 4d
    #   [3] Good: 10d
    #   [4] Easy: 30d
```

### JavaScript Example

```javascript
const response = await fetch("http://localhost:8765", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    action: "getNextReviewCard",
    version: 6,
    params: {
      deckName: "Spanish",
    },
  }),
});

const data = await response.json();
if (!data.error) {
  const card = data.result;

  // Display buttons in UI
  card.buttons.forEach((button) => {
    const buttonElement = document.createElement("button");
    buttonElement.textContent = `${button.label}\n${button.timing}`;
    buttonElement.onclick = () => answerCard(card.cardId, button.ease);
    document.getElementById("buttons").appendChild(buttonElement);
  });
}
```

## Version Compatibility

- **Anki 2.1.45+**: Full support with timing information from v3 scheduler
- **Older versions**: Graceful fallback - `timing` field will be empty string

The implementation automatically detects the scheduler version and provides the best available information.

## Technical Details

### How It Works

1. When `getNextReviewCard` is called, it retrieves the card from the scheduler
2. It calls `get_scheduling_states(card.id)` to get the current and future states
3. It calls `describe_next_states(states)` to get human-readable timing labels
4. The timing information is included in the response for each button

### Scheduler Methods Used

- `collection.sched.answerButtons(card)` - Gets the number of buttons (2, 3, or 4)
- `collection.sched.get_scheduling_states(card.id)` - Gets scheduling states (v3 scheduler)
- `collection.sched.describe_next_states(states)` - Converts states to timing strings

## Benefits

1. **Informed Decisions**: Users can see the consequences of each button choice
2. **Desktop Parity**: Matches Anki desktop's UI behavior
3. **Better UX**: Helps users understand the spaced repetition algorithm
4. **No Breaking Changes**: Existing code continues to work; new field is additive

## See Also

- [Answer Card Time Tracking](ANSWER_CARD_TIME_TRACKING.md) - Track time spent on cards
- [Custom Study API](CUSTOM_STUDY_API.md) - Advanced study session management
