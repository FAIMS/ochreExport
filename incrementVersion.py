import json

data = {}

with open('config.json') as data_file:    
    data = json.load(data_file)

    data["version"] = data["version"] + 1

with open('config.json', 'w') as outfile:
    json.dump(data, outfile)

