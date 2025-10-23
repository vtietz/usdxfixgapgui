import configparser
import os
import tempfile

# Create a temp config file with a value
temp_dir = tempfile.mkdtemp()
config_path = os.path.join(temp_dir, 'test_config.ini')

# Write initial config with last_directory set
c = configparser.ConfigParser()
c['Paths'] = {'last_directory': 'Z:/UltraStarDeluxe/Songs', 'other': 'value'}
with open(config_path, 'w') as f:
    c.write(f)

print("Initial config file:")
with open(config_path, 'r') as f:
    print(f.read())

# Now simulate what the app does
c2 = configparser.ConfigParser()
c2.read(config_path)

print("\nAfter reading, _config dict contains:")
print(f"  last_directory = '{c2['Paths']['last_directory']}'")

# Simulate the property
last_directory_prop = c2.get('Paths', 'last_directory')
print(f"\nProperty value: '{last_directory_prop}'")

# Now simulate save WITHOUT updating the dict (old buggy behavior)
print("\n--- Simulating OLD save logic (when last_directory is empty) ---")
last_directory_prop = ""  # User somehow cleared it or it was never set

# Old logic:
if last_directory_prop:  # This is False!
    c2['Paths']['last_directory'] = last_directory_prop
    print("Updated _config dict")
else:
    print("Skipped updating _config dict (empty value)")

print(f"\n_config dict still has: '{c2['Paths']['last_directory']}'")

# Write to file
with open(config_path, 'w') as f:
    c2.write(f)

print("\nFinal config file:")
with open(config_path, 'r') as f:
    print(f.read())

# Cleanup
import shutil
shutil.rmtree(temp_dir)
