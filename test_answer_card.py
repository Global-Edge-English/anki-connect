#!/usr/bin/env python3
"""
Test script to verify answerCard API with timeTakenSeconds parameter
"""

import requests
import json

def test_api():
    """Test the answerCard API"""
    
    print("Testing AnkiConnect API...")
    print("-" * 50)
    
    # Test 1: Check version
    print("\n1. Checking AnkiConnect version...")
    response = requests.post('http://localhost:8765', json={
        'action': 'version',
        'version': 6
    })
    print(f"   Response: {response.json()}")
    
    # Test 2: Get deck names
    print("\n2. Getting deck names...")
    response = requests.post('http://localhost:8765', json={
        'action': 'deckNames',
        'version': 6
    })
    result = response.json()
    if result.get('error'):
        print(f"   Error: {result['error']}")
        return
    
    decks = result.get('result', [])
    print(f"   Found {len(decks)} decks: {decks[:3]}...")
    
    if not decks:
        print("   ERROR: No decks found!")
        return
    
    # Test 3: Get a card to answer
    print(f"\n3. Getting next review card from '{decks[0]}'...")
    response = requests.post('http://localhost:8765', json={
        'action': 'getNextReviewCard',
        'version': 6,
        'params': {
            'deckName': decks[0]
        }
    })
    result = response.json()
    
    if result.get('error'):
        print(f"   Error: {result['error']}")
        print("   (This is OK if no cards are due)")
    
    card = result.get('result')
    if not card:
        print("   No cards due for review")
        print("\n4. Trying to get due cards instead...")
        response = requests.post('http://localhost:8765', json={
            'action': 'getDueCards',
            'version': 6,
            'params': {
                'deckName': decks[0],
                'limit': 1
            }
        })
        result = response.json()
        card_ids = result.get('result', [])
        if not card_ids:
            print("   No due cards found. Cannot test answerCard.")
            return
        card_id = card_ids[0]
        print(f"   Found card ID: {card_id}")
    else:
        card_id = card['cardId']
        print(f"   Found card ID: {card_id}")
    
    # Test 4: Try answerCard WITHOUT timeTakenSeconds (old way)
    print(f"\n4. Testing answerCard WITHOUT timeTakenSeconds (backward compatibility)...")
    response = requests.post('http://localhost:8765', json={
        'action': 'answerCard',
        'version': 6,
        'params': {
            'cardId': card_id,
            'ease': 3
        }
    })
    result = response.json()
    
    if result.get('error'):
        print(f"   ❌ Error: {result['error']}")
    else:
        print(f"   ✓ Success: {result['result']}")
    
    # Get another card for the next test
    print(f"\n5. Getting another card for time tracking test...")
    response = requests.post('http://localhost:8765', json={
        'action': 'getDueCards',
        'version': 6,
        'params': {
            'deckName': decks[0],
            'limit': 1
        }
    })
    result = response.json()
    card_ids = result.get('result', [])
    
    if not card_ids:
        print("   No more cards available for testing")
        return
    
    card_id = card_ids[0]
    print(f"   Found card ID: {card_id}")
    
    # Test 5: Try answerCard WITH timeTakenSeconds (new way)
    print(f"\n6. Testing answerCard WITH timeTakenSeconds=15.5...")
    response = requests.post('http://localhost:8765', json={
        'action': 'answerCard',
        'version': 6,
        'params': {
            'cardId': card_id,
            'ease': 3,
            'timeTakenSeconds': 15.5
        }
    })
    result = response.json()
    
    if result.get('error'):
        print(f"   ❌ Error: {result['error']}")
        print("\n" + "="*50)
        print("ISSUE FOUND: The timeTakenSeconds parameter is not recognized!")
        print("This means either:")
        print("  1. Anki wasn't restarted after updating the plugin")
        print("  2. The updated files weren't properly installed")
        print("  3. Python is using cached bytecode")
        print("="*50)
    else:
        print(f"   ✓ Success: {result['result']}")
        
        # Verify time was recorded
        print(f"\n7. Verifying time was recorded...")
        response = requests.post('http://localhost:8765', json={
            'action': 'getDeckTimeStats',
            'version': 6,
            'params': {
                'deckName': decks[0],
                'period': 'today'
            }
        })
        result = response.json()
        stats = result.get('result', {})
        print(f"   Total reviews today: {stats.get('totalReviews', 0)}")
        print(f"   Total time: {stats.get('totalTimeSeconds', 0)} seconds")
        print(f"   Average time per card: {stats.get('averageTimePerCardSeconds', 0)} seconds")

if __name__ == '__main__':
    try:
        test_api()
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot connect to AnkiConnect at http://localhost:8765")
        print("Make sure Anki is running with AnkiConnect installed.")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
