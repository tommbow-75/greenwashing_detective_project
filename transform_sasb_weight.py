import json
from pathlib import Path

# Read the original SASB weight map
input_file = Path(__file__).parent / "static" / "data" / "SASB_weightMap.json"
output_file = Path(__file__).parent / "static" / "data" / "SASB_weightMap_by_industry.json"

with open(input_file, 'r', encoding='utf-8') as f:
    sasb_data = json.load(f)

# Get all industries (all keys except '面向' and '議題')
all_industries = set()
for item in sasb_data:
    for key in item.keys():
        if key not in ['面向', '議題']:
            all_industries.add(key)

# Create the transformed structure
transformed_data = []

for industry in sorted(all_industries):
    industry_weights = {"產業": industry}
    
    for item in sasb_data:
        topic = item['議題']
        if industry in item:
            industry_weights[topic] = item[industry]
    
    transformed_data.append(industry_weights)

# Write the transformed data
with open(output_file, 'w', encoding='utf-8') as f:
    json.dump(transformed_data, f, ensure_ascii=False, indent=2)

print(f"✅ Transformation complete!")
print(f"📄 Input: {input_file}")
print(f"📄 Output: {output_file}")
print(f"📊 Total industries: {len(transformed_data)}")
print(f"\n例子 (半導體業):")
for item in transformed_data:
    if item['產業'] == '半導體業':
        print(json.dumps(item, ensure_ascii=False, indent=2))
        break
