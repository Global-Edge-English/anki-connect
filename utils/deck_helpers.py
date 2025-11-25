# Copyright (C) 2025
# Deck Helper Functions for AnkiConnect
#
# This module provides utility functions for deck operations,
# particularly for managing deck hierarchies and configurations.

import anki.utils


def get_direct_child_decks(collection, parent_name):
    """
    Get list of direct child decks for a parent deck.
    Only returns immediate children, not grandchildren.
    
    Args:
        collection: Anki collection object
        parent_name (str): Name of the parent deck
        
    Returns:
        list: List of direct child deck names
    """
    if collection is None:
        return []
    
    children = []
    prefix = parent_name + '::'
    
    for deck_id, deck in collection.decks.decks.items():
        deck_name = deck['name']
        
        # Check if this deck is a direct child
        if deck_name.startswith(prefix):
            # Get the part after the parent prefix
            remainder = deck_name[len(prefix):]
            
            # Only include if there are no more '::' (direct child only)
            if '::' not in remainder:
                children.append(deck_name)
    
    return children


def get_deck_limits(collection, deck_name):
    """
    Get the current newCardsPerDay and reviewsPerDay limits for a deck.
    
    Args:
        collection: Anki collection object
        deck_name (str): Name of the deck
        
    Returns:
        tuple: (newCardsPerDay, reviewsPerDay)
    """
    if collection is None:
        return (0, 0)
    
    deck = collection.decks.byName(deck_name)
    if deck is None:
        return (0, 0)
    
    # Get the deck's configuration
    config = collection.decks.confForDid(deck['id'])
    if config is None:
        return (0, 0)
    
    new_cards = config.get('new', {}).get('perDay', 0)
    reviews = config.get('rev', {}).get('perDay', 0)
    
    return (new_cards, reviews)


def update_parent_deck_silent(collection, parent_name, new_cards_total, reviews_total):
    """
    Silently update a parent deck's study limits without returning info.
    
    Args:
        collection: Anki collection object
        parent_name (str): Name of the parent deck
        new_cards_total (int): Total new cards per day for all children
        reviews_total (int): Total reviews per day for all children
    """
    if collection is None:
        return
    
    # Get the parent deck
    parent_deck = collection.decks.byName(parent_name)
    if parent_deck is None:
        return
    
    parent_id = parent_deck['id']
    current_config_id = parent_deck.get('conf', 1)
    
    try:
        # Check if this config is shared by other decks
        decks_using_config = []
        for did, d in collection.decks.decks.items():
            if d.get('conf') == current_config_id and did != str(parent_id):
                decks_using_config.append(d['name'])
        
        # If config is shared, clone it for this deck only
        if len(decks_using_config) > 0:
            current_config = collection.decks.getConf(current_config_id)
            new_config_name = f"{parent_name} Options"
            new_config_id = collection.decks.confId(new_config_name, current_config)
            
            # Assign the new config to this deck
            parent_deck['conf'] = new_config_id
            collection.decks.save(parent_deck)
            
            # Get the newly created config
            config = collection.decks.getConf(new_config_id)
        else:
            # Config is not shared, safe to modify directly
            config = collection.decks.confForDid(parent_id)
        
        if config is None:
            return
        
        # Update the limits
        config['new']['perDay'] = new_cards_total
        config['rev']['perDay'] = reviews_total
        
        # Save the configuration
        config['mod'] = anki.utils.intTime()
        config['usn'] = collection.usn()
        collection.decks.save(config)
        collection.autosave()
        
    except Exception:
        # Silently fail - don't interrupt the main operation
        pass
