"""
Example file with various TODO markers for testing the scanner.
DELETE THIS FILE after testing!
"""

# TODO: Implement authentication
# This is a high-priority task


def process_data(items):
    """Process a list of items."""
    # FIXME: This breaks if items is None
    for item in items:
        # HACK: temporary workaround until API is fixed
        result = item.get("value", 0) * 2
        
        # TODO: add logging here
        print(result)
    
    # XXX: This entire function needs refactoring
    return True


class UserService:
    """Handle user operations."""
    
    def get_user(self, user_id):
        # TEMP: hardcoded for testing, remove before release
        if user_id == 123:
            return {"name": "Test User"}
        
        # TODO(alice): Implement actual database lookup
        return None
    
    # TODO: add update_user method
    # TODO: add delete_user method


# This line has TODO in a string, should NOT be detected:
message = "TODO: this should not be found"

# But this should be found:
# TODO: clean up this file
