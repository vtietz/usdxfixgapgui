import configparser
import io

# Simulate the config save logic
c = configparser.ConfigParser()
c['Paths'] = {'last_directory': 'Z:/test', 'other': 'value'}

print("Initial state:")
print(f"  last_directory = '{c['Paths']['last_directory']}'")

# Simulate the save logic where last_directory is empty
last_directory_value = ""  # Simulating empty value

# This is the logic from config.py line 234-236
if last_directory_value:
    c['Paths']['last_directory'] = last_directory_value
    print("\nUpdated last_directory in _config")
else:
    print("\nSkipped updating last_directory (empty value)")

# Now write to string
s = io.StringIO()
c.write(s)

print("\nWritten config:")
print(s.getvalue())
print(f"Result: last_directory = '{c['Paths']['last_directory']}'")
