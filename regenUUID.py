import json
import uuid

json_data=open('config.json.original', 'r')
data = json.load(json_data)
data['key'] = str(uuid.uuid4())

json.dump(data, open('config.json', 'w+b'), indent=1, sort_keys=True)