#!/bin/bash

# Script to convert model_pools/models.csv to new format
# From: id,name,description,provider,tokens_served,is_new,capabilities,input_modalities,output_modalities,context_length,created,last_updated,raw_data,is_available,failure_count,last_failure_at,unavailable_reason,marked_unavailable_at,elo_score,matches_played,wins,losses,predict,logo_url
# To: id,author,slug,context_window,pricing,endpoint,max_tokens

set -e

INPUT_FILE="model_pools/models.csv"
OUTPUT_FILE="model_pools/models2.csv"

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: $INPUT_FILE not found!"
    exit 1
fi

echo "Converting $INPUT_FILE to $OUTPUT_FILE..."

# Use Python to properly parse the CSV with quoted fields and handle multiline descriptions
python3 << 'EOF'
import csv
import re
import sys

def slugify(text):
    """Convert text to slug format"""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    text = re.sub(r'^_+|_+$', '', text)
    return text

converted_count = 0
error_count = 0

# Read input CSV and write output CSV
try:
    with open('model_pools/models.csv', 'r', encoding='utf-8') as infile, \
         open('model_pools/models2.csv', 'w', encoding='utf-8', newline='') as outfile:
        
        # Use QUOTE_ALL to handle problematic fields
        reader = csv.DictReader(infile, quoting=csv.QUOTE_ALL)
        writer = csv.writer(outfile, quoting=csv.QUOTE_MINIMAL)
        
        # Write header
        writer.writerow(['id', 'author', 'slug', 'context_window', 'pricing', 'endpoint', 'max_tokens'])
        
        for row in reader:
            try:
                # Extract fields from original CSV
                model_id = row['id'].strip() if 'id' in row and row['id'] else ''
                provider = row['provider'].strip() if 'provider' in row and row['provider'] else ''
                context_length = row['context_length'].strip() if 'context_length' in row and row['context_length'] else ''
                
                # Skip empty rows
                if not model_id:
                    continue
                
                # Generate slug from id
                slug = slugify(model_id)
                
                # Map to new format
                author = provider if provider else 'unknown'
                context_window = context_length if context_length and context_length != 'null' else '32768'
                pricing = '0.0'  # Default pricing
                endpoint = 'openrouter'  # Default endpoint  
                max_tokens = '4096'  # Default max tokens
                
                # Ensure context_window is numeric
                try:
                    int(context_window)
                except (ValueError, TypeError):
                    context_window = '32768'
                
                # Write converted row
                writer.writerow([model_id, author, slug, context_window, pricing, endpoint, max_tokens])
                converted_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"Warning: Skipped row due to error: {e}", file=sys.stderr)
                continue

except Exception as e:
    print(f"Error processing CSV: {e}", file=sys.stderr)
    sys.exit(1)

print(f"CSV conversion completed! Converted {converted_count} rows, skipped {error_count} rows.")
EOF

echo "Conversion complete!"
echo "Original file: $INPUT_FILE ($(wc -l < "$INPUT_FILE") lines)"
echo "Converted file: $OUTPUT_FILE ($(wc -l < "$OUTPUT_FILE") lines)"
echo ""
echo "Sample of converted data:"
head -5 "$OUTPUT_FILE"