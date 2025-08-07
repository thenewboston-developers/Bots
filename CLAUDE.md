# Bots Project Guidelines

## Code Organization

### Class Method Ordering
For all classes in this project, methods should be organized as follows:

1. **Dunder methods first**:
   - `__init__` always comes first
   - All other dunder methods follow, alphabetized (e.g., `__eq__`, `__repr__`, `__str__`)

2. **Regular methods**:
   - All non-dunder methods should be alphabetized

### Static Methods
- Any method that doesn't use `self` or instance variables should be decorated with `@staticmethod`
- This makes the code clearer about which methods are instance-specific vs. general utilities

### Example Structure
```python
class ExampleClass:
    def __init__(self):
        pass
    
    def __repr__(self):
        pass
    
    def __str__(self):
        pass
    
    @staticmethod
    def calculate_something(value):
        pass
    
    def fetch_data(self):
        pass
    
    def process_results(self):
        pass
```